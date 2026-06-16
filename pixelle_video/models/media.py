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
媒体生成结果模型

定义 ComfyUI 工作流执行后返回的媒体结果结构，同时支持图片和视频输出。
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class MediaResult(BaseModel):
    """
    ComfyUI 工作流执行的媒体生成结果

    同时支持图片和视频输出。通过 media_type 字段区分类型，
    提供 is_image / is_video 属性方便判断。

    Attributes:
        media_type (Literal["image","video"]): 生成的媒体类型。
        url (str): 生成媒体的 URL 或本地文件路径。
        duration (Optional[float]): 视频时长（秒）。图片时为 None。

    Requires:
        - 无外部依赖。纯 Pydantic 数据模型。

    Raises:
        - 无自定义校验。Pydantic 自动校验字段类型。

    Examples:
        >>> r = MediaResult(media_type="image", url="http://example.com/img.png")
        >>> r.is_image
        True
        >>> r = MediaResult(media_type="video", url="/tmp/v.mp4", duration=5.2)
        >>> r.is_video
        True
    """

    media_type: Literal["image", "video"] = Field(
        description="生成的媒体类型：'image'(图片) 或 'video'(视频)"
    )
    url: str = Field(
        description="生成媒体文件的 URL 或本地路径"
    )
    duration: Optional[float] = Field(
        None,
        description="视频时长（秒）。仅 media_type='video' 时有值"
    )

    @property
    def is_image(self) -> bool:
        """
        判断是否为图片结果

        Returns:
            bool: media_type 为 "image" 时返回 True。

        Requires:
            - 无外部依赖。
        """
        return self.media_type == "image"

    @property
    def is_video(self) -> bool:
        """
        判断是否为视频结果

        Returns:
            bool: media_type 为 "video" 时返回 True。

        Requires:
            - 无外部依赖。
        """
        return self.media_type == "video"
