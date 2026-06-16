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
视频生成端点

提供同步和异步两种视频生成模式：
- 同步模式（/generate/sync）：阻塞等待，适合小视频（< 30s）
- 异步模式（/generate/async）：立即返回 task_id，通过 /api/tasks 追踪进度
"""

import os
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from api.dependencies import PixelleVideoDep
from api.schemas.video import (
    VideoGenerateRequest,
    VideoGenerateResponse,
    VideoGenerateAsyncResponse,
)
from api.tasks import task_manager, TaskType
from api.error_handler import map_exception

router = APIRouter(prefix="/video", tags=["Video Generation"])


def _resolve_media_size(frame_template: str) -> tuple[int, int]:
    """
    从 HTML 模板中解析媒体尺寸，供 sync/async 两处共用

    解析模板 HTML 中的 meta 标签获取 width 和 height。

    Args:
        frame_template (str): 模板路径，如 '1080x1920/default.html'。

    Returns:
        tuple[int, int]: (width, height) 二元组，单位为像素。

    Raises:
        ValueError: 当 frame_template 为空或 None 时抛出，
            因为无法确定媒体尺寸。

    Requires:
        - HTMLFrameGenerator   — pixelle_video.services.frame_html 中的类
        - resolve_template_path — pixelle_video.utils.template_util 中的工具函数

    Side Effects:
        - 读取 HTML 模板文件（文件 I/O）
        - 创建 HTMLFrameGenerator 实例（临时，方法调用完即释放）
    """
    from pixelle_video.services.frame_html import HTMLFrameGenerator
    from pixelle_video.utils.template_util import resolve_template_path
    if not frame_template:
        raise ValueError("必须指定 frame_template 以确定媒体尺寸")
    template_path = resolve_template_path(frame_template)
    generator = HTMLFrameGenerator(template_path)
    return generator.get_media_size()


def _build_video_params(request_body: VideoGenerateRequest, media_width: int, media_height: int) -> dict:
    """
    从请求体构建视频生成参数字典，sync/async 共用

    Args:
        request_body (VideoGenerateRequest): API 请求体。
        media_width (int): 由模板解析得到的媒体宽度。
        media_height (int): 由模板解析得到的媒体高度。

    Returns:
        dict: 可直接作为 **kwargs 传给 pixelle_video.generate_video() 的参数字典。
            包含 text、mode、n_scenes、tts_workflow、media_workflow 等所有字段。
            可选字段（tts_workflow、ref_audio、template_params）仅在非空时包含。

    Side Effects:
        - 无（纯数据转换函数）
    """
    params = {
        "text": request_body.text,
        "mode": request_body.mode,
        "title": request_body.title,
        "n_scenes": request_body.n_scenes,
        "min_narration_words": request_body.min_narration_words,
        "max_narration_words": request_body.max_narration_words,
        "min_image_prompt_words": request_body.min_image_prompt_words,
        "max_image_prompt_words": request_body.max_image_prompt_words,
        "media_width": media_width,
        "media_height": media_height,
        "media_workflow": request_body.media_workflow,
        "video_fps": request_body.video_fps,
        "frame_template": request_body.frame_template,
        "prompt_prefix": request_body.prompt_prefix,
        "bgm_path": request_body.bgm_path,
        "bgm_volume": request_body.bgm_volume,
    }
    if request_body.tts_workflow:
        params["tts_workflow"] = request_body.tts_workflow
    if request_body.ref_audio:
        params["ref_audio"] = request_body.ref_audio
    if request_body.voice_id:
        logger.warning("voice_id 参数已弃用，请改用 tts_workflow")
        params["voice_id"] = request_body.voice_id
    if request_body.template_params:
        params["template_params"] = request_body.template_params
    return params


def path_to_url(request: Request, file_path: str) -> str:
    """
    将文件路径转换为可访问的 URL

    处理绝对路径和相对路径，提取 output 目录之后的相对路径，
    构造为可通过 /api/files/ 端点访问的完整 URL。

    Args:
        request (Request): FastAPI Request 对象，用于获取 base_url。
        file_path (str): 文件的绝对路径或相对路径。
            绝对路径示例: /home/.../output/20251205_c939/final.mp4
            相对路径示例: output/20251205_c939/final.mp4

    Returns:
        str: 文件的完整访问 URL。
            示例: http://localhost:8000/api/files/20251205_c939/final.mp4

    Raises:
        无 — 异常情况下会降级使用文件名。

    Requires:
        - request.base_url     — FastAPI 自动提供，来源于实际请求的 Host 头

    Side Effects:
        - 无（纯路径处理函数）
    """
    from pathlib import Path
    import os as _os

    # 统一路径分隔符为正斜杠（跨平台兼容）
    file_path = file_path.replace("\\", "/")

    # 判断是否为绝对路径（同时兼容 Windows 和 Linux）
    is_absolute = _os.path.isabs(file_path) or Path(file_path).is_absolute()

    if is_absolute:
        # 在路径中定位 "output" 目录，取其后的相对路径
        parts = file_path.split("/")
        try:
            output_idx = parts.index("output")
            # 获取 "output" 之后的所有部分并拼接
            relative_parts = parts[output_idx + 1:]
            file_path = "/".join(relative_parts)
        except ValueError:
            # 如果路径中不包含 "output"，仅使用文件名
            file_path = Path(file_path).name
    else:
        # 相对路径：去掉开头的 "output/"
        if file_path.startswith("output/"):
            file_path = file_path[7:]  # 移除 "output/"

    # 使用 request 的 base_url 构建 URL（自动匹配请求的 host）
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/api/files/{file_path}"


@router.post("/generate/sync", response_model=VideoGenerateResponse)
async def generate_video_sync(
    request_body: VideoGenerateRequest,
    pixelle_video: PixelleVideoDep,
    request: Request
):
    """
    同步生成视频

    此端点会阻塞直到视频生成完成。适合小视频（< 30 秒）。
    长时间视频可能因超时而失败，请使用 /generate/async 替代。

    入参（VideoGenerateRequest）:
        详见 api/schemas/video.py 的 VideoGenerateRequest 模型。
        关键字段：
        - **text** (str): 源文本，必填
        - **mode** (Literal["generate","fixed"]): 处理模式。默认: "generate"
        - **n_scenes** (int): 场景数量 (1-20)
        - **frame_template** (str): HTML 模板路径，必填
        - **media_workflow** (str, optional): 自定义媒体工作流
        - **tts_workflow** (str, optional): 自定义 TTS 工作流
        - **template_params** (dict, optional): 模板自定义参数

    Returns:
        VideoGenerateResponse: 包含以下字段：
            - video_url (str): 生成视频的访问 URL
            - duration (float): 视频时长（秒）
            - file_size (int): 文件大小（字节）

    Raises:
        HTTPException 400: ``ValueError`` — 参数无效（frame_template 缺失等）
        HTTPException 422: Pydantic 校验失败 — 请求体格式不正确
        HTTPException 500: 内部服务错误 — 视频生成流程失败

    Requires:
        - pixelle_video.generate_video  — 必须已通过 initialize() 注册流水线
        - _resolve_media_size             — 模板尺寸解析（本模块内）
        - _build_video_params             — 参数构建（本模块内）
        - path_to_url                     — 路径转 URL（本模块内）

    Side Effects:
        - 执行完整的视频生成流水线（LLM + TTS + Image + Video）
        - 生成多个中间文件（图片、音频、视频）
        - 向多个外部 API 发送网络请求
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"同步视频生成: {request_body.text[:50]}...")
        media_width, media_height = _resolve_media_size(request_body.frame_template)
        video_params = _build_video_params(request_body, media_width, media_height)
        result = await pixelle_video.generate_video(**video_params)
        file_size = os.path.getsize(result.video_path) if os.path.exists(result.video_path) else 0
        video_url = path_to_url(request, result.video_path)
        return VideoGenerateResponse(video_url=video_url, duration=result.duration, file_size=file_size)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"同步视频生成错误: {e}")
        raise map_exception(e, "video_generate")


@router.post("/generate/async", response_model=VideoGenerateAsyncResponse)
async def generate_video_async(
    request_body: VideoGenerateRequest,
    pixelle_video: PixelleVideoDep,
    request: Request
):
    """
    异步生成视频

    创建后台任务进行视频生成，立即返回 task_id。
    客户端可通过 /api/tasks/{task_id} 轮询进度。

    工作流程:
        1. 提交视频生成请求
        2. 收到响应中的 task_id
        3. 轮询 ``/api/tasks/{task_id}`` 检查状态
        4. 当状态为 "completed" 时，从 result 字段获取视频 URL

    入参（VideoGenerateRequest）:
        与同步接口相同，详见 VideoGenerateRequest 模型。

    Returns:
        VideoGenerateAsyncResponse: 包含以下字段：
            - task_id (str): 用于追踪进度的任务 ID（UUID v4 格式）

    Raises:
        HTTPException 422: Pydantic 校验失败 — 请求体格式不正确
        HTTPException 500: 内部服务错误 — 任务创建失败

    Requires:
        - task_manager          — 全局任务管理器单例（api.tasks.task_manager）
        - pixelle_video.generate_video — 必须已注册流水线

    Side Effects:
        - 在任务管理器中创建新任务记录（内存写入）
        - 启动后台 asyncio 任务执行视频生成
        - 生成完成后将结果写入 task.result
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"异步视频生成: {request_body.text[:50]}...")
        task = task_manager.create_task(
            task_type=TaskType.VIDEO_GENERATION,
            request_params=request_body.model_dump()
        )

        async def execute_video_generation():
            """
            后台执行视频生成

            Returns:
                dict: 包含 video_url、duration、file_size 的结果字典。
                    此结果会被写入 task.result 供客户端查询。
            """
            media_width, media_height = _resolve_media_size(request_body.frame_template)
            video_params = _build_video_params(request_body, media_width, media_height)
            result = await pixelle_video.generate_video(**video_params)
            file_size = os.path.getsize(result.video_path) if os.path.exists(result.video_path) else 0
            video_url = path_to_url(request, result.video_path)
            return {"video_url": video_url, "duration": result.duration, "file_size": file_size}

        await task_manager.execute_task(task_id=task.task_id, coro_func=execute_video_generation)
        return VideoGenerateAsyncResponse(task_id=task.task_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"异步视频生成错误: {e}")
        raise map_exception(e, "video_generate")
