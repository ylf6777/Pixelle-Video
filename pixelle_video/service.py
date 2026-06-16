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
Pixelle-Video 核心服务层（Service Layer）

提供对所有能力的统一访问入口（LLM、TTS、Image、Video 等）。
全局单例 `pixelle_video` 是项目中所有服务的唯一访问点。

架构概览::

    PixelleVideoCore (本类)
      ├── config          — 全局配置（来自 config_manager）
      ├── llm             — 大语言模型服务（直接调用 OpenAI SDK）
      ├── tts             — 文字转语音服务（ComfyKit 工作流）
      ├── media           — 图像/视频生成服务（ComfyKit 工作流）
      ├── api_media       — API 提供商媒体服务（Jimeng/Seedance 等）
      ├── image           — media 的别名，用于向后兼容
      ├── image_analysis  — 图片分析服务
      ├── video_analysis  — 视频分析服务
      ├── api_asset_analysis — API 提供商素材分析服务
      ├── video           — 视频合成服务
      ├── frame_processor — 帧处理器
      ├── persistence     — 持久化服务
      ├── history         — 历史记录管理
      └── pipelines       — 视频生成流水线（standard / custom / asset_based）
"""

import hashlib
import json
from typing import Optional

from loguru import logger
from comfykit import ComfyKit

from pixelle_video.config import config_manager
from pixelle_video.services.llm_service import LLMService
from pixelle_video.services.tts_service import TTSService
from pixelle_video.services.media import MediaService
from pixelle_video.services.api_media import APIProviderMediaService
from pixelle_video.services.image_analysis import ImageAnalysisService
from pixelle_video.services.video_analysis import VideoAnalysisService
from pixelle_video.services.api_asset_analysis import APIAssetAnalysisService
from pixelle_video.services.video import VideoService
from pixelle_video.services.frame_processor import FrameProcessor
from pixelle_video.services.persistence import PersistenceService
from pixelle_video.services.history_manager import HistoryManager
from pixelle_video.pipelines.standard import StandardPipeline
from pixelle_video.pipelines.custom import CustomPipeline
from pixelle_video.pipelines.asset_based import AssetBasedPipeline


class PixelleVideoCore:
    """
    Pixelle-Video 核心服务层

    提供对所有 AI 能力的统一访问入口。
    所有服务在调用 `initialize()` 之前为 None，调用后完成初始化。

    用法::

        from pixelle_video import pixelle_video

        # 初始化
        await pixelle_video.initialize()

        # 直接使用各项能力
        answer = await pixelle_video.llm("解释原子习惯的概念")
        audio = await pixelle_video.tts("你好，世界")
        media = await pixelle_video.media(prompt="一只猫")

        # 检查可用能力
        print(f"使用中的 LLM: {pixelle_video.llm.active}")
        print(f"可用 TTS: {pixelle_video.tts.available}")

    Requires:
        - config.yaml           — 项目根目录配置文件。通过 config_manager 全局单例读取
        - ComfyUI 服务           — ComfyKit 依赖的外部 ComfyUI API，用于 TTS/媒体生成。
                                  通过配置中的 comfyui_url 连接
        - LLM API Key            — OpenAI 兼容 API 密钥，通过配置注入到 LLMService
    """

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化 PixelleVideoCore 实例

        此时仅加载配置并设置占位属性，所有服务在调用 `initialize()` 后才会创建。

        Args:
            config_path (str): 配置文件的路径。
                默认值: "config.yaml"。注意：当前实现中，实际上始终使用全局
                config_manager 单例加载配置，config_path 参数保留但未强制使用。

        Side Effects:
            - 从 config_manager 读取全局配置存入 self.config
            - 将所有服务属性初始化为 None
        """
        # 使用全局 config_manager 单例加载配置
        self.config = config_manager.config.to_dict()
        self._initialized = False

        # ComfyKit 懒加载相关（首次使用时创建，配置变更时重建）
        self._comfykit: Optional[ComfyKit] = None
        self._comfykit_config_hash: Optional[str] = None

        # 核心服务（在 initialize() 中创建）
        self.llm: Optional[LLMService] = None
        self.tts: Optional[TTSService] = None
        self.media: Optional[MediaService] = None
        self.api_media: Optional[APIProviderMediaService] = None
        self.video: Optional[VideoService] = None
        self.frame_processor: Optional[FrameProcessor] = None
        self.persistence: Optional[PersistenceService] = None
        self.history: Optional[HistoryManager] = None

        # 视频生成流水线（dict: pipeline_name → pipeline_instance）
        self.pipelines = {}

        # 默认流水线的可调用包装（向后兼容）
        self.generate_video = None

    def _get_comfykit_config(self) -> dict:
        """
        从 config_manager 获取当前 ComfyKit 配置

        每次调用都会重新加载配置，以支持配置热更新。

        Returns:
            dict: ComfyKit 构造所需的键值对字典。
                包含 comfyui_url、api_key、runninghub_api_key 等字段。
                如果配置中某字段未设置或为空字符串，该键不会出现在返回字典中。

        Side Effects:
            - 从 config_manager 重新加载全局配置到 self.config
        """
        # 从全局 config_manager 重新加载配置（支持热更新）
        self.config = config_manager.config.to_dict()

        comfyui_config = self.config.get("comfyui", {})
        kit_config = {}

        if comfyui_config.get("comfyui_url"):
            kit_config["comfyui_url"] = comfyui_config["comfyui_url"]
        if comfyui_config.get("comfyui_api_key"):
            kit_config["api_key"] = comfyui_config["comfyui_api_key"]
        if comfyui_config.get("runninghub_api_key"):
            kit_config["runninghub_api_key"] = comfyui_config["runninghub_api_key"]
        # 仅当 instance_type 非空时才传入
        instance_type = comfyui_config.get("runninghub_instance_type")
        if instance_type and instance_type.strip():
            kit_config["runninghub_instance_type"] = instance_type

        return kit_config

    def _compute_comfykit_config_hash(self, config: dict) -> str:
        """
        计算 ComfyKit 配置的 MD5 哈希，用于变更检测

        Args:
            config (dict): _get_comfykit_config() 返回的配置字典。

        Returns:
            str: 配置的 MD5 哈希字符串（32 位十六进制）。

        Requires:
            - hashlib: 标准库，无需额外配置。
        """
        # 按键排序以保证哈希一致性
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    async def _get_or_create_comfykit(self) -> ComfyKit:
        """
        获取或创建 ComfyKit 实例（带配置变更检测的懒加载）

        该方法实现的核心逻辑：
        1. 首次使用时创建 ComfyKit（懒加载，不在 initialize 中创建）
        2. 检测到 ComfyUI 配置变更时，自动关闭旧实例并创建新实例
        3. 确保旧实例被正确清理

        Returns:
            ComfyKit: 已就绪的 ComfyKit 实例。

        Raises:
            Exception: 如果 ComfyKit 构造失败（配置中的 URL 不可达或 API Key 无效）。

        Requires:
            - ComfyUI 服务           — 配置中指定的 comfyui_url 必须可达
            - runninghub_api_key    — 如果使用 RunningHub，需要有效的 API Key

        Side Effects:
            - 首次调用时创建 ComfyKit 实例（网络连接）
            - 配置变更时关闭旧实例并创建新实例
            - 更新 self._comfykit 和 self._comfykit_config_hash
        """
        current_config = self._get_comfykit_config()
        current_hash = self._compute_comfykit_config_hash(current_config)

        # 判断是否需要创建或重建 ComfyKit
        if self._comfykit is None or self._comfykit_config_hash != current_hash:
            # 如果存在旧实例，先关闭它
            if self._comfykit is not None:
                logger.info("🔄 ComfyUI 配置已变更，正在重建 ComfyKit 实例...")
                try:
                    await self._comfykit.close()
                except Exception as e:
                    logger.warning(f"关闭旧 ComfyKit 实例失败: {e}")
                self._comfykit = None

            # 使用当前配置创建新实例
            logger.info("✨ 正在创建 ComfyKit 实例...")
            logger.debug(f"ComfyKit 配置: {current_config}")
            self._comfykit = ComfyKit(**current_config)
            self._comfykit_config_hash = current_hash
            logger.info("✅ ComfyKit 实例已创建")

        return self._comfykit

    async def initialize(self):
        """
        初始化所有核心服务

        必须在使用任何能力之前调用。注意：ComfyKit 不会在这里初始化，
        而是在首次使用时通过 _get_or_create_comfykit() 懒加载。

        初始化顺序：
        1. 创建核心服务实例（LLM、TTS、Media 等）
        2. 注册视频生成流水线（standard、custom、asset_based）
        3. 创建默认流水线的可调用包装

        Raises:
            Exception: 如果任何服务初始化失败（LLMService 需要有效的 API 配置）。

        Requires:
            - self.config          — __init__ 中加载的配置字典
            - LLM API Key           — 必须存在于配置中，LLMService 初始化时需要
            - 输出目录 "output"      — PersistenceService 需要此目录存在（会自动创建）

        Side Effects:
            - 创建 LLMService、TTSService 等所有服务实例
            - 注册 pipeline 字典
            - 设置 self._initialized = True
            - 重复调用时记录警告并跳过（幂等操作）

        用法::

            await pixelle_video.initialize()
        """
        if self._initialized:
            logger.warning("Pixelle-Video 已经初始化")
            return

        logger.info("🚀 正在初始化 Pixelle-Video...")

        # 1. 初始化核心服务（ComfyKit 稍后懒加载）
        self.llm = LLMService(self.config)
        self.tts = TTSService(self.config, core=self)
        self.api_media = APIProviderMediaService(self.config, core=self)
        self.media = MediaService(self.config, core=self)
        self.image = self.media  # 向后兼容的别名
        self.image_analysis = ImageAnalysisService(self.config, core=self)
        self.video_analysis = VideoAnalysisService(self.config, core=self)
        self.api_asset_analysis = APIAssetAnalysisService(self.config, core=self)
        self.video = VideoService()
        self.frame_processor = FrameProcessor(self)
        self.persistence = PersistenceService(output_dir="output")
        self.history = HistoryManager(self.persistence)

        # 2. 注册视频生成流水线
        self.pipelines = {
            "standard": StandardPipeline(self),
            "custom": CustomPipeline(self),
            "asset_based": AssetBasedPipeline(self),
        }
        logger.info(f"📹 已注册的流水线: {', '.join(self.pipelines.keys())}")

        # 3. 设置默认流水线的可调用包装（向后兼容）
        self.generate_video = self._create_generate_video_wrapper()

        self._initialized = True
        logger.info("✅ Pixelle-Video 初始化成功\n")

    async def cleanup(self):
        """
        清理资源（关闭 ComfyKit 会话）

        在应用退出时调用，释放 ComfyKit 持有的网络连接等资源。

        Side Effects:
            - 关闭 ComfyKit 实例
            - 重置 self._comfykit 和 self._comfykit_config_hash 为 None
            - 关闭失败时仅记录错误日志，不抛出异常

        用法::

            await pixelle_video.cleanup()
        """
        if self._comfykit:
            logger.info("🧹 正在关闭 ComfyKit 会话...")
            try:
                await self._comfykit.close()
                logger.info("✅ ComfyKit 会话已关闭")
            except Exception as e:
                logger.error(f"关闭 ComfyKit 失败: {e}")
            finally:
                self._comfykit = None
                self._comfykit_config_hash = None

    async def __aenter__(self):
        """
        异步上下文管理器入口

        自动调用 initialize()，支持 ``async with PixelleVideoCore() as core:`` 用法。

        Returns:
            PixelleVideoCore: 当前实例（self）。

        Side Effects:
            - 调用 self.initialize()
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器出口

        自动调用 cleanup()，释放资源。

        Args:
            exc_type: 上下文内发生的异常类型（如果有）。None 表示正常退出。
            exc_val: 异常实例。
            exc_tb: Traceback 对象。

        Side Effects:
            - 调用 self.cleanup()
        """
        await self.cleanup()

    def _create_generate_video_wrapper(self):
        """
        创建 generate_video 的包装函数，支持按名称选择流水线

        详细说明:
            这是一个闭包工厂方法。返回的异步函数 ``generate_video_wrapper``
            会根据 ``pipeline`` 参数查找并调用对应的流水线实例。

            设计原因:
            - ``pixelle_video.generate_video(...)`` 是旧的公开 API
            - 保留这个调用方式以实现向后兼容
            - 内部通过 ``self.pipelines[pipeline]`` 查找已注册的流水线

            闭包捕获的外部变量:
            - ``self`` (PixelleVideoCore): 通过闭包引用，用于访问 self.pipelines 字典

        Returns:
            Callable: 一个异步函数 ``generate_video_wrapper(text, pipeline, **kwargs)``

        Raises:
            ValueError: 当指定的 pipeline 名称在 self.pipelines 中不存在时抛出。

        Side Effects:
            - 无（仅返回一个可调用对象，不执行实际逻辑）

        用法::

            # 使用默认 standard 流水线
            result = await pixelle_video.generate_video(
                text="如何提高学习效率",
                n_scenes=5
            )

            # 使用 custom 流水线
            result = await pixelle_video.generate_video(
                text=your_content,
                pipeline="custom",
                custom_param_example="custom_value"
            )
        """
        async def generate_video_wrapper(
            text: str,
            pipeline: str = "standard",
            **kwargs
        ):
            """
            使用指定流水线生成视频

            Args:
                text (str): 输入文本，作为视频生成的源内容。
                    长度无硬性限制，但过长的文本可能导致 API 超时。
                pipeline (str): 流水线名称。
                    可选值: "standard", "custom", "asset_based"。
                    默认值: "standard"
                **kwargs: 流水线专属参数，透传给对应流水线实例。

            Returns:
                VideoGenerationResult: 视频生成结果对象，包含 video_path、duration 等字段。

            Raises:
                ValueError: 当 ``pipeline`` 不在已注册的流水线列表中时抛出。
                    错误消息会列出所有可用的流水线名称。

            Requires:
                - self.pipelines       — 必须已通过 initialize() 注册流水线

            Side Effects:
                - 调用对应流水线的 __call__ 方法，触发实际的视频生成流程
            """
            if pipeline not in self.pipelines:
                available = ", ".join(self.pipelines.keys())
                raise ValueError(
                    f"未知流水线: '{pipeline}'。"
                    f"可用流水线: {available}"
                )

            pipeline_instance = self.pipelines[pipeline]
            return await pipeline_instance(text=text, **kwargs)

        return generate_video_wrapper

    @property
    def project_name(self) -> str:
        """
        获取项目名称

        Returns:
            str: 配置中的项目名称。如果配置中未设置 project_name，返回默认值
                "Pixelle-Video"。

        Requires:
            - self.config          — 必须已通过 config_manager 加载
        """
        return self.config.get("project_name", "Pixelle-Video")

    def __repr__(self) -> str:
        """
        字符串表示

        Returns:
            str: 格式为 "<PixelleVideoCore project='name' status=s pipelines=[...]>"
                其中 status 为 "initialized" 或 "not initialized"。
        """
        status = "initialized" if self._initialized else "not initialized"
        pipelines = f"pipelines={list(self.pipelines.keys())}" if self._initialized else ""
        return f"<PixelleVideoCore project={self.project_name!r} status={status} {pipelines}>"


# 全局单例 — 项目中所有模块通过此实例访问核心服务
pixelle_video = PixelleVideoCore()
