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
ylf_Video 核心服务包

提供所有原子能力服务的统一入口。

可用服务:
    - LLMService: 大语言模型文本生成
    - TTSService: 文字转语音（本地 Edge-TTS + ComfyUI 工作流）
    - MediaService: 媒体生成（图片 & 视频，基于 ComfyKit）
    - VideoService: 视频合成处理（ffmpeg-python）
    - FrameProcessor: 单帧处理器（TTS → 媒体 → 合成 → 视频片段）
    - PersistenceService: 任务元数据和分镜数据持久化
    - HistoryManager: 历史记录业务逻辑
    - ComfyBaseService: ComfyUI 工作流服务基类

向后兼容:
    - ImageService = MediaService (别名)
"""

from pixelle_video.services.comfy_base_service import ComfyBaseService
from pixelle_video.services.llm_service import LLMService
from pixelle_video.services.tts_service import TTSService
from pixelle_video.services.media import MediaService
from pixelle_video.services.video import VideoService
from pixelle_video.services.frame_processor import FrameProcessor
from pixelle_video.services.persistence import PersistenceService
from pixelle_video.services.history_manager import HistoryManager

ImageService = MediaService  # 向后兼容别名

__all__ = [
    "ComfyBaseService",
    "LLMService",
    "TTSService",
    "MediaService",
    "ImageService",
    "VideoService",
    "FrameProcessor",
    "PersistenceService",
    "HistoryManager",
]
