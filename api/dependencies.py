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
FastAPI 依赖注入模块

提供 PixelleVideoCore 等服务的依赖注入机制。
通过 FastAPI 的 Depends 系统，路由函数可以声明式地获取核心服务实例。

用法::

    from api.dependencies import PixelleVideoDep

    @router.post("/chat")
    async def llm_chat(pixelle_video: PixelleVideoDep):
        result = await pixelle_video.llm(...)
"""

from typing import Annotated
from fastapi import Depends
from loguru import logger

from pixelle_video.service import PixelleVideoCore


# 全局 Pixelle-Video 实例，在 API 进程生命周期内复用
_pixelle_video_instance: PixelleVideoCore = None


async def get_pixelle_video() -> PixelleVideoCore:
    """
    获取 Pixelle-Video 核心实例（用于 FastAPI 依赖注入）

    在 API 进程生命周期内仅初始化一次（单例模式）。
    首次调用时创建实例并调用 initialize()，后续调用直接返回已有实例。

    Returns:
        PixelleVideoCore: 已初始化的核心服务实例。如果初始化失败，
            将抛出对应异常。

    Raises:
        Exception: 可能在首次初始化时抛出，取决于 PixelleVideoCore.initialize()
            内部的服务初始化逻辑。

    Requires:
        - config.yaml            — 项目根目录配置文件。PixelleVideoCore 初始化时需要
        - ComfyUI 服务             — 通过配置中的 comfyui_url 连接
        - LLM API Key             — 配置中的大模型 API 密钥

    Side Effects:
        - 首次调用时创建全局 _pixelle_video_instance 并调用 initialize()
        - 重复调用无副作用（幂等）
    """
    global _pixelle_video_instance

    if _pixelle_video_instance is None:
        _pixelle_video_instance = PixelleVideoCore()
        await _pixelle_video_instance.initialize()
        logger.info("✅ Pixelle-Video 已为 API 初始化完成")

    return _pixelle_video_instance


async def shutdown_pixelle_video():
    """
    关闭 Pixelle-Video 实例并清理所有资源

    在 FastAPI 应用 shutdown 事件中调用。
    清理内容包括：关闭 ComfyKit 会话、关闭 HTML 帧生成器的浏览器实例。

    Side Effects:
        - 调用 _pixelle_video_instance.cleanup() 关闭 ComfyKit
        - 调用 HTMLFrameGenerator.close_browser() 关闭 Playwright 浏览器
        - 重置全局 _pixelle_video_instance 为 None
    """
    global _pixelle_video_instance
    if _pixelle_video_instance:
        logger.info("正在关闭 Pixelle-Video...")
        await _pixelle_video_instance.cleanup()
        _pixelle_video_instance = None

    from pixelle_video.services.frame_html import HTMLFrameGenerator
    await HTMLFrameGenerator.close_browser()


# 依赖注入的类型别名 — 在路由函数签名中使用此类型即可自动注入核心实例
PixelleVideoDep = Annotated[PixelleVideoCore, Depends(get_pixelle_video)]
