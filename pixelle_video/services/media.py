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
Media Generation Service - ComfyUI Workflow-based implementation

Supports both image and video generation workflows.
Automatically detects output type based on ExecuteResult.
"""

from typing import Optional

from comfykit import ComfyKit
from loguru import logger

from pixelle_video.services.comfy_base_service import ComfyBaseService
from pixelle_video.models.media import MediaResult


class MediaService(ComfyBaseService):
    """
    媒体生成服务 —— 基于 ComfyUI 工作流的图片/视频生成

    使用 ComfyKit 执行 image_ 和 video_ 前缀的工作流，支持自部署和 RunningHub 两种后端。
    通过 media_type 参数区分生成类型（"image" 或 "video"）。

    Requires:
        - 父类 ComfyBaseService 已初始化
        - config 中配置了 default_workflow
    """
    
    WORKFLOW_PREFIX = ""  # Will be overridden by _scan_workflows
    DEFAULT_WORKFLOW = None  # No hardcoded default, must be configured
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        初始化媒体生成服务，以 "image" 作为配置键继承 ComfyBaseService

        Args:
            config: 完整应用配置字典
            core: PixelleVideoCore 实例（用于访问共享的 ComfyKit）

        Side Effects:
            调用父类 __init__ 设置 self.config, self.global_config 等属性
        """
        super().__init__(config, service_name="image", core=core)  # Keep "image" for config compatibility
    
    def _scan_workflows(self):
        """
        扫描所有源目录中 image_ 和 video_ 前缀的 JSON 工作流文件

        重写父类方法，同时支持图片和视频两种工作流前缀。

        Returns:
            工作流信息字典列表（按 key 排序）

        Side Effects:
            无缓存（每次重新扫描），与父类不同
        """
        from pixelle_video.utils.os_util import list_resource_dirs, list_resource_files, get_resource_path
        from pathlib import Path
        
        workflows = []
        
        # Get all workflow source directories
        source_dirs = list_resource_dirs("workflows")
        
        if not source_dirs:
            logger.warning("No workflow source directories found")
            return workflows
        
        # Scan each source directory for workflow files
        for source_name in source_dirs:
            # Get all JSON files for this source
            workflow_files = list_resource_files("workflows", source_name)
            
            # Filter to only files matching image_ or video_ prefix
            matching_files = [
                f for f in workflow_files 
                if (f.startswith("image_") or f.startswith("video_")) and f.endswith('.json')
            ]
            
            for filename in matching_files:
                try:
                    # Get actual file path
                    file_path = Path(get_resource_path("workflows", source_name, filename))
                    workflow_info = self._parse_workflow_file(file_path, source_name)
                    workflows.append(workflow_info)
                    logger.debug(f"Found workflow: {workflow_info['key']}")
                except Exception as e:
                    logger.error(f"Failed to parse workflow {source_name}/{filename}: {e}")
        
        # Sort by key (source/name)
        return sorted(workflows, key=lambda w: w["key"])

    def list_workflows(self) -> list[dict]:
        """
        列出 ComfyUI/RunningHub/自部署工作流（不含直接 API 模型）

        直接 API 模型通过 core.api_media.list_workflows() 暴露，UI 层可据此将本地工作流与 API 模型放入不同的选择器。

        Returns:
            工作流信息字典列表（按 key 排序）

        Raises:
            无额外异常，继承父类行为
        """
        return super().list_workflows()
    
    async def __call__(
        self,
        prompt: str,
        workflow: Optional[str] = None,
        # Media type specification (required for proper handling)
        media_type: str = "image",  # "image" or "video"
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        # Common workflow parameters
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[float] = None,  # Video duration in seconds (for video workflows)
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        **params
    ) -> MediaResult:
        """
        通过工作流生成媒体（图片或视频），支持 api/ 前缀路由到 API 媒体服务

        Args:
            prompt: 媒体生成提示词
            workflow: 工作流 key 或文件名（默认使用配置中的 default_workflow）
            media_type: 媒体类型 —— "image" 或 "video"（默认 "image"）
            comfyui_url: ComfyUI URL（可选，覆盖配置）
            runninghub_api_key: RunningHub API 密钥（可选，覆盖配置）
            width: 媒体宽度
            height: 媒体高度
            duration: 目标视频时长/秒（仅视频工作流，通常来自 TTS 音频时长）
            output_path: 输出路径（可选）
            image_path: 输入图片路径（可选，用于图生视频等）
            negative_prompt: 负面提示词
            steps: 采样步数
            seed: 随机种子
            cfg: CFG 缩放系数
            sampler: 采样器名称
            **params: 额外的工作流参数

        Returns:
            包含 media_type（"image" 或 "video"）和 url 的 MediaResult 对象

        Raises:
            RuntimeError: api/ 前缀工作流但 API 媒体服务未初始化
            Exception: 媒体生成失败（状态非 completed 或无输出）
        """
        selected_workflow = workflow or self.config.get("default_workflow")
        if selected_workflow and selected_workflow.startswith("api/"):
            if not self.core or not getattr(self.core, "api_media", None):
                raise RuntimeError("API media service is not initialized")
            return await self.core.api_media(
                prompt=prompt,
                workflow=selected_workflow,
                media_type=media_type,
                width=width,
                height=height,
                duration=duration,
                output_path=output_path,
                image_path=image_path,
                negative_prompt=negative_prompt,
                steps=steps,
                seed=seed,
                cfg=cfg,
                sampler=sampler,
                **params
            )

        # 1. Resolve workflow (returns structured info)
        workflow_info = self._resolve_workflow(workflow=workflow)
        
        # 2. Build workflow parameters (ComfyKit config is now managed by core)
        workflow_params = {"prompt": prompt}
        
        # Add optional parameters
        if width is not None:
            workflow_params["width"] = width
        if height is not None:
            workflow_params["height"] = height
        if duration is not None:
            workflow_params["duration"] = duration
            if media_type == "video":
                logger.info(f"📏 Target video duration: {duration:.2f}s (from TTS audio)")
        if negative_prompt is not None:
            workflow_params["negative_prompt"] = negative_prompt
        if steps is not None:
            workflow_params["steps"] = steps
        if seed is not None:
            workflow_params["seed"] = seed
        if cfg is not None:
            workflow_params["cfg"] = cfg
        if sampler is not None:
            workflow_params["sampler"] = sampler
        if image_path is not None:
            workflow_params["image"] = image_path

        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 4. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "runninghub" and "workflow_id" in workflow_info:
                # RunningHub: pass workflow_id (ComfyKit will use runninghub backend)
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing RunningHub workflow: {workflow_input}")
            else:
                # Selfhost: pass file path (ComfyKit will use local ComfyUI)
                workflow_input = workflow_info["path"]
                logger.info(f"Executing selfhost workflow: {workflow_input}")
            
            result = await kit.execute(workflow_input, workflow_params)
            
            # 5. Handle result based on specified media_type
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"Media generation failed: {error_msg}")
                raise Exception(f"Media generation failed: {error_msg}")
            
            # Extract media based on specified type
            if media_type == "video":
                # Video workflow - get video from result
                if not result.videos:
                    logger.error("No video generated (workflow returned no videos)")
                    raise Exception("No video generated")
                
                video_url = result.videos[0]
                logger.info(f"✅ Generated video: {video_url}")
                
                # Try to extract duration from result (if available)
                duration = None
                if hasattr(result, 'duration') and result.duration:
                    duration = result.duration
                
                return MediaResult(
                    media_type="video",
                    url=video_url,
                    duration=duration
                )
            else:  # image
                # Image workflow - get image from result
                if not result.images:
                    logger.error("No image generated (workflow returned no images)")
                    raise Exception("No image generated")
                
                image_url = result.images[0]
                logger.info(f"✅ Generated image: {image_url}")
                
                return MediaResult(
                    media_type="image",
                    url=image_url
                )
        
        except Exception as e:
            logger.error(f"Media generation error: {e}")
            raise
