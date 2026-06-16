# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""
基于直连 VLM API 的素材分析服务

与 ImageAnalysisService / VideoAnalysisService 保持相同的文本描述契约，
但使用 DashScope 等 VLM API 直连方式，不依赖 ComfyUI 或 RunningHub 工作流。

Requires:
    - pixelle_video.services.api_services.vlm_client.VLM: VLM 客户端。
    - pixelle_video.config.config_manager: API 提供商配置。
    - loguru.logger: 日志记录。

Side Effects:
    - 调用外部 VLM API（网络请求）。
    - 读取本地图片/视频文件。
    - 写入日志（info/error）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger


class APIAssetAnalysisService:
    """
    使用直接 VLM API 提供商分析图片/视频素材的服务

    与 ImageAnalysisService / VideoAnalysisService 保持相同的文本描述契约，
    但使用 DashScope 等 API 直连方式而非 ComfyUI/RunningHub 工作流。
    """

    VLM_MODELS = {
        "dashscope": [
            "qwen3.7-plus",
            "qwen3.6-plus",
            "qwen3.6-flash",
            "qwen3.5-omni-plus",
        ],
    }

    VLM_PROVIDER_LABELS = {
        "dashscope": "DashScope",
    }

    IMAGE_PROMPT = """请分析这张素材图片，用中文给出适合短视频脚本创作的简洁描述。

请重点说明：
1. 画面主体、人物/商品/场景
2. 可用于营销或叙事的关键信息
3. 画面风格、氛围、颜色和构图

输出 2-5 句话，不要编造图片中不存在的信息。"""

    VIDEO_PROMPT = """请分析这个上传的视频素材，用中文概括视频内容。

请重点说明：
1. 视频中的主体、场景和动作变化
2. 可用于短视频脚本的卖点或叙事信息
3. 整体风格、节奏和氛围

输出 3-6 句话，不要编造关键帧中看不到的信息。"""

    def __init__(self, config: dict, core=None):
        """
        初始化 API 素材分析服务

        Args:
            config: 完整应用配置字典
            core: PixelleVideoCore 实例（可选）

        Side Effects:
            保存 config 和 core 引用
        """
        self.config = config
        self.core = core

    def list_models(self, configured_only: bool = True) -> list[dict]:
        """
        列出 API 后端可用的 VLM 模型

        Args:
            configured_only: True 时仅返回已配置 API 密钥的提供商模型

        Returns:
            模型信息字典列表，每个包含 key, name, display_name, source, provider, model 等字段
        """
        providers = self.config.get("api_providers", {}) or {}
        models = []

        for provider, provider_models in self.VLM_MODELS.items():
            provider_config = providers.get(provider, {}) or {}
            if configured_only and not provider_config.get("api_key"):
                continue

            provider_label = self.VLM_PROVIDER_LABELS.get(provider, provider.title())
            for model in provider_models:
                key = f"api/vlm/{provider}/{model}"
                models.append({
                    "key": key,
                    "name": model,
                    "display_name": f"{model} - API {provider_label}",
                    "source": "api",
                    "provider": provider,
                    "model": model,
                    "media_type": "asset_analysis",
                    "ability_type": "vlm_asset_analysis",
                    "ability_types": ["vlm_asset_analysis"],
                })

        return models

    async def analyze_image(
        self,
        image_path: str,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        **_: object,
    ) -> str:
        """
        使用 VLM API 分析图片素材，返回中文描述

        Args:
            image_path: 图片文件路径
            model: VLM 模型 key（None 时使用默认模型）
            prompt: 自定义分析提示词（None 时使用默认 IMAGE_PROMPT）

        Returns:
            图片的中文描述文本

        Raises:
            FileNotFoundError: 图片文件不存在时抛出
            RuntimeError: VLM 返回空描述时抛出
        """
        image_file = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        return await self._query_vlm(
            prompt=prompt or self.IMAGE_PROMPT,
            image_paths=[str(image_file)],
            model=model,
        )

    async def analyze_video(
        self,
        video_path: str,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        **_: object,
    ) -> str:
        """
        使用 VLM API 分析视频素材，返回中文描述

        Args:
            video_path: 视频文件路径
            model: VLM 模型 key（None 时使用默认模型）
            prompt: 自定义分析提示词（None 时使用默认 VIDEO_PROMPT）

        Returns:
            视频的中文描述文本

        Raises:
            FileNotFoundError: 视频文件不存在时抛出
            RuntimeError: VLM 返回空描述时抛出
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        return await self._query_vlm(
            prompt=prompt or self.VIDEO_PROMPT,
            image_paths=[],
            video_paths=[str(video_file)],
            model=model,
        )

    async def __call__(self, asset_path: str, asset_type: Optional[str] = None, **kwargs) -> str:
        """
        统一入口：根据 asset_type 自动路由到 analyze_image 或 analyze_video

        Args:
            asset_path: 素材文件路径
            asset_type: 素材类型（"image" 或 "video"），None 时根据扩展名自动判断
            **kwargs: 传递给 analyze_image/analyze_video 的额外参数

        Returns:
            素材的中文描述文本

        Raises:
            ValueError: 素材类型不支持或无法识别时抛出
        """
        path = Path(asset_path)
        resolved_type = asset_type or self._get_asset_type(path)
        if resolved_type == "image":
            return await self.analyze_image(asset_path, **kwargs)
        if resolved_type == "video":
            return await self.analyze_video(asset_path, **kwargs)
        raise ValueError(f"Unsupported asset type for VLM analysis: {asset_path}")

    async def _query_vlm(
        self,
        prompt: str,
        image_paths: list[str],
        model: Optional[str],
        video_paths: Optional[list[str]] = None,
    ) -> str:
        """
        内部方法：调用 VLM 客户端执行实际的 API 查询

        Args:
            prompt: 分析提示词
            image_paths: 图片文件路径列表
            model: VLM 模型标识符
            video_paths: 视频文件路径列表（可选）

        Returns:
            VLM 返回的描述文本

        Raises:
            RuntimeError: 未选择模型或 VLM 返回空描述时抛出
        """
        from pixelle_video.services.api_services.vlm_client import VLM

        selected_model = (model or "").strip()
        if not selected_model:
            raise RuntimeError(
                "API VLM analysis requires an explicitly selected VLM model. "
                "Please choose one in the asset analysis service settings."
            )

        logger.info(
            f"Analyzing asset via API VLM model={selected_model}, "
            f"images={len(image_paths)}, videos={len(video_paths or [])}"
        )

        providers = self.config.get("api_providers", {}) or {}
        dashscope = providers.get("dashscope", {}) or {}

        client = VLM(
            dashscope_api_key=dashscope.get("api_key"),
            dashscope_base_url=dashscope.get("base_url"),
        )
        result = await asyncio.to_thread(
            client.query,
            prompt,
            image_paths,
            selected_model,
            None,
            video_paths,
        )
        description = str(result or "").strip()
        if not description:
            raise RuntimeError("API VLM analysis returned empty description")
        return description

    def _get_asset_type(self, path: Path) -> str:
        """
        根据文件扩展名判断素材类型

        Args:
            path: 素材文件 Path 对象

        Returns:
            "image"（图片扩展名）、"video"（视频扩展名）或 "unknown"（无法识别）
        """
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        ext = path.suffix.lower()
        if ext in image_exts:
            return "image"
        if ext in video_exts:
            return "video"
        return "unknown"
