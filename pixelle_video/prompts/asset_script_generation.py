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
基于素材的视频脚本生成提示词（Asset Script Generation Prompt）

用于根据用户提供的素材（图片、视频）生成视频脚本。
提示词指示 LLM 将素材分配到各个场景，生成旁白，
并以 JSON 格式输出结构化场景脚本。
"""


ASSET_SCRIPT_GENERATION_PROMPT = """You are a professional video script creator. Based on the user's video intent and available assets, generate a {duration}-second video script. Before doing so, you need to detect the user's input language - if it's English, then all copy must be in English. Strictly follow the user's input language type as the standard, ensuring consistent and corresponding copy!

## Requirements
{title_section}- Video Intent: {intent}
- Target Duration: {duration} seconds

## Available Assets (use exact paths in output)
{assets_text}

## Creation Guidelines
1. Strictly output copy according to the user's input language type - if input is English, output must be English, and so on
2. Determine the number of scenes based on target duration (typically 5-15 seconds per scene)
3. Assign one asset from available assets to each scene
4. Each scene can contain 1-3 narration sentences
5. Try to use all available assets, but assets can be reused if needed
6. Total duration of all scenes should approximately equal {duration} seconds
{title_instruction}

## Language Consistency Requirements (Strictly Enforce)
- Narration language must match the user's input video intent
- If video intent is in Chinese, narration must be in Chinese
- If video intent is in English, narration must be in English
- Unless the video intent explicitly specifies an output language, strictly follow the original language of the intent

## Output Requirements
Provide for each scene:
- scene_number: Scene number (starting from 1)
- asset_path: Exact path selected from available assets list
- narrations: Array containing 1-3 narration sentences
- duration: Estimated duration (seconds)

Now please begin generating the video script:"""


def build_asset_script_prompt(
    intent: str,
    duration: int,
    assets_text: str,
    title: str = ""
) -> str:
    """
    构建基于素材的视频脚本生成提示词。

    根据用户意图、目标时长、可用素材列表和可选标题，格式化
    ASSET_SCRIPT_GENERATION_PROMPT 模板。

    Args:
        intent: 视频意图/目的描述
        duration: 目标视频时长（秒）
        assets_text: 格式化后的可用素材文本（含描述）
        title: 可选视频标题，提供时为提示词添加标题约束

    Returns:
        格式化后的完整提示词字符串

    Raises:
        KeyError: 如果模板变量名与 .format() 参数不匹配
        AttributeError: 如果参数类型与 format() 期望不符

    Requires:
        - intent 为非空字符串
        - duration 为正整数
        - assets_text 为非空字符串

    Side Effects:
        无（纯函数，仅做字符串格式化）
    """
    title_section = f"- Video Title: {title}\n" if title else ""
    title_instruction = f"6. Narration content should be consistent with the video title: {title}\n" if title else ""

    return ASSET_SCRIPT_GENERATION_PROMPT.format(
        duration=duration,
        title_section=title_section,
        intent=intent,
        assets_text=assets_text,
        title_instruction=title_instruction
    )
