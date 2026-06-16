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
分镜数据模型

提供视频生成流程中所有结构化数据模型：分镜配置、分镜帧、内容元数据、
完整分镜表和视频生成结果。所有模型均使用 dataclass 实现，确保低开销和
类型安全。

依赖关系：
    StoryboardConfig → StoryboardFrame → Storyboard → VideoGenerationResult
    ContentMetadata 独立，由 Storyboard 可选引用
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class StoryboardConfig:
    """
    分镜配置参数

    包含视频生成流水线的所有配置项：媒体尺寸、TTS 设置、模板选择、
    工作流文件路径等。该对象在流水线初始化时创建，在整个生成周期中不变。

    Attributes:
        media_width (int): 媒体宽度（像素）。必填，无默认值。
        media_height (int): 媒体高度（像素）。必填，无默认值。
        task_id (Optional[str]): 任务隔离 ID。None 时自动生成 UUID。
            用于将同一任务的输出文件隔离到独立目录。
        n_storyboard (int): 分镜帧数量。默认 5。
        min_narration_words (int): 单段旁白最少字数。默认 5。
        max_narration_words (int): 单段旁白最多字数。默认 20。
        min_image_prompt_words (int): 图片提示词最少字数。默认 30。
        max_image_prompt_words (int): 图片提示词最多字数。默认 60。
        video_fps (int): 视频帧率。默认 30。
        tts_inference_mode (str): TTS 推理模式。"local"(Edge-TTS) 或 "comfyui"。默认 "local"。
        voice_id (Optional[str]): Edge-TTS 音色 ID。如 "zh-CN-YunjianNeural"。None 使用中文默认。
        tts_workflow (Optional[str]): ComfyUI TTS 工作流文件名。仅 comfyui 模式生效。None 使用默认。
        tts_speed (Optional[float]): 语速倍率。范围 0.5-2.0。None 使用默认 1.0。
        ref_audio (Optional[str]): 声音克隆参考音频路径。仅 ComfyUI TTS 支持。
        media_workflow (Optional[str]): 媒体生成工作流文件名。None 使用默认。
        api_video_params (Optional[Dict]): 直连 API 视频生成的额外参数。
        frame_template (str): 帧模板路径（含尺寸前缀）。如 "1080x1920/default.html"。
        template_params (Optional[Dict]): 模板自定义参数。如 {"accent_color": "#ff0000"}。
        reference_images (Optional[Dict[int,str]]): 分镜参考图映射。key=帧索引, value=base64 数据 URL。

    Requires:
        - 无外部依赖。纯数据模型。

    Raises:
        - 无。dataclass 无自定义校验。
    """

    media_width: int
    media_height: int

    task_id: Optional[str] = None

    n_storyboard: int = 5
    min_narration_words: int = 5
    max_narration_words: int = 20
    min_image_prompt_words: int = 30
    max_image_prompt_words: int = 60

    video_fps: int = 30

    tts_inference_mode: str = "local"
    voice_id: Optional[str] = None
    tts_workflow: Optional[str] = None
    tts_speed: Optional[float] = None
    ref_audio: Optional[str] = None

    media_workflow: Optional[str] = None
    api_video_params: Optional[Dict[str, Any]] = None

    frame_template: str = "1080x1920/default.html"
    template_params: Optional[Dict[str, Any]] = None

    reference_images: Optional[Dict[int, str]] = None


@dataclass
class StoryboardFrame:
    """
    单个分镜帧

    表示视频中的一个分镜片段。包含叙事文本、媒体生成提示词、
    生成过程中产生的各种文件路径以及帧元数据。

    Attributes:
        index (int): 帧索引（从 0 开始）。
        narration (str): 旁白文本内容。
        image_prompt (str): 媒体生成提示词。静态模板可为 None。
        audio_path (Optional[str]): 旁白音频文件路径。TTS 生成后填充。
        media_type (Optional[str]): 媒体类型。"image" 或 "video"。无媒体则为 None。
        image_path (Optional[str]): 原始图片路径（图片类型时使用）。
        video_path (Optional[str]): 原始视频路径（视频类型时使用）。
        composed_image_path (Optional[str]): 合成后的图片路径（含字幕，图片类型时使用）。
        video_segment_path (Optional[str]): 最终视频片段路径。
        duration (float): 帧时长（秒）。从音频或视频获取。默认 0.0。
        created_at (Optional[datetime]): 创建时间戳。默认当前时间。

    Requires:
        - 无外部依赖。纯数据模型。

    Raises:
        - 无。
    """

    index: int
    narration: str
    image_prompt: str

    audio_path: Optional[str] = None
    media_type: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    composed_image_path: Optional[str] = None
    video_segment_path: Optional[str] = None

    duration: float = 0.0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """
        帧初始化后处理：自动设置创建时间戳

        Side Effects:
            - 修改 self.created_at
        """
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ContentMetadata:
    """
    内容元数据

    描述视频来源内容的元信息，用于视觉展示和旁白生成上下文。

    Attributes:
        title (str): 内容标题。
        author (Optional[str]): 作者/创作者。
        subtitle (Optional[str]): 副标题。
        genre (Optional[str]): 类型/分类。
        summary (Optional[str]): 内容摘要。
        publication_year (Optional[str]): 出版年份。
        cover_url (Optional[str]): 封面/缩略图 URL。

    Requires:
        - 无外部依赖。
    """

    title: str
    author: Optional[str] = None
    subtitle: Optional[str] = None
    genre: Optional[str] = None
    summary: Optional[str] = None
    publication_year: Optional[str] = None
    cover_url: Optional[str] = None


@dataclass
class Storyboard:
    """
    完整分镜表

    包含视频标题、配置、所有帧及最终输出信息。是视频生成流水线的
    核心数据容器，从初始化到完成全程使用。

    Attributes:
        title (str): 视频标题。
        config (StoryboardConfig): 生成配置。
        frames (List[StoryboardFrame]): 分镜帧列表。默认空列表。
        content_metadata (Optional[ContentMetadata]): 内容元数据。
        final_video_path (Optional[str]): 最终视频文件路径。拼接完成后填充。
        total_duration (float): 总时长（秒）。各帧 duration 累加。
        created_at (Optional[datetime]): 创建时间戳。
        completed_at (Optional[datetime]): 完成时间戳。视频拼接完成时填充。

    Requires:
        - 无外部依赖。纯数据容器。

    Side Effects:
        - __post_init__ 自动设置 created_at
    """

    title: str
    config: StoryboardConfig
    frames: List[StoryboardFrame] = field(default_factory=list)

    content_metadata: Optional[ContentMetadata] = None

    final_video_path: Optional[str] = None
    total_duration: float = 0.0

    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        """
        分镜表初始化后处理：自动设置创建时间戳

        Side Effects:
            - 修改 self.created_at
        """
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_completed(self) -> bool:
        """
        检查所有帧是否处理完毕

        Returns:
            bool: 所有帧的 video_segment_path 均非 None 时返回 True。

        Requires:
            - 无外部依赖。纯内存计算。
        """
        return all(
            frame.video_segment_path is not None
            for frame in self.frames
        )

    @property
    def progress(self) -> float:
        """
        计算处理进度

        Returns:
            float: 进度值（0.0-1.0）。已完成帧数除以总帧数。
            无帧时返回 0.0。

        Requires:
            - 无外部依赖。纯内存计算。
        """
        if not self.frames:
            return 0.0
        completed = sum(
            1 for frame in self.frames
            if frame.video_segment_path is not None
        )
        return completed / len(self.frames)


@dataclass
class VideoGenerationResult:
    """
    视频生成结果

    流水线最终输出，包含视频路径、完整分镜表和文件元数据。

    Attributes:
        video_path (str): 最终视频文件的绝对路径。
        storyboard (Storyboard): 完整分镜表（含所有中间产物路径）。
        duration (float): 视频总时长（秒）。
        file_size (int): 文件大小（字节）。
        created_at (datetime): 创建时间戳。默认当前时间。

    Requires:
        - 无外部依赖。
    """

    video_path: str
    storyboard: Storyboard
    duration: float
    file_size: int
    created_at: datetime = field(default_factory=datetime.now)
