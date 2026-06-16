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
TTS（文字转语音）端点

提供文本到语音合成接口，基于 ComfyUI 工作流。
支持指定工作流和参考音频进行语音克隆。
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.error_handler import map_exception
from api.dependencies import PixelleVideoDep
from api.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from pixelle_video.utils.tts_util import get_audio_duration

router = APIRouter(prefix="/tts", tags=["Basic Services"])


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def tts_synthesize(
    request: TTSSynthesizeRequest,
    pixelle_video: PixelleVideoDep
):
    """
    文字转语音合成端点

    使用 ComfyUI 工作流将文本转换为语音音频。

    入参（TTSSynthesizeRequest）:
        - **text** (str): 需要合成的文本，必填
        - **workflow** (str, optional): TTS 工作流 key。
            如 'runninghub/tts_edge.json' 或 'selfhost/tts_edge.json'。
            不指定则使用配置中的默认工作流。
        - **ref_audio** (str, optional): 参考音频路径，用于语音克隆。可以是本地路径或 URL。
        - **voice_id** (str, optional): 已弃用。请改用 workflow。

    Returns:
        TTSSynthesizeResponse: 包含以下字段：
            - audio_path (str): 生成的音频文件路径
            - duration (float): 音频时长（秒）

    Raises:
        HTTPException 400: ValueError — 参数无效
        HTTPException 500: 内部服务错误 — TTS 工作流执行失败

    Requires:
        - pixelle_video.tts   — 必须已通过 PixelleVideoCore.initialize() 初始化
        - ComfyUI 服务          — 用于执行 TTS 工作流
        - get_audio_duration   — pixelle_video.utils.tts_util 中的音频时长工具函数

    Side Effects:
        - 调用 ComfyUI API 执行 TTS 工作流（网络请求）
        - 生成音频文件写入磁盘
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"TTS 合成请求: {request.text[:50]}...")

        # 构建 TTS 参数
        tts_params = {"text": request.text}

        # 如果指定了工作流，传入对应参数
        if request.workflow:
            tts_params["workflow"] = request.workflow

        # 如果指定了参考音频，传入用于语音克隆
        if request.ref_audio:
            tts_params["ref_audio"] = request.ref_audio

        # 旧版 voice_id 参数支持（已弃用）
        if request.voice_id and not request.workflow:
            logger.warning("voice_id 参数已弃用，请改用 workflow")
            tts_params["voice"] = request.voice_id

        # 调用 TTS 服务
        audio_path = await pixelle_video.tts(**tts_params)

        # 获取音频时长
        duration = get_audio_duration(audio_path)

        return TTSSynthesizeResponse(
            audio_path=audio_path,
            duration=duration
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "tts")
