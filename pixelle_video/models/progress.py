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
进度事件模型

定义视频生成流水线中上报的结构化进度事件，供 UI 层消费和翻译。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProgressEvent:
    """
    视频生成的结构化进度事件

    由流水线通过 progress_callback 回调函数上报，UI 层接收后
    翻译为 i18n 文本并更新进度条。

    Attributes:
        event_type (str): 事件类型标识。如 "generating_narrations", "frame_step",
            "concatenating", "completed"。
        progress (float): 总体进度值。必须介于 0.0 和 1.0 之间。
        frame_current (Optional[int]): 当前帧号（从 1 开始）。仅帧处理事件有值。
        frame_total (Optional[int]): 帧总数。仅帧处理事件有值。
        step (Optional[int]): 帧内步骤号（1=音频, 2=图片, 3=合成, 4=视频）。
            仅帧处理事件有值。
        action (Optional[str]): 帧内动作标识。"audio", "image", "compose", "video"。
        extra_info (Optional[str]): 额外信息文本。如批量进度描述。

    Requires:
        - 无外部依赖。

    Raises:
        ValueError: progress 值不在 [0.0, 1.0] 范围内时，在 __post_init__ 中抛出。

    Examples:
        >>> e = ProgressEvent(event_type="generating_narrations", progress=0.05)
        >>> e = ProgressEvent(
        ...     event_type="frame_step", progress=0.23,
        ...     frame_current=1, frame_total=5, step=1, action="audio"
        ... )
    """

    event_type: str
    progress: float

    frame_current: Optional[int] = None
    frame_total: Optional[int] = None
    step: Optional[int] = None
    action: Optional[str] = None
    extra_info: Optional[str] = None

    def __post_init__(self):
        """
        初始化后校验：确保 progress 值在合法范围内

        Raises:
            ValueError: progress 不在 [0.0, 1.0] 范围内

        Requires:
            - 无外部依赖。

        Side Effects:
            - 无。仅做校验，不修改数据。
        """
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError(
                f"Progress must be between 0.0 and 1.0, got {self.progress}"
            )
