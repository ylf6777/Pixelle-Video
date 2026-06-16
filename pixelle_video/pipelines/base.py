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
流水线抽象基类

定义所有视频生成流水线的统一接口。每个流水线通过 __call__ 方法执行，
接收输入文本和可选进度回调，返回 VideoGenerationResult。

子类通过 self.core 访问所有核心服务（LLM、TTS、Media 等）。
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable

from loguru import logger

from pixelle_video.models.progress import ProgressEvent
from pixelle_video.models.storyboard import VideoGenerationResult


class BasePipeline(ABC):
    """
    视频生成流水线抽象基类

    所有自定义流水线继承此类，实现 __call__ 方法。
    每个流水线表示一个独立的视频生成工作流。

    设计原则:
        - 流水线之间完全独立，可拥有完全不同的逻辑
        - 通过 self.core 访问所有核心服务
        - 通过 progress_callback 报告进度

    Attributes:
        core: PixelleVideoCore 实例（提供所有服务访问）。
        llm: LLMService 快捷引用。
        tts: TTSService 快捷引用。
        media: MediaService 快捷引用。
        video: VideoService 快捷引用。
        image: media 的别名（向后兼容）。

    Requires:
        - pixelle_video.service.PixelleVideoCore: 核心服务容器。
    """

    def __init__(self, pixelle_video_core):
        """
        初始化流水线

        Args:
            pixelle_video_core: PixelleVideoCore 实例，提供所有核心服务访问。

        Side Effects:
            - 设置 self.core, self.llm, self.tts, self.media, self.video, self.image 属性。
        """
        self.core = pixelle_video_core

        self.llm = pixelle_video_core.llm
        self.tts = pixelle_video_core.tts
        self.media = pixelle_video_core.media
        self.video = pixelle_video_core.video

        self.image = pixelle_video_core.media

    @abstractmethod
    async def __call__(
        self,
        text: str,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        **kwargs
    ) -> VideoGenerationResult:
        """
        执行流水线

        Args:
            text (str): 输入文本（各流水线对含义有不同解释）。
            progress_callback (Optional[Callable]): 进度回调函数，接收 ProgressEvent。
            **kwargs: 流水线特定参数。

        Returns:
            VideoGenerationResult: 包含视频路径和元数据的生成结果。

        Raises:
            由具体流水线实现决定。通常是网络/IO/LLM 相关异常。
        """
        pass

    def _report_progress(
        self,
        callback: Optional[Callable[[ProgressEvent], None]],
        event_type: str,
        progress: float,
        **kwargs
    ) -> None:
        """
        向回调报告进度

        callback 为 None 时仅记录 debug 日志，不报错。

        Args:
            callback (Optional[Callable]): 进度回调函数，None 则跳过。
            event_type (str): 事件类型标识。如 "generating_narrations"。
            progress (float): 进度值（0.0-1.0）。
            **kwargs: 传递给 ProgressEvent 的额外字段（frame_current, frame_total 等）。

        Requires:
            - ProgressEvent: 进度事件模型。

        Side Effects:
            - 调用 callback（如果非 None）。
            - 写入 debug 日志。
        """
        if callback:
            event = ProgressEvent(event_type=event_type, progress=progress, **kwargs)
            callback(event)
            logger.debug(f"Progress: {progress*100:.0f}% - {event_type}")
        else:
            logger.debug(f"Progress: {progress*100:.0f}% - {event_type}")
