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
TTS API Schema 模型

定义文字转语音接口的请求和响应数据结构。
"""

from typing import Optional
from pydantic import BaseModel, Field


class TTSSynthesizeRequest(BaseModel):
    """
    TTS 合成请求模型

    Attributes:
        text (str): 需要合成的文本内容。必填。
            长度建议在 2000 字符以内，过长的文本可能导致 API 超时。
        workflow (Optional[str]): TTS 工作流 key。
            格式: 'runninghub/tts_edge.json' 或 'selfhost/tts_edge.json'。
            不指定则使用 config.yaml 中配置的默认 TTS 工作流。
            默认: None
        ref_audio (Optional[str]): 参考音频路径，用于语音克隆。
            可以是本地文件路径或 URL。
            需要工作流支持语音克隆功能（如 tts_index2.json）。
            默认: None
        voice_id (Optional[str]): 已弃用参数，请改用 workflow。
            仅保留用于向后兼容旧版 API 调用。
            默认: None
    """
    text: str = Field(..., description="需要合成的文本")
    workflow: Optional[str] = Field(
        None,
        description="TTS 工作流 key（如 'runninghub/tts_edge.json' 或 'selfhost/tts_edge.json'）。不指定则使用配置的默认工作流。"
    )
    ref_audio: Optional[str] = Field(
        None,
        description="参考音频路径，用于语音克隆（可选）。可以是本地路径或 URL。"
    )
    voice_id: Optional[str] = Field(
        None,
        description="Voice ID（已弃用，请改用 workflow）"
    )

    class Config:
        """Pydantic 模型配置"""
        json_schema_extra = {
            "example": {
                "text": "你好，欢迎使用 Pixelle-Video！",
                "workflow": "runninghub/tts_edge.json",
                "ref_audio": None
            }
        }


class TTSSynthesizeResponse(BaseModel):
    """
    TTS 合成响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        audio_path (str): 生成的音频文件路径。
            格式如: output/20251205_233630_c939/audio_0.wav
        duration (float): 音频时长（秒）。
            通过 get_audio_duration() 从文件元数据获取。
    """
    success: bool = True
    message: str = "Success"
    audio_path: str = Field(..., description="生成的音频文件路径")
    duration: float = Field(..., description="音频时长（秒）")
