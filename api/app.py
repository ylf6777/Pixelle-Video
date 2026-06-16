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
ylf_Video FastAPI 应用入口

包含 FastAPI 应用实例、CORS 中间件、路由注册和应用生命周期管理。

启动命令::

    uv run python api/app.py
    uv run python api/app.py --host 0.0.0.0 --port 8080 --reload

"""

import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，确保在开发和打包环境中都能正确导入模块
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import argparse
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 配置文件日志轮转（生产环境）
logger.add(
    "logs/ylf_video_{time:YYYY-MM-DD}.log",
    rotation="00:00",       # 每天午夜轮转
    retention="30 days",    # 保留 30 天
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    encoding="utf-8",
)

from api.config import api_config
from api.tasks import task_manager
from api.dependencies import shutdown_pixelle_video

# 导入所有路由
from api.routers import (
    health_router,
    llm_router,
    tts_router,
    image_router,
    content_router,
    video_router,
    tasks_router,
    files_router,
    resources_router,
    frame_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理器

    管理启动和关闭事件：
    - 启动时：启动任务管理器
    - 关闭时：停止任务管理器并关闭 PixelleVideoCore

    Raises:
        Exception: 如果 task_manager.start() 失败（如内部状态异常）。

    Requires:
        - task_manager          — 全局任务管理器单例（api.tasks.task_manager）
        - shutdown_pixelle_video — 核心服务关闭函数（api.dependencies.shutdown_pixelle_video）

    Side Effects:
        - 启动：task_manager 开始运行，创建清理定时任务
        - 关闭：取消所有正在运行的任务，关闭 ComfyKit 和 Playwright 浏览器
    """
    # 启动阶段
    logger.info("🚀 正在启动 ylf_Video API...")
    await task_manager.start()
    logger.info("✅ ylf_Video API 启动成功\n")

    yield

    # 关闭阶段
    logger.info("🛑 正在关闭 ylf_Video API...")
    await task_manager.stop()
    await shutdown_pixelle_video()
    logger.info("✅ ylf_Video API 关闭完成")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="ylf_Video API",
    description="""
    ## ylf_Video - AI 视频生成平台 API

    ### 功能
    - 🤖 **LLM**: 大语言模型集成
    - 🔊 **TTS**: 文字转语音合成
    - 🎨 **Image**: AI 图片生成
    - 📝 **Content**: 自动化内容生成
    - 🎬 **Video**: 端到端视频生成

    ### 视频生成模式
    - **Sync**: `/api/video/generate/sync` — 适用于小视频（< 30s）
    - **Async**: `/api/video/generate/async` — 适用于大视频，带任务追踪

    ### 快速入门
    1. 健康检查: `GET /health`
    2. 生成旁白: `POST /api/content/narration`
    3. 生成视频: `POST /api/video/generate/sync` 或 `/async`
    4. 追踪任务: `GET /api/tasks/{task_id}`
    """,
    version="0.1.0",
    docs_url=api_config.docs_url,
    redoc_url=api_config.redoc_url,
    openapi_url=api_config.openapi_url,
    lifespan=lifespan,
)

# 添加 CORS 中间件
if api_config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS 已启用，允许来源: {api_config.cors_origins}")

# === 安全中间件 ===
from web_ui.security import (
    ErrorMonitoringMiddleware,
    CSPMiddleware,
    RateLimitMiddleware,
)

app.add_middleware(ErrorMonitoringMiddleware)
app.add_middleware(CSPMiddleware)
app.add_middleware(RateLimitMiddleware)
logger.info("安全中间件已启用: 错误监控 + CSP + 速率限制")

# === 注册路由 ===

# 健康检查（无前缀）
app.include_router(health_router)

# API 路由（统一加上 /api 前缀）
app.include_router(llm_router, prefix=api_config.api_prefix)
app.include_router(tts_router, prefix=api_config.api_prefix)
app.include_router(image_router, prefix=api_config.api_prefix)
app.include_router(content_router, prefix=api_config.api_prefix)
app.include_router(video_router, prefix=api_config.api_prefix)
app.include_router(tasks_router, prefix=api_config.api_prefix)
app.include_router(files_router, prefix=api_config.api_prefix)
app.include_router(resources_router, prefix=api_config.api_prefix)
app.include_router(frame_router, prefix=api_config.api_prefix)

# === Web UI 静态文件和页面路由 ===
from fastapi.staticfiles import StaticFiles
from pathlib import Path as _Path

_web_ui_dir = _Path(__file__).resolve().parent.parent / "web_ui"
if _web_ui_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_web_ui_dir / "static")), name="static")

    from web_ui.routes import router as web_ui_router
    app.include_router(web_ui_router)

    logger.info("Web UI 路由已注册: /, /workflow/*, /history")
else:
    logger.warning("web_ui/ 目录不存在，跳过 Web UI 路由注册")


@app.get("/")
async def root():
    """
    根路由 — 返回 API 概览信息

    Returns:
        dict: 包含服务名、版本号、文档和子路由 URL 的概览字典。
            格式::

                {
                    "service": "ylf_Video API",
                    "version": "0.1.0",
                    "docs": "/docs",
                    "health": "/health",
                    "api": { ... }
                }

    Side Effects:
        - 无（纯查询端点）
    """
    return {
        "service": "ylf_Video API",
        "version": "0.1.0",
        "docs": api_config.docs_url,
        "health": "/health",
        "api": {
            "llm": f"{api_config.api_prefix}/llm",
            "tts": f"{api_config.api_prefix}/tts",
            "image": f"{api_config.api_prefix}/image",
            "content": f"{api_config.api_prefix}/content",
            "video": f"{api_config.api_prefix}/video",
            "tasks": f"{api_config.api_prefix}/tasks",
            "files": f"{api_config.api_prefix}/files",
            "resources": f"{api_config.api_prefix}/resources",
            "frame": f"{api_config.api_prefix}/frame",
        }
    }


if __name__ == "__main__":
    import uvicorn

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="启动 ylf_Video API 服务器")
    parser.add_argument("--host", default="0.0.0.0", help="绑定的主机地址")
    parser.add_argument("--port", type=int, default=8000, help="绑定的端口号")
    parser.add_argument("--reload", action="store_true", help="启用自动重载（开发模式）")

    args = parser.parse_args()

    # 打印启动信息
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    ylf_Video API Server                      ║
╚══════════════════════════════════════════════════════════════╝

正在启动服务器: http://{args.host}:{args.port}
API 文档: http://{args.host}:{args.port}/docs
ReDoc: http://{args.host}:{args.port}/redoc

按 Ctrl+C 停止服务器
""")

    # 启动服务器
    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
