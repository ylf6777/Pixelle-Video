# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
内容生成工具函数（Content Generation Utilities）

纯/无状态函数，通过 LLM 生成视频内容。可在不同 pipeline 中复用。

提供:
- generate_title: 标题生成（auto/direct/llm 三种策略）
- generate_narrations_from_topic: 从话题/主题生成旁白
- generate_narrations_from_content: 从用户内容生成旁白
- split_narration_script: 脚本拆分（paragraph/line/sentence 三种模式）
- generate_image_prompts: 图像提示词生成（分批 + 重试）
- generate_video_prompts: 视频提示词生成（分批 + 重试）
- generate_scene_breakdown: 文章转分镜拆解（含每镜提示词）

内部函数:
- _parse_json: 从 LLM 响应中提取 JSON（多种回退策略）
- _process_single_batch: 共享的批次处理逻辑（含重试）
"""

import asyncio
import json
import re
from typing import List, Optional, Literal, Callable

from loguru import logger


# ══════════════════════════════════════════════════════════════════════════════
# 内部工具函数
# ══════════════════════════════════════════════════════════════════════════════

def _parse_json(text: str) -> dict:
    """
    从文本中解析 JSON，支持多种回退策略。

    解析顺序:
        1. 直接 json.loads 解析
        2. 从 markdown 代码块中提取（```json ... ```）
        3. 匹配合法 JSON 数组 [{...}]
        4. 匹配包含已知键的对象 {"narrations"|"image_prompts"|"narration": [...]}
        5. 通用括号匹配（最后一个回退）

    Args:
        text: LLM 返回的原始文本，可能包含 JSON

    Returns:
        解析后的 JSON 对象（dict 或 list）

    Raises:
        json.JSONDecodeError: 如果所有策略都无法提取有效 JSON

    Requires:
        - text 为非空字符串或包含 JSON 子串的文本

    Side Effects:
        - 输出 debug 级别日志（输入长度和预览）
    """
    logger.debug(f"_parse_json: input ({len(text)} chars): {text[:200]}...")
    # 首先尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取 JSON（对象或数组）
    json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 优先匹配数组 [{...}]（generate_scene_breakdown 使用此格式）
    # 必须在对象匹配之前执行，避免匹配到数组内的第一个 {obj}
    arr_start = text.find('[{')
    if arr_start != -1:
        arr_end = text.rfind('}]')
        if arr_end > arr_start:
            try:
                json_str = text[arr_start:arr_end + 2]
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # 尝试匹配包含已知键的 JSON 对象
    obj_pattern = r'\{[^{}]*(?:"narrations"|"image_prompts"|"narration")\s*:\s*\[[^\]]*\][^{}]*\}'
    match = re.search(obj_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 通用括号匹配（数组的最终回退）
    bracket_start = text.find('[')
    bracket_end = text.rfind(']')
    if bracket_start != -1 and bracket_end > bracket_start:
        try:
            json_str = text[bracket_start:bracket_end + 1]
            result = json.loads(json_str)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 所有策略均失败，抛出异常
    raise json.JSONDecodeError("No valid JSON found", text, 0)


async def _process_single_batch(
    llm_service,
    batch_narrations: List[str],
    batch_idx: int,
    total_batches: int,
    prompt_key: str,
    build_prompt_fn: Callable[..., str],
    min_words: int,
    max_words: int,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
) -> List[str]:
    """
    处理单个批次的提示词生成，带重试逻辑。

    此为 generate_image_prompts 和 generate_video_prompts 的共享内部函数。
    不直接调用 prompt builder，而是通过 build_prompt_fn 参数注入。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        batch_narrations: 当前批次的旁白列表
        batch_idx: 当前批次索引（1-based）
        total_batches: 总批次数
        prompt_key: JSON 响应中期望的键名（如 "image_prompts" 或 "video_prompts"）
        build_prompt_fn: 构建提示词的函数，签名为 fn(narrations, min_words, max_words) -> str
        min_words: 提示词最少字数
        max_words: 提示词最多字数
        max_retries: 每批次最大重试次数（默认 3）
        progress_callback: 可选进度回调 completed, total, message

    Returns:
        当前批次生成的提示词列表

    Raises:
        ValueError: max_retries 耗尽后仍验证失败（如数量不匹配）
        json.JSONDecodeError: max_retries 耗尽后仍无法解析 LLM 响应
        KeyError: LLM 响应中缺少 prompt_key 指定的键

    Requires:
        - llm_service 为可 await 的对象，接受 prompt/temperature/max_tokens 参数
        - build_prompt_fn 返回格式化后的完整提示词字符串
        - batch_narrations 非空

    Side Effects:
        - 调用 LLM 服务（网络请求）
        - 输出 debug/info/warning/error 级别日志
        - 在重试时调用 asyncio.sleep
    """
    logger.info(f"Processing batch {batch_idx}/{total_batches} ({len(batch_narrations)} narrations)")

    # 该批次的带重试循环
    for attempt in range(1, max_retries + 1):
        try:
            # 为该批次生成提示词
            prompt = build_prompt_fn(
                narrations=batch_narrations,
                min_words=min_words,
                max_words=max_words
            )

            response = await llm_service(
                prompt=prompt,
                temperature=0.7,
                max_tokens=8192
            )

            logger.debug(
                f"Batch {batch_idx} attempt {attempt}: "
                f"LLM response length: {len(response)} chars"
            )

            # 解析 JSON
            result = _parse_json(response)

            if prompt_key not in result:
                raise KeyError(
                    f"Invalid response format: missing '{prompt_key}' key"
                )

            batch_prompts = result[prompt_key]

            # 验证批次结果 — 数量必须精确匹配
            if len(batch_prompts) != len(batch_narrations):
                error_msg = (
                    f"Batch {batch_idx} prompt count mismatch "
                    f"(attempt {attempt}/{max_retries}):\n"
                    f"  Expected: {len(batch_narrations)} prompts\n"
                    f"  Got: {len(batch_prompts)} prompts"
                )
                logger.warning(error_msg)

                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.info(f"Retrying batch {batch_idx} in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise ValueError(error_msg)

            # 成功！
            logger.info(
                f"✅ Batch {batch_idx} completed successfully "
                f"({len(batch_prompts)} prompts)"
            )

            # 报告进度
            if progress_callback:
                progress_callback(
                    0,  # completed 由调用方计算
                    0,  # total 由调用方计算
                    f"Batch {batch_idx}/{total_batches} completed"
                )

            return batch_prompts

        except json.JSONDecodeError as e:
            logger.error(
                f"Batch {batch_idx} JSON parse error "
                f"(attempt {attempt}/{max_retries}): {e}"
            )
            if attempt >= max_retries:
                raise
            delay = 2 ** attempt
            logger.info(f"Retrying batch {batch_idx} in {delay}s...")
            await asyncio.sleep(delay)

        except KeyError as e:
            logger.error(
                f"Batch {batch_idx} missing key error "
                f"(attempt {attempt}/{max_retries}): {e}"
            )
            if attempt >= max_retries:
                raise
            delay = 2 ** attempt
            logger.info(f"Retrying batch {batch_idx} in {delay}s...")
            await asyncio.sleep(delay)

    # 不应到达此处（所有路径均 return 或 raise）
    raise RuntimeError(
        f"Batch {batch_idx}: unexpected end of retry loop"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 标题生成
# ══════════════════════════════════════════════════════════════════════════════

async def generate_title(
    llm_service,
    content: str,
    strategy: Literal["auto", "direct", "llm"] = "auto",
    max_length: int = 15
) -> str:
    """
    从内容生成标题。

    支持三种策略:
    - "direct": 直接用内容截断（无需 LLM 调用）
    - "auto": 自动决定（内容短直接用，长则调 LLM）
    - "llm": 始终通过 LLM 生成标题

    生成后会自动清理引号和尾部标点，并智能截断到 max_length。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        content: 源内容（话题或脚本）
        strategy: 生成策略
            - "auto": 根据内容长度自动决定（默认）
            - "direct": 直接使用内容（必要时截断）
            - "llm": 始终使用 LLM 生成
        max_length: 标题最大字符数（默认 15）

    Returns:
        生成并清理后的标题字符串

    Raises:
        无（LLM 错误由调用方处理，direct/auto 策略不调用 LLM）

    Requires:
        - content 为非空字符串
        - llm_service 在 strategy 为 "llm" 或 "auto"（长内容时）可用

    Side Effects:
        - strategy 为 "llm" 或 auto（长内容）时：调用 LLM 服务
        - 输出 debug 级别日志（生成的标题和长度）
    """
    if strategy == "direct":
        content = content.strip()
        return content[:max_length] if len(content) > max_length else content

    if strategy == "auto":
        if len(content.strip()) <= 15:
            return content.strip()
        # 继续走 LLM 分支

    # 使用 LLM 生成标题
    from pixelle_video.prompts import build_title_generation_prompt

    # 将 max_length 传给 prompt，让 LLM 知道字符限制
    prompt = build_title_generation_prompt(content, max_length=max_length)
    response = await llm_service(prompt, temperature=0.7, max_tokens=2000)

    # 清理响应
    title = response.strip()

    # 去除引号
    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]
    if title.startswith("'") and title.endswith("'"):
        title = title[1:-1]

    # 去除尾部标点
    title = title.rstrip('.,!?;:\'"')

    # 安全兜底：仍超限时智能截断
    if len(title) > max_length:
        # 尝试在词边界截断
        truncated = title[:max_length]
        last_space = truncated.rfind(' ')

        # 仅在回退不太远时使用词边界（至少保留 max_length 的 60%）
        if last_space > max_length * 0.6:
            title = truncated[:last_space]
        else:
            title = truncated

        # 截断后再次去除尾部标点
        title = title.rstrip('.,!?;:\'"')

    logger.debug(f"Generated title: '{title}' (length: {len(title)})")
    return title


# ══════════════════════════════════════════════════════════════════════════════
# 旁白生成
# ══════════════════════════════════════════════════════════════════════════════

async def generate_narrations_from_topic(
    llm_service,
    topic: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20
) -> List[str]:
    """
    从话题/主题生成旁白列表。

    使用 build_topic_narration_prompt 构建提示词，
    LLM 返回 JSON 格式的 narrations 数组。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        topic: 要生成旁白的话题或主题文本
        n_scenes: 需要生成的旁白数量（默认 5）
        min_words: 每段旁白最少字数（默认 5）
        max_words: 每段旁白最多字数（默认 20）

    Returns:
        旁白文本列表，长度等于 n_scenes

    Raises:
        ValueError: 如果 LLM 响应中缺少 "narrations" 键，
                   或返回数量与 n_scenes 不匹配（多取少报错）
        json.JSONDecodeError: 如果 LLM 响应无法解析为 JSON

    Requires:
        - llm_service 可用且接受 prompt/temperature/max_tokens 参数
        - topic 为非空字符串

    Side Effects:
        - 调用 LLM 服务（网络请求）
        - 输出 info/debug/warning 级别日志
    """
    from pixelle_video.prompts import build_topic_narration_prompt

    logger.info(f"Generating {n_scenes} narrations from topic: {topic}")

    prompt = build_topic_narration_prompt(
        topic=topic,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words
    )

    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=10000
    )

    logger.debug(f"LLM response: {response[:200]}...")

    # 解析 JSON
    result = _parse_json(response)

    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")

    narrations = result["narrations"]

    # 验证数量
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")

    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


async def generate_narrations_from_content(
    llm_service,
    content: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20
) -> List[str]:
    """
    从用户提供的原始内容生成旁白列表。

    与 generate_narrations_from_topic 不同，此函数使用
    build_content_narration_prompt 构建提示词，适合从长文中提取核心观点。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        content: 用户提供的原始内容文本
        n_scenes: 需要生成的旁白数量（默认 5）
        min_words: 每段旁白最少字数（默认 5）
        max_words: 每段旁白最多字数（默认 20）

    Returns:
        旁白文本列表，长度等于 n_scenes

    Raises:
        ValueError: 如果 LLM 响应中缺少 "narrations" 键，
                   或返回数量与 n_scenes 不匹配
        json.JSONDecodeError: 如果 LLM 响应无法解析为 JSON

    Requires:
        - llm_service 可用且接受 prompt/temperature/max_tokens 参数
        - content 为非空字符串

    Side Effects:
        - 调用 LLM 服务（网络请求）
        - 输出 info/debug/warning 级别日志
    """
    from pixelle_video.prompts import build_content_narration_prompt

    logger.info(f"Generating {n_scenes} narrations from content ({len(content)} chars)")

    prompt = build_content_narration_prompt(
        content=content,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words
    )

    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=10000
    )

    # 解析 JSON
    result = _parse_json(response)

    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")

    narrations = result["narrations"]

    # 验证数量
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")

    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


# ══════════════════════════════════════════════════════════════════════════════
# 脚本拆分
# ══════════════════════════════════════════════════════════════════════════════

async def split_narration_script(
    script: str,
    split_mode: Literal["paragraph", "line", "sentence"] = "paragraph",
) -> List[str]:
    """
    将用户提供的旁白脚本拆分为片段。

    支持三种拆分模式:
    - "paragraph": 按双换行拆分，保留段内单换行
    - "line": 按单换行拆分，每行一个片段
    - "sentence": 按句末标点拆分（支持中英文）

    Args:
        script: 完整的旁白脚本文本
        split_mode: 拆分策略
            - "paragraph": 按 \\n\\n 拆分段落（默认）
            - "line": 按 \\n 拆分行
            - "sentence": 按句子结尾标点拆分（。.!?！？）

    Returns:
        旁白片段列表

    Raises:
        无（未知 split_mode 时回退到 "line" 模式）

    Requires:
        - script 为非空字符串

    Side Effects:
        - 输出 info/warning 级别日志（拆分模式、片段统计）
    """
    logger.info(f"Splitting script (mode={split_mode}, length={len(script)} chars)")

    narrations = []

    if split_mode == "paragraph":
        # 按双换行拆分（段落模式）
        # 保留段落内的单换行
        paragraphs = re.split(r'\n\s*\n', script)
        for para in paragraphs:
            # 仅去除首尾空白，保留内部换行
            cleaned = para.strip()
            if cleaned:
                narrations.append(para)
        logger.info(f"✅ Split script into {len(narrations)} segments (by paragraph)")

    elif split_mode == "line":
        # 按单换行拆分（原始行为）
        narrations = [line.strip() for line in script.split('\n') if line.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by line)")

    elif split_mode == "sentence":
        # 按句末标点拆分
        # 支持中文（。！？）和英文（.!?）
        # 使用正则拆分，同时保留句子完整
        cleaned = re.sub(r'\s+', ' ', script.strip())
        # 在句末标点处拆分，标点保留在句中
        sentences = re.split(r'(?<=[。.!?！？])\s*', cleaned)
        narrations = [s.strip() for s in sentences if s.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by sentence)")

    else:
        # 回退到行模式
        logger.warning(f"Unknown split_mode '{split_mode}', falling back to 'line'")
        narrations = [line.strip() for line in script.split('\n') if line.strip()]

    # 记录统计信息
    if narrations:
        lengths = [len(s) for s in narrations]
        logger.info(
            f"   Min: {min(lengths)} chars, "
            f"Max: {max(lengths)} chars, "
            f"Avg: {sum(lengths)//len(lengths)} chars"
        )

    return narrations


# ══════════════════════════════════════════════════════════════════════════════
# 提示词生成（图像 / 视频）
# ══════════════════════════════════════════════════════════════════════════════

async def generate_image_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None
) -> List[str]:
    """
    从旁白生成图像提示词（带分批和重试）。

    将旁白列表按 batch_size 分批，每批通过 LLM 生成对应数量的英文图像提示词。
    使用 _process_single_batch 处理每批，支持自动重试。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        narrations: 旁白文本列表
        min_words: 图像提示词最少字数（默认 30）
        max_words: 图像提示词最多字数（默认 60）
        batch_size: 每批最多处理的旁白数（默认 10）
        max_retries: 每批最大重试次数（默认 3）
        progress_callback: 可选进度回调 completed, total, message

    Returns:
        图像提示词列表（基础提示词，不含 style prefix）

    Raises:
        ValueError: max_retries 耗尽后提示词数量仍不匹配
        json.JSONDecodeError: max_retries 耗尽后仍无法解析 LLM 响应
        KeyError: LLM 响应缺少 "image_prompts" 键

    Requires:
        - llm_service 为可 await 的对象
        - narrations 为非空字符串列表
        - build_image_prompt_prompt 可从 pixelle_video.prompts 导入

    Side Effects:
        - 调用 LLM 服务（网络请求，可能多次）
        - 输出 info/debug 级别日志
        - 通过 progress_callback 报告进度
    """
    from pixelle_video.prompts import build_image_prompt_prompt

    logger.info(
        f"Generating image prompts for {len(narrations)} narrations "
        f"(batch_size={batch_size})"
    )

    # 将旁白拆分为批次
    batches = [
        narrations[i:i + batch_size]
        for i in range(0, len(narrations), batch_size)
    ]
    logger.info(f"Split into {len(batches)} batches")

    all_prompts = []

    # 逐批处理
    for batch_idx, batch_narrations in enumerate(batches, 1):
        batch_prompts = await _process_single_batch(
            llm_service=llm_service,
            batch_narrations=batch_narrations,
            batch_idx=batch_idx,
            total_batches=len(batches),
            prompt_key="image_prompts",
            build_prompt_fn=build_image_prompt_prompt,
            min_words=min_words,
            max_words=max_words,
            max_retries=max_retries,
            progress_callback=None,  # 下方自行处理
        )
        all_prompts.extend(batch_prompts)

        # 报告进度
        if progress_callback:
            progress_callback(
                len(all_prompts),
                len(narrations),
                f"Batch {batch_idx}/{len(batches)} completed"
            )

    logger.info(f"✅ Generated {len(all_prompts)} image prompts")
    return all_prompts


async def generate_video_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None
) -> List[str]:
    """
    从旁白生成视频提示词（带分批和重试）。

    将旁白列表按 batch_size 分批，每批通过 LLM 生成对应数量的英文视频提示词。
    使用 _process_single_batch 处理每批，支持自动重试。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        narrations: 旁白文本列表
        min_words: 视频提示词最少字数（默认 30）
        max_words: 视频提示词最多字数（默认 60）
        batch_size: 每批最多处理的旁白数（默认 10）
        max_retries: 每批最大重试次数（默认 3）
        progress_callback: 可选进度回调 completed, total, message

    Returns:
        视频提示词列表（基础提示词，不含 style prefix）

    Raises:
        ValueError: max_retries 耗尽后提示词数量仍不匹配
        json.JSONDecodeError: max_retries 耗尽后仍无法解析 LLM 响应
        KeyError: LLM 响应缺少 "video_prompts" 键

    Requires:
        - llm_service 为可 await 的对象
        - narrations 为非空字符串列表
        - build_video_prompt_prompt 可从 pixelle_video.prompts.video_generation 导入

    Side Effects:
        - 调用 LLM 服务（网络请求，可能多次）
        - 输出 info/debug 级别日志
        - 通过 progress_callback 报告进度
    """
    from pixelle_video.prompts.video_generation import build_video_prompt_prompt

    logger.info(
        f"Generating video prompts for {len(narrations)} narrations "
        f"(batch_size={batch_size})"
    )

    # 将旁白拆分为批次
    batches = [
        narrations[i:i + batch_size]
        for i in range(0, len(narrations), batch_size)
    ]
    logger.info(f"Split into {len(batches)} batches")

    all_prompts = []

    # 逐批处理
    for batch_idx, batch_narrations in enumerate(batches, 1):
        batch_prompts = await _process_single_batch(
            llm_service=llm_service,
            batch_narrations=batch_narrations,
            batch_idx=batch_idx,
            total_batches=len(batches),
            prompt_key="video_prompts",
            build_prompt_fn=build_video_prompt_prompt,
            min_words=min_words,
            max_words=max_words,
            max_retries=max_retries,
            progress_callback=None,  # 下方自行处理
        )
        all_prompts.extend(batch_prompts)

        # 报告进度
        if progress_callback:
            progress_callback(
                len(all_prompts),
                len(narrations),
                f"Batch {batch_idx}/{len(batches)} completed"
            )

    logger.info(f"✅ Generated {len(all_prompts)} video prompts")
    return all_prompts


# ══════════════════════════════════════════════════════════════════════════════
# 分镜拆解
# ══════════════════════════════════════════════════════════════════════════════

async def generate_scene_breakdown(
    llm_service,
    article: str,
    media_type: str = "image",
) -> list[dict]:
    """
    将文章拆为分镜，每项含旁白和按字数分配的画面/视频提示词。

    根据 media_type 选择 IMAGE 或 VIDEO 分镜模板，
    返回的场景列表中每项包含 narration 和对应的 image_prompts/video_prompts。

    Args:
        llm_service: LLM 服务实例（可 await 的 callable）
        article: 待拆解的文章文本
        media_type: 媒体类型，"image" 返回 image_prompts，
                   "video" 返回 video_prompts

    Returns:
        场景字典列表，每项包含:
        - "narration": 旁白文本
        - "image_prompts" 或 "video_prompts": 对应的提示词列表

    Raises:
        ValueError: LLM 未返回分镜数组
        json.JSONDecodeError: LLM 响应无法解析为有效 JSON

    Requires:
        - llm_service 为可 await 的对象
        - article 为非空字符串
        - build_scene_breakdown_prompt 可从 pixelle_video.prompts 导入

    Side Effects:
        - 调用 LLM 服务（网络请求）
        - 可能对返回数据进行就地修改（字段规范化）
    """
    from pixelle_video.prompts.scene_breakdown import build_scene_breakdown_prompt

    prompt = build_scene_breakdown_prompt(article, media_type)
    response = await llm_service(prompt=prompt, temperature=0.7, max_tokens=8192)
    result = _parse_json(response)

    if isinstance(result, dict):
        result = result.get("scenes") or result.get("data") or []
    if not isinstance(result, list):
        raise ValueError("LLM 未返回分镜数组")

    # 根据 media_type 确定提示词字段名
    prompt_key = "video_prompts" if media_type == "video" else "image_prompts"

    for item in result:
        if prompt_key not in item:
            # 兼容旧字段名
            fallback = (
                item.get("image_prompts")
                or item.get("video_prompts")
                or [item.get("image_prompt", item.get("narration", ""))]
            )
            if isinstance(fallback, str):
                fallback = [fallback]
            item[prompt_key] = fallback
        if isinstance(item[prompt_key], str):
            item[prompt_key] = [item[prompt_key]]
        if "narration" not in item:
            item["narration"] = item.get("text", "")

    return result
