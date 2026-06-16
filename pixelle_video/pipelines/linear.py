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
线性视频流水线基类 — 模板方法模式

定义 PipelineContext 状态容器和 LinearVideoPipeline 流程编排器。
所有标准流水线（Standard/Custom/AssetBased）继承此类，重写生命周期方法。

生命周期:
    1. setup_environment    → 创建任务目录
    2. generate_content     → 生成/分割文案
    3. determine_title      → 确定标题
    4. plan_visuals         → 生成图片提示词
    5. initialize_storyboard → 创建 Storyboard 和帧
    6. produce_assets       → 逐帧生成媒体（核心步骤）
    7. post_production      → 视频拼接 + BGM
    8. finalize             → 创建结果对象 + 持久化
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from loguru import logger

from pixelle_video.pipelines.base import BasePipeline
from pixelle_video.models.storyboard import (
    Storyboard, VideoGenerationResult, StoryboardConfig
)
from pixelle_video.models.progress import ProgressEvent


@dataclass
class PipelineContext:
    """
    单次流水线执行的状态容器

    在 LinearVideoPipeline 的 8 个生命周期步骤之间传递，逐步累积数据。
    每个步骤读写此容器的对应字段。

    Attributes:
        input_text (str): 输入文本（主题或固定文案）。
        params (Dict[str,Any]): 流水线参数（来自 **kwargs）。
        progress_callback (Optional[Callable]): 进度回调函数，接收 ProgressEvent。
        task_id (Optional[str]): 任务隔离 ID，setup_environment 中生成。
        task_dir (Optional[str]): 任务输出目录。
        title (Optional[str]): 视频标题。
        narrations (List[str]): 旁白文本列表。
        image_prompts (List[Optional[str]]): 图片/视频提示词列表（与 narrations 等长）。
        config (Optional[StoryboardConfig]): 分镜配置。
        storyboard (Optional[Storyboard]): 完整分镜表。
        final_video_path (Optional[str]): 最终视频文件路径。
        result (Optional[VideoGenerationResult]): 生成结果（finalize 后填充）。

    Requires:
        - 无外部依赖。纯 dataclass 数据容器。
    """

    input_text: str
    params: Dict[str, Any]
    progress_callback: Optional[Callable[[ProgressEvent], None]] = None

    task_id: Optional[str] = None
    task_dir: Optional[str] = None

    title: Optional[str] = None
    narrations: List[str] = field(default_factory=list)

    image_prompts: List[Optional[str]] = field(default_factory=list)

    config: Optional[StoryboardConfig] = None
    storyboard: Optional[Storyboard] = None

    final_video_path: Optional[str] = None
    result: Optional[VideoGenerationResult] = None


class LinearVideoPipeline(BasePipeline):
    """
    线性视频流水线基类 — 模板方法模式

    将视频生成流程编排为 8 个生命周期步骤。子类重写特定步骤以
    定制行为，不必修改整体流程。

    Requires:
        - pixelle_video.pipelines.base.BasePipeline: 基类（提供进度报告）。
        - PipelineContext: 状态容器。

    Side Effects:
        - 各步骤可能产生文件 I/O、网络请求等副作用（由子类实现决定）。
    """

    async def __call__(
        self,
        text: str,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        **kwargs
    ) -> VideoGenerationResult:
        """
        执行流水线（模板方法入口）

        Args:
            text (str): 输入文本（主题或固定文案，含义由子类定义）。
            progress_callback (Optional[Callable]): 进度回调。None 表示不报告进度。
            **kwargs: 传递给 PipelineContext.params 的额外参数。

        Returns:
            VideoGenerationResult: 包含视频路径、分镜表和元数据的结果对象。

        Raises:
            Exception: 任一步骤失败时通过 handle_exception 处理后重新抛出。

        Requires:
            - 子类实现的 8 个生命周期方法。

        Side Effects:
            - 创建 PipelineContext。
            - 依次调用 8 个生命周期步骤，每个步骤可能产生 I/O/网络副作用。
        """
        ctx = PipelineContext(
            input_text=text,
            params=kwargs,
            progress_callback=progress_callback
        )

        try:
            await self.setup_environment(ctx)
            await self.generate_content(ctx)
            await self.determine_title(ctx)
            await self.plan_visuals(ctx)
            await self.initialize_storyboard(ctx)
            await self.produce_assets(ctx)
            await self.post_production(ctx)
            return await self.finalize(ctx)

        except Exception as e:
            await self.handle_exception(ctx, e)
            raise

    # ==================== 生命周期方法 ====================

    async def setup_environment(self, ctx: PipelineContext) -> None:
        """
        步骤 1: 创建任务目录和环境

        子类应在此创建 task_dir、设置 task_id、确定 output_path。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 task_id, task_dir。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def generate_content(self, ctx: PipelineContext) -> None:
        """
        步骤 2: 生成或处理文案/旁白

        子类应在此生成 narrations 列表。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 narrations。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def determine_title(self, ctx: PipelineContext) -> None:
        """
        步骤 3: 确定或生成视频标题

        子类应在此设置 ctx.title。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 title。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def plan_visuals(self, ctx: PipelineContext) -> None:
        """
        步骤 4: 生成媒体提示词或视觉描述

        子类应在此生成 image_prompts 列表。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 image_prompts。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def initialize_storyboard(self, ctx: PipelineContext) -> None:
        """
        步骤 5: 创建 Storyboard 对象和帧

        子类应在此创建 StoryboardConfig 和 Storyboard，建立帧列表。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 config 和 storyboard。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def produce_assets(self, ctx: PipelineContext) -> None:
        """
        步骤 6: 逐帧生成媒体资产（核心步骤）

        子类应在此遍历 storyboard.frames，调用 frame_processor 生成
        音频、图片/视频、合成帧。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应修改 storyboard.frames 和 total_duration。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def post_production(self, ctx: PipelineContext) -> None:
        """
        步骤 7: 视频拼接和后处理

        子类应在此拼接视频片段、添加 BGM。

        Args:
            ctx (PipelineContext): 流水线上下文。子类应写入 final_video_path。

        Requires:
            - 由子类实现。基类为空操作。
        """
        pass

    async def finalize(self, ctx: PipelineContext) -> VideoGenerationResult:
        """
        步骤 8: 创建结果对象并持久化元数据

        Args:
            ctx (PipelineContext): 完整的流水线上下文。

        Returns:
            VideoGenerationResult: 最终生成结果。

        Raises:
            NotImplementedError: 子类必须实现此方法。
        """
        raise NotImplementedError("finalize must be implemented by subclass")

    async def handle_exception(self, ctx: PipelineContext, error: Exception) -> None:
        """
        流水线异常处理

        子类可重写此方法执行清理逻辑。基类仅记录错误日志。

        Args:
            ctx (PipelineContext): 异常发生时的上下文状态。
            error (Exception): 捕获的异常。

        Requires:
            - loguru.logger: 日志记录。

        Side Effects:
            - 写入错误日志。
        """
        logger.error(f"Pipeline execution failed: {error}")
