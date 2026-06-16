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
图片生成 API Schema 模型

定义 AI 图片生成接口的请求和响应数据结构。
注意：此端点仅支持图片工作流，视频工作流请使用 /api/video。
"""

from typing import Optional
from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    """
    图片生成请求模型

    Attributes:
        prompt (str): 图片生成提示词/描述。必填。
            建议用英文撰写，对 Stable Diffusion/Flux 兼容性更好。
            例如: "A serene mountain landscape at sunset, photorealistic style"
        width (int): 图片宽度（像素）。
            取值范围: 512 ~ 2048。默认: 1024。
            注意：过大的尺寸会显著增加生成时间。
        height (int): 图片高度（像素）。
            取值范围: 512 ~ 2048。默认: 1024。
        workflow (Optional[str]): 自定义工作流文件名。
            如不指定，使用 config.yaml 中配置的默认图片工作流。
            默认: None
    """
    prompt: str = Field(..., description="图片生成提示词")
    width: int = Field(1024, ge=512, le=2048, description="图片宽度（像素）")
    height: int = Field(1024, ge=512, le=2048, description="图片高度（像素）")
    workflow: Optional[str] = Field(None, description="自定义工作流文件名")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "prompt": "宁静的山间日落风景，写实风格",
                "width": 1024,
                "height": 1024
            }
        }


class ImageGenerateResponse(BaseModel):
    """
    图片生成响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        image_path (str): 生成图片的文件路径。
            可通过 /api/files/{path} 访问。
    """
    success: bool = True
    message: str = "Success"
    image_path: str = Field(..., description="生成图片的文件路径")
