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
Video generation endpoints

Supports both synchronous and asynchronous video generation.
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
    """从模板中解析媒体尺寸，统一 sync/async 两处调用"""
    from pixelle_video.services.frame_html import HTMLFrameGenerator
    from pixelle_video.utils.template_util import resolve_template_path
    if not frame_template:
        raise ValueError("frame_template is required to determine media size")
    template_path = resolve_template_path(frame_template)
    generator = HTMLFrameGenerator(template_path)
    return generator.get_media_size()


def _build_video_params(request_body, media_width: int, media_height: int) -> dict:
    """从请求体构建 video generation 参数字典，sync/async 共用"""
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
        logger.warning("voice_id parameter is deprecated, please use tts_workflow instead")
        params["voice_id"] = request_body.voice_id
    if request_body.template_params:
        params["template_params"] = request_body.template_params
    return params


def path_to_url(request: Request, file_path: str) -> str:
    """
    Convert file path to accessible URL
    
    Handles both absolute and relative paths, extracting the path relative
    to the output directory for URL construction.
    
    Args:
        request: FastAPI Request object (provides base_url from actual request)
        file_path: Absolute or relative file path
    
    Returns:
        Full URL to access the file
    
    Examples:
        Windows: G:\\...\\output\\20251205_233630_c939\\final.mp4
              -> http://localhost:8000/api/files/20251205_233630_c939/final.mp4
        
        Linux:   /home/user/.../output/20251205_233630_c939/final.mp4
              -> http://localhost:8000/api/files/20251205_233630_c939/final.mp4
        
        Domain:  With domain request -> https://your-domain.com/api/files/...
    """
    from pathlib import Path
    import os
    
    # Normalize path separators to forward slashes first (for cross-platform compatibility)
    file_path = file_path.replace("\\", "/")
    
    # Check if it's an absolute path (works for both Windows and Linux)
    is_absolute = os.path.isabs(file_path) or Path(file_path).is_absolute()
    
    if is_absolute:
        # Find "output" in the path and get everything after it
        # Split by / to work with normalized paths
        parts = file_path.split("/")
        try:
            output_idx = parts.index("output")
            # Get all parts after "output" and join them
            relative_parts = parts[output_idx + 1:]
            file_path = "/".join(relative_parts)
        except ValueError:
            # If "output" not in path, use the filename only
            file_path = Path(file_path).name
    else:
        # If relative path starting with "output/", remove it
        if file_path.startswith("output/"):
            file_path = file_path[7:]  # Remove "output/"
    
    # Build URL using request's base_url (automatically matches the request host)
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/api/files/{file_path}"


@router.post("/generate/sync", response_model=VideoGenerateResponse)
async def generate_video_sync(
    request_body: VideoGenerateRequest,
    pixelle_video: PixelleVideoDep,
    request: Request
):
    """
    Generate video synchronously
    
    This endpoint blocks until video generation is complete.
    Suitable for small videos (< 30 seconds).
    
    **Note**: May timeout for large videos. Use `/generate/async` instead.
    
    Request body includes all video generation parameters.
    See VideoGenerateRequest schema for details.
    
    Returns path to generated video, duration, and file size.
    """
    try:
        logger.info(f"Sync video generation: {request_body.text[:50]}...")
        media_width, media_height = _resolve_media_size(request_body.frame_template)
        video_params = _build_video_params(request_body, media_width, media_height)
        result = await pixelle_video.generate_video(**video_params)
        file_size = os.path.getsize(result.video_path) if os.path.exists(result.video_path) else 0
        video_url = path_to_url(request, result.video_path)
        return VideoGenerateResponse(video_url=video_url, duration=result.duration, file_size=file_size)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Sync video generation error: {e}")
        raise map_exception(e, "video_generate")


@router.post("/generate/async", response_model=VideoGenerateAsyncResponse)
async def generate_video_async(
    request_body: VideoGenerateRequest,
    pixelle_video: PixelleVideoDep,
    request: Request
):
    """
    Generate video asynchronously
    
    Creates a background task for video generation.
    Returns immediately with a task_id for tracking progress.
    
    **Workflow:**
    1. Submit video generation request
    2. Receive task_id in response
    3. Poll `/api/tasks/{task_id}` to check status
    4. When status is "completed", retrieve video from result
    
    Request body includes all video generation parameters.
    See VideoGenerateRequest schema for details.
    
    Returns task_id for tracking progress.
    """
    try:
        logger.info(f"Async video generation: {request_body.text[:50]}...")
        task = task_manager.create_task(
            task_type=TaskType.VIDEO_GENERATION,
            request_params=request_body.model_dump()
        )

        async def execute_video_generation():
            """Execute video generation in background"""
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
        logger.exception(f"Async video generation error: {e}")
        raise map_exception(e, "video_generate")

