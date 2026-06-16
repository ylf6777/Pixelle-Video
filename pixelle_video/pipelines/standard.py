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
Standard Video Generation Pipeline

Standard workflow for generating short videos from topic or fixed script.
This is the default pipeline for general-purpose video generation.
Refactored to use LinearVideoPipeline (Template Method Pattern).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Literal, List
import asyncio
import shutil

from loguru import logger

from pixelle_video.pipelines.linear import LinearVideoPipeline, PipelineContext
from pixelle_video.models.progress import ProgressEvent
from pixelle_video.models.storyboard import (
    Storyboard,
    StoryboardFrame,
    StoryboardConfig,
    ContentMetadata,
    VideoGenerationResult
)
from pixelle_video.utils.content_generators import (
    generate_title,
    generate_narrations_from_topic,
    split_narration_script,
    generate_image_prompts,
)
from pixelle_video.utils.os_util import (
    create_task_output_dir,
    get_task_final_video_path
)
from pixelle_video.utils.template_util import get_template_type
from pixelle_video.utils.prompt_helper import build_image_prompt
from pixelle_video.services.video import VideoService




class StandardPipeline(LinearVideoPipeline):
    """
    标准视频生成流水线

    从主题或固定脚本生成完整短视频。支持 generate（AI 生成文案）
    和 fixed（使用已有文案）两种模式。

    工作流:
        1. 创建任务目录和运行环境
        2. 生成/分割旁白文案
        3. 确定/生成视频标题
        4. 为每段旁白生成媒体提示词
        5. 创建 Storyboard 和帧
        6. 逐帧处理（TTS → 媒体生成 → 帧合成 → 视频片段）
        7. 拼接视频 + 添加 BGM
        8. 持久化结果

    Requires:
        - pixelle_video.utils.content_generators: generate_title, generate_narrations_from_topic,
          split_narration_script, generate_image_prompts。
        - pixelle_video.utils.os_util: create_task_output_dir, get_task_final_video_path。
        - pixelle_video.utils.template_util: get_template_type。
        - pixelle_video.utils.prompt_helper: build_image_prompt。
        - pixelle_video.services.video.VideoService: 视频拼接和 BGM。

    Side Effects:
        - 创建 output/{task_id}/ 目录及所有中间文件。
        - 调用 LLM API（生成文案/标题/提示词）。
        - 调用 ComfyUI/API 生成媒体。
        - 调用 TTS 生成音频。
        - 写入日志。
    """

    # ==================== 生命周期方法 ====================

    async def setup_environment(self, ctx: PipelineContext):
        """
        步骤 1: 创建任务输出目录和环境

        Args:
            ctx (PipelineContext): 流水线上下文。写入 task_id, task_dir, final_video_path。

        Requires:
            - create_task_output_dir: 创建隔离的任务目录。
            - get_task_final_video_path: 确定最终视频路径。

        Side Effects:
            - 在 output/ 下创建任务目录。
            - 写入日志（info）。
        """
        text = ctx.input_text
        mode = ctx.params.get("mode", "generate")
        
        logger.info(f"🚀 Starting StandardPipeline in '{mode}' mode")
        logger.info(f"   Text length: {len(text)} chars")
        
        # Create isolated task directory
        task_dir, task_id = create_task_output_dir()
        ctx.task_id = task_id
        ctx.task_dir = task_dir
        
        logger.info(f"📁 Task directory created: {task_dir}")
        logger.info(f"   Task ID: {task_id}")
        
        # Determine final video path
        output_path = ctx.params.get("output_path")
        if output_path is None:
            ctx.final_video_path = get_task_final_video_path(task_id)
        else:
            # We will copy to this path in finalize/post_production
            # For internal processing, we still use the task dir path? 
            # Actually StandardPipeline logic used get_task_final_video_path as the target for concat
            # and then copied. Let's stick to that.
            ctx.final_video_path = get_task_final_video_path(task_id)
            logger.info(f"   Will copy final video to: {output_path}")

    async def generate_content(self, ctx: PipelineContext):
        """
        步骤 2: 生成或分割旁白文案

        generate 模式: LLM 根据主题自动生成旁白。
        fixed 模式: 按指定方式（段落/行/句子）分割已有脚本。

        Args:
            ctx (PipelineContext): 写入 narrations 列表。

        Requires:
            - generate_narrations_from_topic: LLM 生成旁白（generate 模式）。
            - split_narration_script: 脚本分割（fixed 模式）。
            - self.llm: LLMService 实例（generate 模式使用）。

        Side Effects:
            - 调用 LLM API（generate 模式）。
            - 写入日志（info）。
        """
        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text
        n_scenes = ctx.params.get("n_scenes", 5)
        min_words = ctx.params.get("min_narration_words", 5)
        max_words = ctx.params.get("max_narration_words", 20)
        
        if mode == "generate":
            self._report_progress(ctx.progress_callback, "generating_narrations", 0.05)
            ctx.narrations = await generate_narrations_from_topic(
                self.llm,
                topic=text,
                n_scenes=n_scenes,
                min_words=min_words,
                max_words=max_words
            )
            logger.info(f"✅ Generated {len(ctx.narrations)} narrations")
        else:  # fixed
            self._report_progress(ctx.progress_callback, "splitting_script", 0.05)
            split_mode = ctx.params.get("split_mode", "paragraph")
            ctx.narrations = await split_narration_script(text, split_mode=split_mode)
            logger.info(f"✅ Split script into {len(ctx.narrations)} segments (mode={split_mode})")
            logger.info(f"   Note: n_scenes={n_scenes} is ignored in fixed mode")

    async def determine_title(self, ctx: PipelineContext):
        """
        步骤 3: 确定或生成视频标题

        优先使用用户指定的标题，否则调用 LLM 自动生成。

        Args:
            ctx (PipelineContext): 写入 title。

        Requires:
            - generate_title: 标题生成函数（策略: auto 或 llm）。
            - self.llm: LLMService 实例。

        Side Effects:
            - 可能调用 LLM API。
            - 写入日志（info）。
        """
        
        title = ctx.params.get("title")
        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text
        
        if title:
            ctx.title = title
            logger.info(f"   Title: '{title}' (user-specified)")
        else:
            self._report_progress(ctx.progress_callback, "generating_title", 0.01)
            if mode == "generate":
                ctx.title = await generate_title(self.llm, text, strategy="auto")
                logger.info(f"   Title: '{ctx.title}' (auto-generated)")
            else:  # fixed
                ctx.title = await generate_title(self.llm, text, strategy="llm")
                logger.info(f"   Title: '{ctx.title}' (LLM-generated)")

    async def plan_visuals(self, ctx: PipelineContext):
        """
        步骤 4: 生成媒体提示词

        检测模板类型决定是否需要媒体生成。静态模板跳过此步骤（节省 LLM 调用和成本）。
        支持「画面|旁白」格式的直接拆分，无需调用 LLM。

        Args:
            ctx (PipelineContext): 写入 image_prompts 列表（静态模板时为全 None）。

        Requires:
            - get_template_type: 解析模板类型（image/video/static）。
            - build_image_prompt: 拼合前缀和基础提示词。
            - generate_image_prompts: LLM 批量为旁白生成图片提示词。
            - self.core.config: 读取 comfyui.image.prompt_prefix。

        Side Effects:
            - 可能调用 LLM API（非静态模板）。
            - 临时覆盖和恢复 prompt_prefix 配置。
            - 写入日志（info）。
        """
        # Detect template type to determine if media generation is needed
        frame_template = ctx.params.get("frame_template") or "1080x1920/default.html"
        
        template_name = Path(frame_template).name
        template_type = get_template_type(template_name)
        template_requires_media = (template_type in ["image", "video"])
        
        if template_type == "image":
            logger.info(f"📸 Template requires image generation")
        elif template_type == "video":
            logger.info(f"🎬 Template requires video generation")
        else:  # static
            logger.info(f"⚡ Static template - skipping media generation pipeline")
            logger.info(f"   💡 Benefits: Faster generation + Lower cost + No ComfyUI dependency")
        
        # Only generate image prompts if template requires media
        if template_requires_media:
            self._report_progress(ctx.progress_callback, "generating_image_prompts", 0.15)
            
            prompt_prefix = ctx.params.get("prompt_prefix")
            min_words = ctx.params.get("min_image_prompt_words", 30)
            max_words = ctx.params.get("max_image_prompt_words", 60)
            
            # Override prompt_prefix if provided
            original_prefix = None
            if prompt_prefix is not None:
                image_config = self.core.config.get("comfyui", {}).get("image", {})
                original_prefix = image_config.get("prompt_prefix")
                image_config["prompt_prefix"] = prompt_prefix
                logger.info(f"Using custom prompt_prefix: '{prompt_prefix}'")
            
            try:
                # Create progress callback wrapper for image prompt generation
                def image_prompt_progress(completed: int, total: int, message: str):
                    batch_progress = completed / total if total > 0 else 0
                    overall_progress = 0.15 + (batch_progress * 0.15)
                    self._report_progress(
                        ctx.progress_callback,
                        "generating_image_prompts",
                        overall_progress,
                        extra_info=message
                    )
                
                # 检测「画面|旁白」格式，有则直接拆分，不调LLM
                if all('|' in n for n in ctx.narrations):
                    image_parts, narration_parts = [], []
                    for n in ctx.narrations:
                        parts = n.split('|', 1)
                        image_parts.append(parts[0].strip())
                        narration_parts.append(parts[1].strip() if len(parts) > 1 else parts[0].strip())
                    ctx.narrations = narration_parts
                    base_image_prompts = image_parts
                else:
                    base_image_prompts = await generate_image_prompts(
                    self.llm,
                    narrations=ctx.narrations,
                    min_words=min_words,
                    max_words=max_words,
                    progress_callback=image_prompt_progress
                )
                
                # Apply prompt prefix
                image_config = self.core.config.get("comfyui", {}).get("image", {})
                prompt_prefix_to_use = prompt_prefix if prompt_prefix is not None else image_config.get("prompt_prefix", "")
                
                ctx.image_prompts = []
                for base_prompt in base_image_prompts:
                    final_prompt = build_image_prompt(base_prompt, prompt_prefix_to_use)
                    ctx.image_prompts.append(final_prompt)
                
            finally:
                # Restore original prompt_prefix
                if original_prefix is not None:
                    image_config["prompt_prefix"] = original_prefix
            
            logger.info(f"✅ Generated {len(ctx.image_prompts)} image prompts")
        else:
            # Static template - skip image prompt generation entirely
            ctx.image_prompts = [None] * len(ctx.narrations)
            logger.info(f"⚡ Skipped image prompt generation (static template)")
            logger.info(f"   💡 Savings: {len(ctx.narrations)} LLM calls + {len(ctx.narrations)} media generations")

    async def initialize_storyboard(self, ctx: PipelineContext):
        """
        步骤 5: 创建 Storyboard 和帧

        处理 TTS 参数的 old/new API 兼容，创建 StoryboardConfig 和 Storyboard，
        为每个旁白建立对应的 StoryboardFrame。

        Args:
            ctx (PipelineContext): 写入 config 和 storyboard。

        Requires:
            - StoryboardConfig, Storyboard, StoryboardFrame: Pydantic 模型。

        Side Effects:
            - 创建 Python 对象（无 I/O）。
            - 写入日志（debug）。
        """
        # === 处理 TTS 参数的 old/new API 兼容 ===
        tts_inference_mode = ctx.params.get("tts_inference_mode")
        tts_voice = ctx.params.get("tts_voice")
        voice_id = ctx.params.get("voice_id")
        tts_workflow = ctx.params.get("tts_workflow")
        
        final_voice_id = None
        final_tts_workflow = tts_workflow
        
        if tts_inference_mode:
            # New API from web UI
            if tts_inference_mode == "local":
                final_voice_id = tts_voice or "zh-CN-YunjianNeural"
                final_tts_workflow = None
                logger.debug(f"TTS Mode: local (voice={final_voice_id})")
            elif tts_inference_mode == "comfyui":
                final_voice_id = None
                logger.debug(f"TTS Mode: comfyui (workflow={final_tts_workflow})")
        else:
            # Old API
            final_voice_id = voice_id or tts_voice or "zh-CN-YunjianNeural"
            logger.debug(f"TTS Mode: legacy (voice_id={final_voice_id}, workflow={final_tts_workflow})")
            
        # Create config
        ctx.config = StoryboardConfig(
            task_id=ctx.task_id,
            n_storyboard=len(ctx.narrations), # Use actual length
            min_narration_words=ctx.params.get("min_narration_words", 5),
            max_narration_words=ctx.params.get("max_narration_words", 20),
            min_image_prompt_words=ctx.params.get("min_image_prompt_words", 30),
            max_image_prompt_words=ctx.params.get("max_image_prompt_words", 60),
            video_fps=ctx.params.get("video_fps", 30),
            tts_inference_mode=tts_inference_mode or "local",
            voice_id=final_voice_id,
            tts_workflow=final_tts_workflow,
            tts_speed=ctx.params.get("tts_speed", 1.2),
            ref_audio=ctx.params.get("ref_audio"),
            media_width=ctx.params.get("media_width"),
            media_height=ctx.params.get("media_height"),
            media_workflow=ctx.params.get("media_workflow"),
            api_video_params=ctx.params.get("api_video_params"),
            frame_template=ctx.params.get("frame_template") or "1080x1920/default.html",
            template_params=ctx.params.get("template_params"),
            reference_images=ctx.params.get("reference_images")
        )
        
        # Create storyboard
        ctx.storyboard = Storyboard(
            title=ctx.title,
            config=ctx.config,
            content_metadata=ctx.params.get("content_metadata"),
            created_at=datetime.now()
        )
        
        # Create frames
        for i, (narration, image_prompt) in enumerate(zip(ctx.narrations, ctx.image_prompts)):
            frame = StoryboardFrame(
                index=i,
                narration=narration,
                image_prompt=image_prompt,
                created_at=datetime.now()
            )
            ctx.storyboard.frames.append(frame)

    async def produce_assets(self, ctx: PipelineContext):
        """
        步骤 6: 逐帧生成媒体资产（核心处理步骤）

        RunningHub 工作流支持并行处理（使用 asyncio.Semaphore 控制并发）。
        非 RunningHub 工作流串行处理。

        Args:
            ctx (PipelineContext): 读取 storyboard.frames，修改每个帧。

        Requires:
            - self.core.frame_processor: FrameProcessor 实例（调用 TTS→媒体→合成）。
            - pixelle_video.config.config_manager: 读取 RunningHub 并发限制。

        Side Effects:
            - 逐帧调用 TTS、媒体生成、帧合成（重大 I/O 和网络开销）。
            - 修改 storyboard.frames 和 total_duration。
            - 写入进度日志和进度回调。
        """
        storyboard = ctx.storyboard
        config = ctx.config
        
        # Check if using RunningHub workflows for parallel processing
        is_runninghub = (
            (config.tts_workflow and config.tts_workflow.startswith("runninghub/")) or
            (config.media_workflow and config.media_workflow.startswith("runninghub/"))
        )
        
        # Get concurrent limit from config_manager (supports hot reload without restart)
        from pixelle_video.config import config_manager
        runninghub_concurrent_limit = config_manager.config.comfyui.runninghub_concurrent_limit or 1
        
        if is_runninghub and runninghub_concurrent_limit > 1:
            logger.info(f"🚀 Using parallel processing for RunningHub workflows (max {runninghub_concurrent_limit} concurrent)")
            
            semaphore = asyncio.Semaphore(runninghub_concurrent_limit)
            completed_count = 0
            
            async def process_frame_with_semaphore(i: int, frame: StoryboardFrame):
                nonlocal completed_count
                async with semaphore:
                    base_progress = 0.2
                    frame_range = 0.6
                    per_frame_progress = frame_range / len(storyboard.frames)
                    
                    # Create frame-specific progress callback
                    def frame_progress_callback(event: ProgressEvent):
                        overall_progress = base_progress + (per_frame_progress * completed_count) + (per_frame_progress * event.progress)
                        if ctx.progress_callback:
                            adjusted_event = ProgressEvent(
                                event_type=event.event_type,
                                progress=overall_progress,
                                frame_current=i+1,
                                frame_total=len(storyboard.frames),
                                step=event.step,
                                action=event.action
                            )
                            ctx.progress_callback(adjusted_event)
                    
                    # Report frame start
                    self._report_progress(
                        ctx.progress_callback,
                        "processing_frame",
                        base_progress + (per_frame_progress * completed_count),
                        frame_current=i+1,
                        frame_total=len(storyboard.frames)
                    )
                    
                    processed_frame = await self.core.frame_processor(
                        frame=frame,
                        storyboard=storyboard,
                        config=config,
                        total_frames=len(storyboard.frames),
                        progress_callback=frame_progress_callback
                    )
                    
                    completed_count += 1
                    logger.info(f"✅ Frame {i+1} completed ({processed_frame.duration:.2f}s) [{completed_count}/{len(storyboard.frames)}]")
                    return i, processed_frame
            
            # Create all tasks and execute in parallel
            tasks = [process_frame_with_semaphore(i, frame) for i, frame in enumerate(storyboard.frames)]
            results = await asyncio.gather(*tasks)
            
            # Update frames in order and calculate total duration
            for idx, processed_frame in sorted(results, key=lambda x: x[0]):
                storyboard.frames[idx] = processed_frame
                storyboard.total_duration += processed_frame.duration
            
            logger.info(f"✅ All frames processed in parallel (total duration: {storyboard.total_duration:.2f}s)")
        else:
            # Serial processing for non-RunningHub workflows
            logger.info("⚙️ Using serial processing (non-RunningHub workflow)")
            
            for i, frame in enumerate(storyboard.frames):
                base_progress = 0.2
                frame_range = 0.6
                per_frame_progress = frame_range / len(storyboard.frames)
                
                # Create frame-specific progress callback
                def frame_progress_callback(event: ProgressEvent):
                    overall_progress = base_progress + (per_frame_progress * i) + (per_frame_progress * event.progress)
                    if ctx.progress_callback:
                        adjusted_event = ProgressEvent(
                            event_type=event.event_type,
                            progress=overall_progress,
                            frame_current=event.frame_current,
                            frame_total=event.frame_total,
                            step=event.step,
                            action=event.action
                        )
                        ctx.progress_callback(adjusted_event)
                
                # Report frame start
                self._report_progress(
                    ctx.progress_callback,
                    "processing_frame",
                    base_progress + (per_frame_progress * i),
                    frame_current=i+1,
                    frame_total=len(storyboard.frames)
                )
                
                processed_frame = await self.core.frame_processor(
                    frame=frame,
                    storyboard=storyboard,
                    config=config,
                    total_frames=len(storyboard.frames),
                    progress_callback=frame_progress_callback
                )
                storyboard.total_duration += processed_frame.duration
                logger.info(f"✅ Frame {i+1} completed ({processed_frame.duration:.2f}s)")

    async def post_production(self, ctx: PipelineContext):
        """
        步骤 7: 拼接视频并添加背景音乐

        使用 ffmpeg concat demuxer 拼接所有帧视频片段，可选添加 BGM。

        Args:
            ctx (PipelineContext): 读取 storyboard.frames 的 video_segment_path，
                写入 final_video_path。

        Requires:
            - VideoService.concat_videos: ffmpeg 拼接 + BGM 混音。
            - shutil.copy2: 复制到用户指定路径。

        Side Effects:
            - 调用 ffmpeg（外部进程）。
            - 写入最终视频文件。
            - 可能复制文件到用户指定路径。
        """
        self._report_progress(ctx.progress_callback, "concatenating", 0.85)
        
        storyboard = ctx.storyboard
        segment_paths = [frame.video_segment_path for frame in storyboard.frames]
        
        video_service = VideoService()
        
        final_video_path = video_service.concat_videos(
            videos=segment_paths,
            output=ctx.final_video_path,
            bgm_path=ctx.params.get("bgm_path"),
            bgm_volume=ctx.params.get("bgm_volume", 0.2),
            bgm_mode=ctx.params.get("bgm_mode", "loop")
        )
        
        storyboard.final_video_path = final_video_path
        storyboard.completed_at = datetime.now()
        
        # Copy to user-specified path if provided
        user_specified_output = ctx.params.get("output_path")
        if user_specified_output:
            Path(user_specified_output).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_video_path, user_specified_output)
            logger.info(f"📹 Final video copied to: {user_specified_output}")
            ctx.final_video_path = user_specified_output
            storyboard.final_video_path = user_specified_output
        
        logger.success(f"🎬 Video generation completed: {ctx.final_video_path}")

    async def finalize(self, ctx: PipelineContext) -> VideoGenerationResult:
        """
        步骤 8: 创建结果对象并持久化元数据

        Args:
            ctx (PipelineContext): 包含完整的流水线状态。

        Returns:
            VideoGenerationResult: 视频路径、分镜表、时长、文件大小。

        Requires:
            - VideoGenerationResult: 结果模型。
            - self._persist_task_data: 保存元数据和分镜到磁盘。

        Side Effects:
            - 读取视频文件获取文件大小。
            - 调用 _persist_task_data 写入 output/ 目录。
            - 写入日志（info）。
        """
        self._report_progress(ctx.progress_callback, "completed", 1.0)
        
        video_path_obj = Path(ctx.final_video_path)
        file_size = video_path_obj.stat().st_size
        
        result = VideoGenerationResult(
            video_path=ctx.final_video_path,
            storyboard=ctx.storyboard,
            duration=ctx.storyboard.total_duration,
            file_size=file_size
        )
        
        ctx.result = result
        
        logger.info(f"✅ Generated video: {ctx.final_video_path}")
        logger.info(f"   Duration: {ctx.storyboard.total_duration:.2f}s")
        logger.info(f"   Size: {file_size / (1024*1024):.2f} MB")
        logger.info(f"   Frames: {len(ctx.storyboard.frames)}")
        
        # Persist metadata
        await self._persist_task_data(ctx)
        
        return result

    async def _persist_task_data(self, ctx: PipelineContext):
        """
        持久化任务元数据和分镜数据到文件系统

        构建 metadata.json 和保存 Storyboard，失败不影响视频生成结果。

        Args:
            ctx (PipelineContext): 包含完整流水线状态。

        Requires:
            - self.core.persistence.save_task_metadata: 写入 metadata.json。
            - self.core.persistence.save_storyboard: 写入 storyboard.json。
            - self.core.config: 读取 LLM/ComfyUI 配置信息。

        Raises:
            - 不抛出。持久化失败仅记录错误日志，不阻断流程。

        Side Effects:
            - 写入 output/{task_id}/metadata.json 和 storyboard.json。
            - 写入日志（info/warning/error）。
        """
        try:
            storyboard = ctx.storyboard
            result = ctx.result
            task_id = storyboard.config.task_id
            
            if not task_id:
                logger.warning("No task_id in storyboard, skipping persistence")
                return
            
            # Build metadata
            input_with_title = ctx.params.copy()
            input_with_title["text"] = ctx.input_text # Ensure text is included
            if not input_with_title.get("title"):
                input_with_title["title"] = storyboard.title
            
            metadata = {
                "task_id": task_id,
                "created_at": storyboard.created_at.isoformat() if storyboard.created_at else None,
                "completed_at": storyboard.completed_at.isoformat() if storyboard.completed_at else None,
                "status": "completed",
                
                "input": input_with_title,
                
                "result": {
                    "video_path": result.video_path,
                    "duration": result.duration,
                    "file_size": result.file_size,
                    "n_frames": len(storyboard.frames)
                },
                
                "config": {
                    "llm_model": self.core.config.get("llm", {}).get("model", "unknown"),
                    "llm_base_url": self.core.config.get("llm", {}).get("base_url", "unknown"),
                    "comfyui_url": self.core.config.get("comfyui", {}).get("comfyui_url", "unknown"),
                    "runninghub_enabled": bool(self.core.config.get("comfyui", {}).get("runninghub_api_key")),
                }
            }
            
            # Save metadata
            await self.core.persistence.save_task_metadata(task_id, metadata)
            logger.info(f"💾 Saved task metadata: {task_id}")
            
            # Save storyboard
            await self.core.persistence.save_storyboard(task_id, storyboard)
            logger.info(f"💾 Saved storyboard: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to persist task data: {e}")
            # Don't raise - persistence failure shouldn't break video generation
