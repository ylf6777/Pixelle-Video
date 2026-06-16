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
LLM（大语言模型）端点

提供基于配置的 LLM 服务的文本对话接口。
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.error_handler import map_exception
from api.dependencies import PixelleVideoDep
from api.schemas.llm import LLMChatRequest, LLMChatResponse

router = APIRouter(prefix="/llm", tags=["Basic Services"])


@router.post("/chat", response_model=LLMChatResponse)
async def llm_chat(
    request: LLMChatRequest,
    pixelle_video: PixelleVideoDep
):
    """
    LLM 对话端点

    使用配置的 LLM 生成文本响应。

    入参（LLMChatRequest）:
        - **prompt** (str): 用户提问/提示词，必填
        - **temperature** (float): 创意度 (0.0-2.0)，越低越确定。默认: 0.7
        - **max_tokens** (int): 最大响应长度 (1-32000)。默认: 2000

    Returns:
        LLMChatResponse: 包含以下字段：
            - success (bool): 始终为 True
            - message (str): 始终为 "Success"
            - content (str): LLM 生成的响应文本
            - tokens_used (Optional[int]): 当前固定为 None

    Raises:
        HTTPException 400: ValueError — 参数无效（如 prompt 为空）
        HTTPException 500: 内部服务错误 — LLM 服务调用失败

    Requires:
        - pixelle_video.llm   — 必须已通过 PixelleVideoCore.initialize() 初始化
        - LLM API Key          — 配置中必须包含有效的 API Key

    Side Effects:
        - 向 LLM API 发送网络请求
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"LLM 对话请求: {request.prompt[:50]}...")

        # 调用 LLM 服务
        response = await pixelle_video.llm(
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return LLMChatResponse(
            content=response,
            tokens_used=None  # 可在此添加 token 计数
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "llm")
