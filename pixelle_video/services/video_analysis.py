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
Video Analysis Service - ComfyUI Workflow-based implementation

Uses ComfyUI workflows to analyze video content and generate descriptions.
"""

from typing import Optional, Literal
from pathlib import Path

from comfykit import ComfyKit
from loguru import logger

from pixelle_video.services.comfy_base_service import ComfyBaseService


class VideoAnalysisService(ComfyBaseService):
    """
    视频分析服务 —— 基于 ComfyUI 工作流的视频理解模型分析

    工作流命名约定：{source}/analyse_video.json
    - runninghub/analyse_video.json（云端默认）
    - selfhost/analyse_video.json（本地 ComfyUI）

    Requires:
        - 父类 ComfyBaseService 已初始化
        - config 中配置了 video_analysis 服务的 default_workflow
    """
    
    WORKFLOW_PREFIX = "analyse_video"
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        初始化视频分析服务，以 "video_analysis" 作为配置键继承 ComfyBaseService

        Args:
            config: 完整应用配置字典
            core: PixelleVideoCore 实例（用于访问共享的 ComfyKit）

        Side Effects:
            调用父类 __init__ 设置 self.config, self.global_config 等属性
        """
        super().__init__(config, service_name="video_analysis", core=core)
    
    async def __call__(
        self,
        video_path: str,
        # Workflow source selection
        source: Literal['runninghub', 'selfhost'] = 'runninghub',
        workflow: Optional[str] = None,
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        # Additional workflow parameters
        **params
    ) -> str:
        """
        使用视频理解模型工作流分析视频内容，返回文本描述

        支持两种后端来源：RunningHub（云端）和自部署 ComfyUI。

        Args:
            video_path: 视频文件路径（本地路径）
            source: 工作流来源 —— "runninghub"（云端默认）或 "selfhost"（本地 ComfyUI）
            workflow: 工作流 key（可选，覆盖 source 自动解析）
            comfyui_url: ComfyUI URL（可选，覆盖配置）
            runninghub_api_key: RunningHub API 密钥（可选，覆盖配置）
            **params: 额外的工作流参数

        Returns:
            视频内容的文本描述字符串

        Raises:
            FileNotFoundError: 视频文件不存在时抛出
            Exception: 分析失败或未生成描述文本时抛出
        """
        from pixelle_video.utils.workflow_util import resolve_workflow_path
        
        # 1. Validate video path
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # 2. Resolve workflow path using convention
        if workflow is None:
            # Use standardized naming: {source}/analyse_video.json
            workflow = resolve_workflow_path("analyse_video", source)
            logger.info(f"Using {source} workflow: {workflow}")
        
        # 3. Resolve workflow (returns structured info)
        workflow_info = self._resolve_workflow(workflow=workflow)
        
        # 4. Build workflow parameters
        workflow_params = {
            "video": str(video_path)  # Pass video path to workflow
        }
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 5. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "runninghub" and "workflow_id" in workflow_info:
                # RunningHub: pass workflow_id
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing RunningHub workflow: {workflow_input}")
            else:
                # Selfhost: pass file path
                workflow_input = workflow_info["path"]
                logger.info(f"Executing selfhost workflow: {workflow_input}")
            
            result = await kit.execute(workflow_input, workflow_params)
            
            # 6. Extract description from result
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"Video analysis failed: {error_msg}")
                raise Exception(f"Video analysis failed: {error_msg}")
            
            # Extract text description from result
            # Video understanding workflow returns text in result.texts array
            description = None
            
            # Format 1: Direct texts array (most common for video understanding)
            if result.texts and len(result.texts) > 0:
                description = result.texts[0]
                logger.debug(f"Found description in result.texts: {description[:100]}...")
            
            # Format 2: Selfhost outputs (direct text in outputs)
            # Format: {'6': {'text': ['description text']}}
            elif result.outputs:
                for node_id, node_output in result.outputs.items():
                    if 'text' in node_output:
                        text_list = node_output['text']
                        if text_list and len(text_list) > 0:
                            description = text_list[0]
                            logger.debug(f"Found description in outputs.text: {description[:100]}...")
                            break
            
            # Format 3: RunningHub raw_data (text file URL)
            # Format: {'raw_data': [{'fileUrl': 'https://...txt', 'fileType': 'txt', ...}]}
            if not description and result.outputs and 'raw_data' in result.outputs:
                raw_data = result.outputs['raw_data']
                if raw_data and len(raw_data) > 0:
                    # Find text file entry
                    for item in raw_data:
                        if item.get('fileType') == 'txt' and 'fileUrl' in item:
                            # Download text content from URL
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(item['fileUrl']) as resp:
                                    if resp.status == 200:
                                        description = await resp.text()
                                        description = description.strip()
                                        logger.debug(f"Downloaded description from URL: {description[:100]}...")
                                        break
            
            if not description:
                logger.error(f"No text found in result. Status: {result.status}, Outputs: {result.outputs}, Texts: {result.texts}")
                raise Exception("No description generated from video analysis")
            
            logger.info(f"✅ Video analyzed: {description[:100]}...")
            
            return description
        
        except Exception as e:
            logger.error(f"Video analysis error: {e}")
            raise
