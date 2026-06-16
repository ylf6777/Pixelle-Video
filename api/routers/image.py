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
图片生成端点

提供基于 ComfyKit 的 AI 图片生成接口。
注意：此端点仅支持图片工作流，使用视频工作流会返回 400 错误。
如需视频生成，请使用 /api/video 或 /api/media 相关端点。
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.error_handler import map_exception
from api.dependencies import PixelleVideoDep
from api.schemas.image import ImageGenerateRequest, ImageGenerateResponse

router = APIRouter(prefix="/image", tags=["Basic Services"])


@router.post("/generate", response_model=ImageGenerateResponse)
async def image_generate(
    request: ImageGenerateRequest,
    pixelle_video: PixelleVideoDep
):
    """
    图片生成端点

    使用 ComfyKit 从文本提示词生成图片。

    入参（ImageGenerateRequest）:
        - **prompt** (str): 图片描述/提示词，必填
        - **width** (int): 图片宽度 (512-2048)。默认: 1024
        - **height** (int): 图片高度 (512-2048)。默认: 1024
        - **workflow** (str, optional): 自定义工作流文件名

    Returns:
        ImageGenerateResponse: 包含以下字段：
            - image_path (str): 生成的图片文件路径

    Raises:
        HTTPException 400: ``ValueError`` — 参数无效；或使用了视频工作流
        HTTPException 500: 内部服务错误 — ComfyKit 工作流执行失败

    Requires:
        - pixelle_video.media  — 必须已通过 PixelleVideoCore.initialize() 初始化
        - ComfyKit / ComfyUI    — 用于执行图片生成工作流

    Side Effects:
        - 调用 ComfyUI API 生成图片（网络请求）
        - 图片文件写入磁盘
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"图片生成请求: {request.prompt[:50]}...")

        # 调用 media 服务（向后兼容 image API）
        media_result = await pixelle_video.media(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            workflow=request.workflow
        )

        # 向后兼容：/image 端点仅支持图片结果
        if media_result.is_video:
            raise HTTPException(
                status_code=400,
                detail="检测到视频工作流。视频生成请使用 /media/generate 端点。"
            )

        return ImageGenerateResponse(
            image_path=media_result.url
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "image")
