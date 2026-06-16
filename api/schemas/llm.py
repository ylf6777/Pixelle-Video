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
LLM API Schema 模型

定义 LLM 对话接口的请求和响应数据结构。
"""

from typing import Optional
from pydantic import BaseModel, Field


class LLMChatRequest(BaseModel):
    """
    LLM 对话请求模型

    Attributes:
        prompt (str): 用户提示词/问题。必填字段。
            长度无硬性限制，但过长的 prompt 可能导致 token 超出限制。
        temperature (float): 创意度/随机性控制。
            取值范围: 0.0 ~ 2.0。默认: 0.7。
            0.0 = 最确定性（适合事实性问答），2.0 = 最高创意度（适合创意写作）。
        max_tokens (int): 最大响应 token 数。
            取值范围: 1 ~ 32000。默认: 2000。
            "token" 约等于 0.75 个英文单词或 0.5 个中文字。
    """
    prompt: str = Field(..., description="用户提示词")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="创意度 (0.0-2.0)")
    max_tokens: int = Field(2000, ge=1, le=32000, description="最大响应 token 数")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "prompt": "用三句话解释原子习惯的概念",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }


class LLMChatResponse(BaseModel):
    """
    LLM 对话响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        content (str): LLM 生成的响应文本内容。
        tokens_used (Optional[int]): 实际使用的 token 数量。
            当前固定为 None，后续可接入 token 计数功能。
            默认: None
    """
    success: bool = True
    message: str = "Success"
    content: str = Field(..., description="生成的响应文本")
    tokens_used: Optional[int] = Field(None, description="使用的 token 数（如果可用）")
