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
视频生成 API Schema 模型

定义视频生成接口的请求和响应数据结构。
支持两种模式：同步（sync）和异步（async + task_id）。
"""

from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class VideoGenerateRequest(BaseModel):
    """
    视频生成请求模型

    包含视频生成的完整参数配置，适用于同步和异步两种模式。

    Attributes:
        text (str): 源文本内容。必填。
            在 'generate' 模式下，LLM 会将其分解为多个旁白和场景。
            在 'fixed' 模式下，文本直接作为旁白使用。

        mode (Literal["generate", "fixed"]): 处理模式。
            'generate' — AI 自动生成旁白和图片提示词（适合无预设脚本的场景）
            'fixed'   — 使用 text 内容作为固定旁白（适合已有完整脚本的场景）
            默认: "generate"

        title (Optional[str]): 视频标题。
            不提供则自动生成。默认: None

        n_scenes (Optional[int]): 场景数量。
            仅在 'generate' 模式下生效，'fixed' 模式下忽略。
            取值范围: 1 ~ 20。默认: 5

        tts_workflow (Optional[str]): TTS 工作流 key。
            如 'runninghub/tts_edge.json'。不指定则使用默认工作流。默认: None

        ref_audio (Optional[str]): 参考音频路径（语音克隆用）。默认: None

        voice_id (Optional[str]): 已弃用。请改用 tts_workflow。默认: None

        min_narration_words (int): 旁白最小词数。
            取值范围: 1 ~ 100。默认: 5

        max_narration_words (int): 旁白最大词数。
            取值范围: 1 ~ 200。默认: 20

        min_image_prompt_words (int): 图片提示词最小词数。
            取值范围: 10 ~ 100。默认: 30

        max_image_prompt_words (int): 图片提示词最大词数。
            取值范围: 10 ~ 200。默认: 60

        media_workflow (Optional[str]): 自定义媒体工作流（图片或视频）。
            不指定则使用默认工作流。默认: None

        video_fps (int): 视频帧率。
            取值范围: 15 ~ 60。默认: 30

        frame_template (Optional[str]): HTML 模板路径和尺寸。
            如 '1080x1920/default.html'。必填，因为视频尺寸从模板中自动推断。

        template_params (Optional[Dict[str, Any]]): 模板自定义参数。
            键值对格式，具体可用参数取决于模板。
            通过 GET /api/frame/template/params?template=... 查询可用参数。默认: None

        prompt_prefix (Optional[str]): 图片风格前缀。
            会附加到每个图片提示词前面。默认: None

        bgm_path (Optional[str]): 背景音乐路径。
            如 'bgm/default.mp3' 或 'data/bgm/my_music.mp3'。默认: None

        bgm_volume (float): 背景音乐音量。
            取值范围: 0.0 ~ 1.0（0=静音, 1=原音量）。默认: 0.3
    """

    # === 输入 ===
    text: str = Field(..., description="视频生成的源文本")

    # === 处理模式 ===
    mode: Literal["generate", "fixed"] = Field(
        "generate",
        description="处理模式: 'generate'（AI生成旁白）或 'fixed'（直接使用文本）"
    )

    # === 标题（可选） ===
    title: Optional[str] = Field(None, description="视频标题（不提供则自动生成）")

    # === 基础配置 ===
    n_scenes: Optional[int] = Field(5, ge=1, le=20, description="场景数量（仅在 'generate' 模式下生效）")

    # === TTS 参数 ===
    tts_workflow: Optional[str] = Field(
        None,
        description="TTS 工作流 key（如 'runninghub/tts_edge.json'）。不指定则使用配置的默认工作流。"
    )
    ref_audio: Optional[str] = Field(
        None,
        description="参考音频路径，用于语音克隆（可选）"
    )
    voice_id: Optional[str] = Field(
        None,
        description="（已弃用）TTS 语音 ID，仅用于向后兼容"
    )

    # === LLM 参数 ===
    min_narration_words: int = Field(5, ge=1, le=100, description="旁白最小词数")
    max_narration_words: int = Field(20, ge=1, le=200, description="旁白最大词数")
    min_image_prompt_words: int = Field(30, ge=10, le=100, description="图片提示词最小词数")
    max_image_prompt_words: int = Field(60, ge=10, le=200, description="图片提示词最大词数")

    # === 媒体参数 ===
    # 注意：media_width 和 media_height 从模板 meta 标签自动推断
    media_workflow: Optional[str] = Field(None, description="自定义媒体工作流（图片或视频）")

    # === 视频参数 ===
    video_fps: int = Field(30, ge=15, le=60, description="视频帧率 (FPS)")

    # === 帧模板（决定视频尺寸） ===
    frame_template: Optional[str] = Field(
        None,
        description="HTML 模板路径（如 '1080x1920/default.html'）。视频尺寸从模板自动推断。"
    )

    # === 模板自定义参数 ===
    template_params: Optional[Dict[str, Any]] = Field(
        None,
        description="模板自定义参数。通过 GET /api/frame/template/params?template=... 查询可用参数。"
    )

    # === 图片风格 ===
    prompt_prefix: Optional[str] = Field(None, description="图片风格前缀，附加到每个图片提示词前面")

    # === 背景音乐 ===
    bgm_path: Optional[str] = Field(None, description="背景音乐文件路径")
    bgm_volume: float = Field(0.3, ge=0.0, le=1.0, description="背景音乐音量 (0.0-1.0)")

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "text": "原子习惯教导我们微小的改变会随时间累积产生显著结果。",
                "mode": "generate",
                "n_scenes": 5,
                "frame_template": "1080x1920/image_default.html",
                "template_params": {
                    "accent_color": "#3498db",
                    "background": "https://example.com/custom-bg.jpg"
                },
                "title": "原子习惯的力量"
            }
        }


class VideoGenerateResponse(BaseModel):
    """
    视频生成同步响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        video_url (str): 生成视频的完整访问 URL。
            例如: http://localhost:8000/api/files/20251205_c939/final.mp4
        duration (float): 视频时长（秒）。
        file_size (int): 文件大小（字节）。
            如果文件不存在（极端情况），值为 0。
    """
    success: bool = True
    message: str = "Success"
    video_url: str = Field(..., description="生成视频的访问 URL")
    duration: float = Field(..., description="视频时长（秒）")
    file_size: int = Field(..., description="文件大小（字节）")


class VideoGenerateAsyncResponse(BaseModel):
    """
    视频生成异步响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Task created successfully"
        task_id (str): 任务追踪 ID（UUID v4 格式）。
            客户端可通过 ``GET /api/tasks/{task_id}`` 轮询进度和结果。
    """
    success: bool = True
    message: str = "Task created successfully"
    task_id: str = Field(..., description="任务追踪 ID")
