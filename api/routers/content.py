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
内容生成端点

提供基于 LLM 的旁白生成、图片提示词生成和标题生成接口。
所有端点均使用 LLM 服务（通过 PixelleVideoDep 注入）进行内容创作。
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.error_handler import map_exception
from api.dependencies import PixelleVideoDep
from api.schemas.content import (
    NarrationGenerateRequest,
    NarrationGenerateResponse,
    ImagePromptGenerateRequest,
    ImagePromptGenerateResponse,
    TitleGenerateRequest,
    TitleGenerateResponse,
)
from pixelle_video.utils.content_generators import (
    generate_narrations_from_topic,
    generate_image_prompts,
    generate_title,
)

router = APIRouter(prefix="/content", tags=["Content Generation"])


@router.post("/narration", response_model=NarrationGenerateResponse)
async def generate_narration(
    request: NarrationGenerateRequest,
    pixelle_video: PixelleVideoDep
):
    """
    从文本生成旁白

    使用 LLM 将源文本分解为多个旁白段落。

    入参（NarrationGenerateRequest）:
        - **text** (str): 源文本，必填
        - **n_scenes** (int): 生成的旁白数量 (1-20)。默认: 5
        - **min_words** (int): 每个旁白的最小词数 (1-100)。默认: 5
        - **max_words** (int): 每个旁白的最大词数 (1-200)。默认: 20

    Returns:
        NarrationGenerateResponse: 包含字段：
            - narrations (List[str]): 生成的旁白文本列表

    Raises:
        HTTPException 400: ValueError — 参数无效
        HTTPException 500: 内部服务错误 — LLM 调用失败

    Requires:
        - pixelle_video.llm  — 必须已通过 PixelleVideoCore.initialize() 初始化
        - generate_narrations_from_topic — pixelle_video.utils.content_generators 中的工具函数

    Side Effects:
        - 向 LLM API 发送网络请求
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"正在从文本生成 {request.n_scenes} 段旁白")

        # 调用旁白生成工具函数
        narrations = await generate_narrations_from_topic(
            llm_service=pixelle_video.llm,
            topic=request.text,
            n_scenes=request.n_scenes,
            min_words=request.min_words,
            max_words=request.max_words
        )

        return NarrationGenerateResponse(
            narrations=narrations
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "content")


@router.post("/image-prompt", response_model=ImagePromptGenerateResponse)
async def generate_image_prompt(
    request: ImagePromptGenerateRequest,
    pixelle_video: PixelleVideoDep
):
    """
    从旁白列表生成图片提示词

    使用 LLM 为每段旁白创建详细的图片生成提示词。

    入参（ImagePromptGenerateRequest）:
        - **narrations** (List[str]): 旁白文本列表，必填
        - **min_words** (int): 每个提示词的最小词数 (10-100)。默认: 30
        - **max_words** (int): 每个提示词的最大词数 (10-200)。默认: 60

    Returns:
        ImagePromptGenerateResponse: 包含字段：
            - image_prompts (List[str]): 生成的图片提示词列表，与 narrations 一一对应

    Raises:
        HTTPException 400: ValueError — narrations 为空列表
        HTTPException 500: 内部服务错误 — LLM 调用失败

    Requires:
        - pixelle_video.llm  — 必须已初始化
        - generate_image_prompts — pixelle_video.utils.content_generators 中的工具函数

    Side Effects:
        - 向 LLM API 发送网络请求
    """
    try:
        logger.info(f"正在为 {len(request.narrations)} 段旁白生成图片提示词")

        # 调用图片提示词生成工具函数
        image_prompts = await generate_image_prompts(
            llm_service=pixelle_video.llm,
            narrations=request.narrations,
            min_words=request.min_words,
            max_words=request.max_words
        )

        return ImagePromptGenerateResponse(
            image_prompts=image_prompts
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "content")


@router.post("/title", response_model=TitleGenerateResponse)
async def generate_title_endpoint(
    request: TitleGenerateRequest,
    pixelle_video: PixelleVideoDep
):
    """
    从文本生成视频标题

    使用 LLM 为给定内容创建吸引人的标题。

    入参（TitleGenerateRequest）:
        - **text** (str): 源文本/内容描述，必填
        - **style** (str, optional): 标题风格提示。
            如 'engaging'（吸引人）、'formal'（正式）。默认: None

    Returns:
        TitleGenerateResponse: 包含字段：
            - title (str): 生成的标题

    Raises:
        HTTPException 400: ValueError — text 为空
        HTTPException 500: 内部服务错误 — LLM 调用失败

    Requires:
        - pixelle_video.llm  — 必须已初始化
        - generate_title      — pixelle_video.utils.content_generators 中的工具函数

    Side Effects:
        - 向 LLM API 发送网络请求
    """
    try:
        logger.info("正在从文本生成标题")

        # 调用标题生成工具函数
        title = await generate_title(
            llm_service=pixelle_video.llm,
            content=request.text,
            strategy="llm"
        )

        return TitleGenerateResponse(
            title=title
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "content")
