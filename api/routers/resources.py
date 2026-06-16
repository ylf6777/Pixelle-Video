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
资源发现端点

提供可用工作流、模板和 BGM 的查询接口。
前端通过这些接口动态获取可选项列表，无需硬编码。
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import PixelleVideoDep
from api.schemas.resources import (
    WorkflowInfo,
    WorkflowListResponse,
    TemplateInfo,
    TemplateListResponse,
    BGMInfo,
    BGMListResponse,
)
from pixelle_video.utils.os_util import list_resource_files, get_root_path, get_data_path
from pixelle_video.utils.template_util import get_all_templates_with_info

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.get("/workflows/tts", response_model=WorkflowListResponse)
async def list_tts_workflows(pixelle_video: PixelleVideoDep):
    """
    列出可用 TTS 工作流

    返回来自 RunningHub 和自托管源的所有 TTS 工作流列表。

    Returns:
        WorkflowListResponse: 包含 workflows 列表，每个元素格式::

            {
                "name": "tts_edge.json",
                "display_name": "tts_edge.json - Runninghub",
                "source": "runninghub",
                "path": "workflows/runninghub/tts_edge.json",
                "key": "runninghub/tts_edge.json",
                "workflow_id": "123456"
            }

    Raises:
        HTTPException 500: 服务内部错误 — TTS 服务工作流查询失败

    Requires:
        - pixelle_video.tts        — 必须已初始化。提供 list_workflows() 方法
        - pixelle_video.tts.list_workflows() — 返回所有已注册的工作流信息列表

    Side Effects:
        - 无（查询内存中的工作流注册表）
    """
    try:
        # 从 TTS 服务获取所有工作流
        all_workflows = pixelle_video.tts.list_workflows()

        # 仅筛选文件名以 "tts_" 开头的 TTS 工作流
        tts_workflows = [
            WorkflowInfo(**wf)
            for wf in all_workflows
            if wf["name"].startswith("tts_")
        ]

        return WorkflowListResponse(workflows=tts_workflows)

    except Exception as e:
        logger.error(f"列出 TTS 工作流出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/media", response_model=WorkflowListResponse)
async def list_media_workflows(pixelle_video: PixelleVideoDep):
    """
    列出可用媒体工作流（图片和视频）

    返回来自 RunningHub 和自托管源的所有媒体工作流列表（包括图片和视频）。

    Returns:
        WorkflowListResponse: 包含 workflows 列表，每项包含 name、source、path、key 等字段。

    Raises:
        HTTPException 500: 服务内部错误 — 媒体服务工作流查询失败

    Requires:
        - pixelle_video.media      — 必须已初始化。提供 list_workflows() 方法

    Side Effects:
        - 无（查询内存中的工作流注册表）
    """
    try:
        # 从 media 服务获取所有工作流（包括图片和视频）
        all_workflows = pixelle_video.media.list_workflows()

        media_workflows = [WorkflowInfo(**wf) for wf in all_workflows]

        return WorkflowListResponse(workflows=media_workflows)

    except Exception as e:
        logger.error(f"列出媒体工作流出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 保留旧端点以向后兼容
@router.get("/workflows/image", response_model=WorkflowListResponse)
async def list_image_workflows(pixelle_video: PixelleVideoDep):
    """
    列出可用图片工作流（已弃用，请使用 /workflows/media）

    此端点保留用于向后兼容，仅返回文件名以 "image_" 开头的工作流。

    Returns:
        WorkflowListResponse: 仅包含图片工作流的列表。

    Raises:
        HTTPException 500: 服务内部错误

    Requires:
        - pixelle_video.media      — 必须已初始化

    Side Effects:
        - 无
    """
    try:
        all_workflows = pixelle_video.media.list_workflows()

        # 仅筛选文件名以 "image_" 开头的图片工作流
        image_workflows = [
            WorkflowInfo(**wf)
            for wf in all_workflows
            if wf["name"].startswith("image_")
        ]

        return WorkflowListResponse(workflows=image_workflows)

    except Exception as e:
        logger.error(f"列出图片工作流出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates():
    """
    列出可用视频模板

    返回按尺寸（竖屏/横屏/方形）分组的 HTML 模板列表。
    模板从默认目录（templates/）和自定义目录（data/templates/）合并而来。

    Returns:
        TemplateListResponse: 包含 templates 列表，每项格式::

            {
                "name": "default.html",
                "display_name": "default.html",
                "size": "1080x1920",
                "width": 1080,
                "height": 1920,
                "orientation": "portrait",
                "path": "templates/1080x1920/default.html",
                "key": "1080x1920/default.html"
            }

    Raises:
        HTTPException 500: 服务内部错误 — 模板扫描失败

    Requires:
        - get_all_templates_with_info — pixelle_video.utils.template_util 中的工具函数
        - templates/ 目录             — 项目根目录下的默认模板目录（必须存在）
        - data/templates/ 目录         — 用户自定义模板目录（可选）

    Side Effects:
        - 扫描文件系统中的模板目录（文件 I/O）
    """
    try:
        # 获取所有模板及其信息
        all_templates = get_all_templates_with_info()

        # 转换为 API 响应格式
        templates = []
        for t in all_templates:
            templates.append(TemplateInfo(
                name=t.display_info.name,
                display_name=t.display_info.name,
                size=t.display_info.size,
                width=t.display_info.width,
                height=t.display_info.height,
                orientation=t.display_info.orientation,
                path=t.template_path,
                key=t.template_path
            ))

        return TemplateListResponse(templates=templates)

    except Exception as e:
        logger.error(f"列出模板出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bgm", response_model=BGMListResponse)
async def list_bgm():
    """
    列出可用背景音乐文件

    返回从默认目录（bgm/）和自定义目录（data/bgm/）合并的 BGM 文件列表。
    同名文件以自定义目录中的为准。

    支持的格式: mp3, wav, flac, m4a, aac, ogg

    Returns:
        BGMListResponse: 包含 bgm_files 列表，每项格式::

            {
                "name": "default.mp3",
                "path": "bgm/default.mp3",
                "source": "default"  // 或 "custom"
            }

    Raises:
        HTTPException 500: 服务内部错误 — BGM 目录扫描失败

    Requires:
        - get_root_path("bgm")   — pixelle_video.utils.os_util 中的路径工具函数
        - get_data_path("bgm")    — 同上
        - bgm/ 目录               — 默认 BGM 目录（必须存在）
        - data/bgm/ 目录          — 用户自定义 BGM 目录（可选）

    Side Effects:
        - 扫描文件系统中的 BGM 目录（文件 I/O）
    """
    try:
        # 支持的音频文件扩展名
        audio_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg')

        # 收集 BGM 文件：{filename: {"path": str, "source": str}}
        bgm_files_dict = {}

        # 扫描默认 bgm/ 目录
        default_bgm_dir = Path(get_root_path("bgm"))
        if default_bgm_dir.exists() and default_bgm_dir.is_dir():
            for item in default_bgm_dir.iterdir():
                if item.is_file() and item.suffix.lower() in audio_extensions:
                    bgm_files_dict[item.name] = {
                        "path": f"bgm/{item.name}",
                        "source": "default"
                    }

        # 扫描自定义 data/bgm/ 目录（同名文件覆盖默认）
        custom_bgm_dir = Path(get_data_path("bgm"))
        if custom_bgm_dir.exists() and custom_bgm_dir.is_dir():
            for item in custom_bgm_dir.iterdir():
                if item.is_file() and item.suffix.lower() in audio_extensions:
                    bgm_files_dict[item.name] = {
                        "path": f"data/bgm/{item.name}",
                        "source": "custom"
                    }

        # 转换为响应格式
        bgm_files = [
            BGMInfo(
                name=name,
                path=info["path"],
                source=info["source"]
            )
            for name, info in sorted(bgm_files_dict.items())
        ]

        return BGMListResponse(bgm_files=bgm_files)

    except Exception as e:
        logger.error(f"列出 BGM 出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))
