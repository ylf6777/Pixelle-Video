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
API 路由索引模块

集中导入并导出所有路由对象，供 api/app.py 统一注册。

路由清单:
    - health_router      — 健康检查 (/health, /version)
    - llm_router         — LLM 对话 (/api/llm/*)
    - tts_router         — TTS 合成 (/api/tts/*)
    - image_router       — 图片生成 (/api/image/*)
    - content_router     — 内容生成 (/api/content/*)
    - video_router       — 视频生成 (/api/video/*)
    - tasks_router       — 任务管理 (/api/tasks/*)
    - files_router       — 文件服务 (/api/files/*)
    - resources_router   — 资源发现 (/api/resources/*)
    - frame_router       — 帧渲染 (/api/frame/*)
"""

from api.routers.health import router as health_router
from api.routers.llm import router as llm_router
from api.routers.tts import router as tts_router
from api.routers.image import router as image_router
from api.routers.content import router as content_router
from api.routers.video import router as video_router
from api.routers.tasks import router as tasks_router
from api.routers.files import router as files_router
from api.routers.resources import router as resources_router
from api.routers.frame import router as frame_router

__all__ = [
    "health_router",
    "llm_router",
    "tts_router",
    "image_router",
    "content_router",
    "video_router",
    "tasks_router",
    "files_router",
    "resources_router",
    "frame_router",
]
