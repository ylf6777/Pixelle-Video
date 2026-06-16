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
API Schema 包（Pydantic 数据模型）

集中管理所有 API 请求和响应的 Pydantic 模型定义。
所有模型都用于 FastAPI 的自动请求校验、文档生成和响应序列化。

Schema 清单:
    - base      — 基础响应模型（BaseResponse, ErrorResponse）
    - llm       — LLM 对话请求/响应
    - tts       — TTS 合成请求/响应
    - image     — 图片生成请求/响应
    - content   — 内容生成请求/响应（旁白、图片提示词、标题）
    - video     — 视频生成请求/响应
    - frame     — 帧渲染请求/响应
    - resources — 资源发现响应模型
"""

from api.schemas.base import BaseResponse, ErrorResponse
from api.schemas.llm import LLMChatRequest, LLMChatResponse
from api.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from api.schemas.image import ImageGenerateRequest, ImageGenerateResponse
from api.schemas.content import (
    NarrationGenerateRequest,
    NarrationGenerateResponse,
    ImagePromptGenerateRequest,
    ImagePromptGenerateResponse,
    TitleGenerateRequest,
    TitleGenerateResponse,
)
from api.schemas.video import (
    VideoGenerateRequest,
    VideoGenerateResponse,
    VideoGenerateAsyncResponse,
)

__all__ = [
    # 基础模型
    "BaseResponse",
    "ErrorResponse",
    # LLM
    "LLMChatRequest",
    "LLMChatResponse",
    # TTS
    "TTSSynthesizeRequest",
    "TTSSynthesizeResponse",
    # 图片
    "ImageGenerateRequest",
    "ImageGenerateResponse",
    # 内容生成
    "NarrationGenerateRequest",
    "NarrationGenerateResponse",
    "ImagePromptGenerateRequest",
    "ImagePromptGenerateResponse",
    "TitleGenerateRequest",
    "TitleGenerateResponse",
    # 视频生成
    "VideoGenerateRequest",
    "VideoGenerateResponse",
    "VideoGenerateAsyncResponse",
]
