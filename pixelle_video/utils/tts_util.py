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
Edge TTS 工具函数（Edge TTS Utility）

基于 Microsoft Edge 免费文字转语音服务。

功能:
- edge_tts: 文字转语音（400+ 语音，100+ 语言），含自动重试
- get_audio_duration: 获取音频文件时长（ffmpeg 优先，文件大小回退）
- list_voices: 列出所有可用语音

设计特性:
- 指数退避 + 随机抖动重试
- 通过 asyncio.Semaphore 控制并发请求数
- 预请求随机延迟进行频率控制
- 通过 certifi 进行 SSL 验证

注意: 当前 TTS 服务已改用 ComfyUI 工作流，此模块保留供未来使用。
"""

import asyncio
import ssl
import random
import certifi
import edge_tts as edge_tts_sdk
from edge_tts.exceptions import NoAudioReceived
from loguru import logger
from aiohttp import WSServerHandshakeError, ClientResponseError


# 使用 certifi 证书包进行 SSL 验证，替代直接禁用验证
_USE_CERTIFI_SSL = True

# Edge TTS 重试配置（处理 401 认证错误和 NoAudioReceived）
_RETRY_COUNT = 5           # 默认重试次数
_RETRY_BASE_DELAY = 1.0     # 基础重试延迟（秒），用于指数退避
_MAX_RETRY_DELAY = 10.0     # 最大重试延迟（秒）

# 频率控制配置
_REQUEST_DELAY = 0.5        # 每次请求前的最小延迟（秒）
_MAX_CONCURRENT_REQUESTS = 3  # 最大并发请求数

# 全局信号量，用于频率限制（每个事件循环一个实例）
_request_semaphore = None
_semaphore_loop = None


def _get_request_semaphore() -> asyncio.Semaphore:
    """
    获取或创建当前事件循环的请求信号量。

    使用信号量限制并发 Edge TTS 请求数量，防止被 Microsoft 服务限流。
    每个事件循环一个信号量实例。

    Args:
        无

    Returns:
        asyncio.Semaphore 实例，限制为 _MAX_CONCURRENT_REQUESTS

    Raises:
        无（无运行中事件循环时创建新信号量）

    Requires:
        无

    Side Effects:
        - 可能更新模块级全局变量 _request_semaphore 和 _semaphore_loop
    """
    global _request_semaphore, _semaphore_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        # 无运行中的事件循环
        return asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

    # 如果信号量不存在或属于不同的事件循环，创建新的
    if _request_semaphore is None or _semaphore_loop != current_loop:
        _request_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)
        _semaphore_loop = current_loop

    return _request_semaphore


async def edge_tts(
    text: str,
    voice: str = "[Chinese] zh-CN Yunjian",
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    output_path: str = None,
    retry_count: int = _RETRY_COUNT,
    retry_base_delay: float = _RETRY_BASE_DELAY,
) -> bytes:
    """
    使用 Microsoft Edge TTS 将文本转换为语音。

    免费服务，无需 API Key。支持 400+ 种语音和 100+ 种语言。
    返回 MP3 格式的音频字节数据。

    包含自动重试机制（指数退避 + 随机抖动）处理 401 认证错误
    和临时网络问题。同时包含并发请求限制和频率控制。

    Args:
        text: 要转换为语音的文本
        voice: 语音 ID（如 "[Chinese] zh-CN Yunjian", "[English] en-US Jenny"）
        rate: 语速（如 "+0%", "+50%", "-20%"）
        volume: 音量（如 "+0%", "+50%", "-20%"）
        pitch: 音调（如 "+0Hz", "+10Hz", "-5Hz"）
        output_path: 可选输出文件路径，提供时保存音频到文件
        retry_count: 失败时的重试次数（默认 5）
        retry_base_delay: 指数退避的基础延迟（秒，默认 1.0）

    Returns:
        MP3 格式的音频字节数据

    Raises:
        WSServerHandshakeError: 所有重试耗尽后仍无法握手
        ClientResponseError: 所有重试耗尽后仍收到客户端错误
        NoAudioReceived: 所有重试耗尽后仍未收到音频数据
        Exception: 其他不可重试的错误（如参数无效）

    Requires:
        - text 为非空字符串
        - 网络连接可访问 Microsoft Edge TTS 服务
        - certifi 包可用于 SSL 验证

    Side Effects:
        - 发起 WebSocket 连接到 Microsoft Edge TTS 服务
        - 如果提供 output_path，写入音频文件到磁盘
        - 输出 debug/info/warning 级别日志

    Popular Chinese voices:
    - [Chinese] zh-CN Yunjian (male, default)
    - [Chinese] zh-CN Xiaoxiao (female)
    - [Chinese] zh-CN Yunxi (male)
    - [Chinese] zh-CN Xiaoyi (female)

    Popular English voices:
    - [English] en-US Jenny (female)
    - [English] en-US Guy (male)
    - [English] en-GB Sonia (female, British)

    Example:
        audio_bytes = await edge_tts(
            text="你好，世界！",
            voice="[Chinese] zh-CN Yunjian",
            rate="+20%"
        )
    """
    logger.debug(f"Calling Edge TTS with voice: {voice}, rate: {rate}, retry_count: {retry_count}")

    # 使用信号量限制并发请求
    request_semaphore = _get_request_semaphore()
    async with request_semaphore:
        # 每次请求前添加小随机延迟，避免触发频率限制
        pre_delay = _REQUEST_DELAY + random.uniform(0, 0.3)
        logger.debug(f"Waiting {pre_delay:.2f}s before request (rate limiting)")
        await asyncio.sleep(pre_delay)

        last_error = None

        # 重试循环
        for attempt in range(retry_count + 1):  # +1 因为第一次是初始请求而非重试
            if attempt > 0:
                # 指数退避 + 随机抖动
                # delay = base * (2 ^ attempt) + random jitter
                exponential_delay = retry_base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, retry_base_delay)
                retry_delay = min(exponential_delay + jitter, _MAX_RETRY_DELAY)

                logger.info(f"🔄 Retrying Edge TTS (attempt {attempt + 1}/{retry_count + 1}) after {retry_delay:.2f}s delay...")
                await asyncio.sleep(retry_delay)

            try:
                # 使用 certifi SSL 上下文创建通信实例
                if _USE_CERTIFI_SSL:
                    if attempt == 0:  # 仅首次记录信息日志
                        logger.debug("Using certifi SSL certificates for secure Edge TTS connection")
                    # 使用 certifi 证书包创建 SSL 上下文
                    import certifi
                    ssl_context = ssl.create_default_context(cafile=certifi.where())
                else:
                    ssl_context = None

                # 创建通信实例
                communicate = edge_tts_sdk.Communicate(
                    text=text,
                    voice=voice,
                    rate=rate,
                    volume=volume,
                    pitch=pitch,
                )

                # 收集音频分块
                audio_chunks = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])

                audio_data = b"".join(audio_chunks)

                if attempt > 0:
                    logger.success(f"✅ Retry succeeded on attempt {attempt + 1}")

                logger.info(f"Generated {len(audio_data)} bytes of audio data")

                # 如果提供了 output_path 则保存到文件
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    logger.info(f"Audio saved to: {output_path}")

                return audio_data

            except (WSServerHandshakeError, ClientResponseError) as e:
                # 网络/认证错误 — 重试
                last_error = e
                error_code = getattr(e, 'status', 'unknown')
                error_msg = str(e)

                # 对 401 错误记录更详细信息
                if error_code == 401 or '401' in error_msg:
                    logger.warning(f"⚠️  Edge TTS 401 Authentication Error (attempt {attempt + 1}/{retry_count + 1})")
                    logger.debug(f"Error details: {error_msg}")
                    logger.debug(f"This is usually caused by rate limiting. Will retry with exponential backoff...")
                else:
                    logger.warning(f"⚠️  Edge TTS error (attempt {attempt + 1}/{retry_count + 1}): {error_code} - {e}")

                if attempt >= retry_count:
                    # 最后一次尝试失败
                    logger.error(f"❌ All {retry_count + 1} attempts failed. Last error: {error_code}")
                    raise
                # 否则继续下次重试

            except NoAudioReceived as e:
                # NoAudioReceived 通常是临时问题 — 用更长的延迟重试
                last_error = e
                logger.warning(f"⚠️  Edge TTS NoAudioReceived (attempt {attempt + 1}/{retry_count + 1})")
                logger.debug(f"This is usually a temporary Microsoft service issue. Will retry with longer delay...")

                if attempt >= retry_count:
                    logger.error(f"❌ All {retry_count + 1} attempts failed due to NoAudioReceived")
                    raise
                # NoAudioReceived 错误增加额外延迟
                await asyncio.sleep(2.0)

            except Exception as e:
                # 其他错误 — 不重试，立即抛出
                logger.error(f"Edge TTS error (non-retryable): {type(e).__name__} - {e}")
                raise

        # 不应到达此处，但做兜底处理
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Edge TTS failed without error (unexpected)")


def get_audio_duration(audio_path: str) -> float:
    """
    获取音频文件的时长（秒）。

    优先使用 ffmpeg.probe 精确获取，失败时回退到基于文件大小的粗略估算。

    Args:
        audio_path: 音频文件路径

    Returns:
        音频时长（秒），最小返回 1.0 秒

    Raises:
        无（异常在内部捕获，回退到估算值）

    Requires:
        - audio_path 指向有效的音频文件
        - ffmpeg 可执行文件在 PATH 中（可选，用于精确探测）
        - 文件系统可读权限

    Side Effects:
        - 如果使用 ffmpeg，会调用子进程
        - 输出 warning 级别日志（回退时）
    """
    try:
        # 尝试使用 ffmpeg-python
        import ffmpeg
        probe = ffmpeg.probe(audio_path)
        duration = float(probe['format']['duration'])
        return duration
    except Exception as e:
        logger.warning(f"Failed to get audio duration: {e}, using estimate")
        # 回退：基于文件大小估算（非常粗略）
        import os
        file_size = os.path.getsize(audio_path)
        # MP3 约 16kbps，即每秒约 2KB
        estimated_duration = file_size / 2000
        return max(1.0, estimated_duration)  # 至少 1 秒


async def list_voices(
    locale: str = None,
    retry_count: int = _RETRY_COUNT,
    retry_base_delay: float = _RETRY_BASE_DELAY
) -> list[str]:
    """
    列出 Edge TTS 所有可用的语音。

    返回语音 ID 列表（ShortName）。可按 locale 过滤。
    包含自动重试机制（指数退避 + 随机抖动）处理网络错误和限流。

    Args:
        locale: 按地区过滤语音（如 "zh-CN", "en-US", "ja-JP"）
        retry_count: 重试次数（默认 5）
        retry_base_delay: 指数退避的基础延迟（秒，默认 1.0）

    Returns:
        语音 ID 字符串列表（ShortName 格式）

    Raises:
        WSServerHandshakeError: 所有重试耗尽后仍无法握手
        ClientResponseError: 所有重试耗尽后仍收到客户端错误
        Exception: 其他不可重试的错误

    Requires:
        - 网络连接可访问 Microsoft Edge TTS 服务
        - certifi 包可用于 SSL 验证

    Side Effects:
        - 发起 HTTPS 请求到 Microsoft Edge TTS 服务
        - 输出 debug/info/warning 级别日志

    Example:
        # 列出所有语音
        voices = await list_voices()
        # Returns: ['[Chinese] zh-CN Yunjian', '[Chinese] zh-CN Xiaoxiao', ...]

        # 仅列出中文语音
        voices = await list_voices(locale="zh-CN")
        # Returns: ['[Chinese] zh-CN Yunjian', '[Chinese] zh-CN Xiaoxiao', ...]
    """
    logger.debug(f"Fetching Edge TTS voices, locale filter: {locale}, retry_count: {retry_count}")

    # 使用信号量限制并发请求
    request_semaphore = _get_request_semaphore()
    async with request_semaphore:
        # 每次请求前添加小随机延迟，避免触发频率限制
        pre_delay = _REQUEST_DELAY + random.uniform(0, 0.3)
        logger.debug(f"Waiting {pre_delay:.2f}s before request (rate limiting)")
        await asyncio.sleep(pre_delay)

        last_error = None

        # 重试循环
        for attempt in range(retry_count + 1):
            if attempt > 0:
                # 指数退避 + 随机抖动
                exponential_delay = retry_base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, retry_base_delay)
                retry_delay = min(exponential_delay + jitter, _MAX_RETRY_DELAY)

                logger.info(f"🔄 Retrying list voices (attempt {attempt + 1}/{retry_count + 1}) after {retry_delay:.2f}s delay...")
                await asyncio.sleep(retry_delay)

            try:
                # 获取所有语音（edge-tts 内部处理 SSL）
                voices = await edge_tts_sdk.list_voices()

                # 如果指定了 locale 则过滤
                if locale:
                    voices = [v for v in voices if v["Locale"].startswith(locale)]

                # 提取语音 ID（ShortName）
                voice_ids = [voice["ShortName"] for voice in voices]

                if attempt > 0:
                    logger.success(f"✅ Retry succeeded on attempt {attempt + 1}")

                logger.info(f"Found {len(voice_ids)} voices" + (f" for locale '{locale}'" if locale else ""))
                return voice_ids

            except (WSServerHandshakeError, ClientResponseError) as e:
                # 网络/认证错误 — 重试
                last_error = e
                error_code = getattr(e, 'status', 'unknown')
                error_msg = str(e)

                # 对 401 错误记录更详细信息
                if error_code == 401 or '401' in error_msg:
                    logger.warning(f"⚠️  Edge TTS 401 Authentication Error (list_voices attempt {attempt + 1}/{retry_count + 1})")
                    logger.debug(f"Error details: {error_msg}")
                    logger.debug(f"This is usually caused by rate limiting. Will retry with exponential backoff...")
                else:
                    logger.warning(f"⚠️  List voices error (attempt {attempt + 1}/{retry_count + 1}): {error_code} - {e}")

                if attempt >= retry_count:
                    logger.error(f"❌ All {retry_count + 1} attempts failed. Last error: {error_code}")
                    raise

            except Exception as e:
                # 其他错误 — 不重试，立即抛出
                logger.error(f"List voices error (non-retryable): {type(e).__name__} - {e}")
                raise

        # 不应到达此处，但做兜底处理
        if last_error:
            raise last_error
        else:
            raise RuntimeError("List voices failed without error (unexpected)")
