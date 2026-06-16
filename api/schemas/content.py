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
内容生成 API Schema 模型

定义旁白生成、图片提示词生成和标题生成的请求/响应数据结构。
所有内容生成均由 LLM 驱动。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 旁白生成
# ============================================================================

class NarrationGenerateRequest(BaseModel):
    """
    旁白生成请求模型

    使用 LLM 将源文本分解为多个旁白段落。

    Attributes:
        text (str): 源文本/主题。必填。
            如: "原子习惯教导我们微小的改变会随时间累积产生显著结果"
        n_scenes (int): 生成的旁白段落数。
            取值范围: 1 ~ 20。默认: 5。
        min_words (int): 每段旁白的最小词数。
            取值范围: 1 ~ 100。默认: 5。
        max_words (int): 每段旁白的最大词数。
            取值范围: 1 ~ 200。默认: 20。
    """
    text: str = Field(..., description="用于生成旁白的源文本")
    n_scenes: int = Field(5, ge=1, le=20, description="旁白段落数")
    min_words: int = Field(5, ge=1, le=100, description="每段旁白的最小词数")
    max_words: int = Field(20, ge=1, le=200, description="每段旁白的最大词数")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "text": "原子习惯教导我们微小的改变会随时间累积产生显著结果。",
                "n_scenes": 5,
                "min_words": 5,
                "max_words": 20
            }
        }


class NarrationGenerateResponse(BaseModel):
    """
    旁白生成响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        narrations (List[str]): 生成的旁白文本列表。
            列表长度等于请求中的 n_scenes。
    """
    success: bool = True
    message: str = "Success"
    narrations: List[str] = Field(..., description="生成的旁白列表")


# ============================================================================
# 图片提示词生成
# ============================================================================

class ImagePromptGenerateRequest(BaseModel):
    """
    图片提示词生成请求模型

    使用 LLM 为每段旁白生成详细的美术 prompt，用于后续的 AI 图片生成。

    Attributes:
        narrations (List[str]): 旁白文本列表。必填。
            列表长度决定生成的 prompt 数量。
        min_words (int): 每个提示词的最小词数。
            取值范围: 10 ~ 100。默认: 30。
            建议 >= 20 以获得足够详细的美术描述。
        max_words (int): 每个提示词的最大词数。
            取值范围: 10 ~ 200。默认: 60。
    """
    narrations: List[str] = Field(..., description="旁白文本列表")
    min_words: int = Field(30, ge=10, le=100, description="每个提示词的最小词数")
    max_words: int = Field(60, ge=10, le=200, description="每个提示词的最大词数")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "narrations": [
                    "微小的习惯会随时间累积",
                    "专注于系统而非目标"
                ],
                "min_words": 30,
                "max_words": 60
            }
        }


class ImagePromptGenerateResponse(BaseModel):
    """
    图片提示词生成响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        image_prompts (List[str]): 生成的图片提示词列表。
            与请求中的 narrations 一一对应。
    """
    success: bool = True
    message: str = "Success"
    image_prompts: List[str] = Field(..., description="生成的图片提示词列表")


# ============================================================================
# 标题生成
# ============================================================================

class TitleGenerateRequest(BaseModel):
    """
    标题生成请求模型

    使用 LLM 为视频内容创建吸引人的标题。

    Attributes:
        text (str): 视频内容的源文本/描述。必填。
        style (Optional[str]): 标题风格提示。
            如: 'engaging'（吸引人）、'formal'（正式）、'clickbait'（点击诱饵）。
            不指定则由 LLM 自由发挥。默认: None
    """
    text: str = Field(..., description="源文本/内容描述")
    style: Optional[str] = Field(None, description="标题风格（如 'engaging', 'formal'）")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "text": "原子习惯教导我们微小的改变会随时间累积产生显著结果。",
                "style": "engaging"
            }
        }


class TitleGenerateResponse(BaseModel):
    """
    标题生成响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        title (str): 生成的标题文本。
    """
    success: bool = True
    message: str = "Success"
    title: str = Field(..., description="生成的标题")
