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
资源发现 API Schema 模型

定义工作流、模板和 BGM 资源查询接口的数据结构。
前端通过 GET /api/resources/* 接口动态获取可用选项列表。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 工作流
# ============================================================================

class WorkflowInfo(BaseModel):
    """
    工作流信息模型

    描述一个 ComfyUI 工作流文件的元数据。

    Attributes:
        name (str): 工作流文件名。
            如 'tts_edge.json', 'image_flux.json'。
        display_name (str): 前端显示名称，包含来源信息。
            如 'tts_edge.json - Runninghub'。
        source (str): 工作流来源。
            可选值: 'runninghub'（RunningHub 平台）或 'selfhost'（自托管 ComfyUI）。
        path (str): 工作流文件的完整路径。
            如 'workflows/runninghub/tts_edge.json'。
        key (str): 工作流的唯一标识 key。
            格式: '{source}/{name}'，如 'runninghub/tts_edge.json'。
        workflow_id (Optional[str]): RunningHub 平台上的工作流 ID。
            仅当 source='runninghub' 时有值。默认: None
    """
    name: str = Field(..., description="工作流文件名")
    display_name: str = Field(..., description="显示名称（含来源信息）")
    source: str = Field(..., description="来源 (runninghub 或 selfhost)")
    path: str = Field(..., description="工作流文件的完整路径")
    key: str = Field(..., description="工作流唯一标识 key")
    workflow_id: Optional[str] = Field(None, description="RunningHub 工作流 ID（如适用）")


class WorkflowListResponse(BaseModel):
    """
    工作流列表响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        workflows (List[WorkflowInfo]): 可用工作流列表。
    """
    success: bool = True
    message: str = "Success"
    workflows: List[WorkflowInfo] = Field(..., description="可用工作流列表")


# ============================================================================
# 模板
# ============================================================================

class TemplateInfo(BaseModel):
    """
    模板信息模型

    描述一个 HTML 视频模板的元数据。

    Attributes:
        name (str): 模板文件名。
            如 'default.html', 'image_default.html'。
        display_name (str): 前端显示名称。
        size (str): 模板尺寸字符串。
            如 '1080x1920', '1920x1080'。
        width (int): 模板宽度（像素）。
        height (int): 模板高度（像素）。
        orientation (str): 模板方向。
            可选值: 'portrait'（竖屏）, 'landscape'（横屏）, 'square'（方形）。
        path (str): 模板文件的完整路径。
            如 'templates/1080x1920/default.html'。
        key (str): 模板的唯一标识 key。
            格式: '{size}/{name}'，如 '1080x1920/default.html'。
    """
    name: str = Field(..., description="模板文件名")
    display_name: str = Field(..., description="显示名称")
    size: str = Field(..., description="尺寸（如 1080x1920）")
    width: int = Field(..., description="宽度（像素）")
    height: int = Field(..., description="高度（像素）")
    orientation: str = Field(..., description="方向 (portrait/landscape/square)")
    path: str = Field(..., description="模板文件的完整路径")
    key: str = Field(..., description="模板唯一标识 key")


class TemplateListResponse(BaseModel):
    """
    模板列表响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        templates (List[TemplateInfo]): 可用模板列表。
    """
    success: bool = True
    message: str = "Success"
    templates: List[TemplateInfo] = Field(..., description="可用模板列表")


# ============================================================================
# 背景音乐 (BGM)
# ============================================================================

class BGMInfo(BaseModel):
    """
    背景音乐信息模型

    描述一个 BGM 音频文件的元数据。

    Attributes:
        name (str): BGM 文件名。
            如 'default.mp3', 'happy.mp3'。
        path (str): BGM 文件的相对路径。
            如 'bgm/default.mp3' 或 'data/bgm/happy.mp3'。
        source (str): BGM 来源。
            可选值: 'default'（默认内置 BGM）或 'custom'（用户自定义 BGM）。
    """
    name: str = Field(..., description="BGM 文件名")
    path: str = Field(..., description="BGM 文件路径")
    source: str = Field(..., description="来源 (default 或 custom)")


class BGMListResponse(BaseModel):
    """
    BGM 列表响应模型

    Attributes:
        success (bool): 请求是否成功。固定: True
        message (str): 响应消息。固定: "Success"
        bgm_files (List[BGMInfo]): 可用 BGM 文件列表。
    """
    success: bool = True
    message: str = "Success"
    bgm_files: List[BGMInfo] = Field(..., description="可用 BGM 文件列表")
