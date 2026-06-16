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
帧/模板渲染 API Schema 模型

定义 HTML 模板渲染和参数查询接口的数据结构。
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class FrameRenderRequest(BaseModel):
    """
    帧渲染请求模型

    使用 HTML 模板将文本和图片组合渲染为一张帧图片。

    Attributes:
        template (str): 模板 key。必填。
            如 '1080x1920/default.html'。也支持仅传文件名（使用默认尺寸）。
        title (Optional[str]): 帧标题（显示在模板的标题区域）。
            不提供则模板中标题位置为空。默认: None
        text (str): 帧文本内容（显示在模板的正文区域）。必填。
        image (Optional[str]): 帧中嵌入的图片路径。
            可以是本地文件路径或 URL。默认: None
    """
    template: str = Field(
        ...,
        description="模板 key（如 '1080x1920/default.html'）。也支持仅传文件名。"
    )
    title: Optional[str] = Field(None, description="帧标题（可选）")
    text: str = Field(..., description="帧文本内容")
    image: Optional[str] = Field(None, description="图片路径或 URL（可选）")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "template": "1080x1920/default.html",
                "title": "示例标题",
                "text": "这是帧的示例文本内容。",
                "image": "resources/example.png"
            }
        }


class FrameRenderResponse(BaseModel):
    """
    帧渲染响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        frame_path (str): 生成帧图片的文件路径。
        width (int): 帧宽度（像素）。
        height (int): 帧高度（像素）。
    """
    success: bool = True
    message: str = "Success"
    frame_path: str = Field(..., description="生成帧图片的文件路径")
    width: int = Field(..., description="帧宽度（像素）")
    height: int = Field(..., description="帧高度（像素）")


class TemplateParamConfig(BaseModel):
    """
    单个模板参数的配置模型

    描述模板 HTML 中定义的 {{param:type=default}} 语法解析结果。

    Attributes:
        type (str): 参数类型。
            可选值: 'text', 'number', 'color', 'bool'。
        default (Any): 参数的默认值。
            类型取决于 type：text 为 str，number 为 int/float，
            color 为 hex 字符串（如 '#ff0000'），bool 为 True/False。
        label (str): 参数的显示标签（通常取自参数名）。
    """
    type: str = Field(..., description="参数类型: 'text', 'number', 'color', 'bool'")
    default: Any = Field(..., description="参数的默认值")
    label: str = Field(..., description="参数的显示标签")


class TemplateParamsResponse(BaseModel):
    """
    模板参数查询响应模型

    返回模板的所有可配置参数及其类型和默认值。

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        template (str): 查询的模板路径。
        media_width (int): 模板 meta 标签中定义的媒体宽度（像素）。
        media_height (int): 模板 meta 标签中定义的媒体高度（像素）。
        params (Dict[str, TemplateParamConfig]): 参数名 → 参数配置的映射。
            如果模板中没有定义 {{param:type=default}} 语法，则为空字典。
    """
    success: bool = True
    message: str = "Success"
    template: str = Field(..., description="模板路径")
    media_width: int = Field(..., description="模板 meta 标签定义的媒体宽度")
    media_height: int = Field(..., description="模板 meta 标签定义的媒体高度")
    params: Dict[str, TemplateParamConfig] = Field(
        default_factory=dict,
        description="模板自定义参数。key 为参数名，value 为配置。"
    )
