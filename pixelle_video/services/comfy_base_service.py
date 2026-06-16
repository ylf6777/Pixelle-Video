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
ComfyUI Base Service - Common logic for ComfyUI-based services
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from comfykit import ComfyKit
from loguru import logger

from pixelle_video.utils.os_util import (
    get_resource_path,
    list_resource_files,
    list_resource_dirs
)


class ComfyBaseService:
    """
    Base service for ComfyUI workflow-based capabilities
    
    Provides common functionality for TTS, Image, and other ComfyUI-based services.
    
    Subclasses should define:
    - WORKFLOW_PREFIX: Prefix for workflow files (e.g., "image_", "tts_")
    - DEFAULT_WORKFLOW: Default workflow filename (e.g., "image_flux.json")
    - WORKFLOWS_DIR: Directory containing workflows (default: "workflows")
    """
    
    WORKFLOW_PREFIX: str = ""  # Must be overridden by subclass
    DEFAULT_WORKFLOW: str = ""  # Must be overridden by subclass
    WORKFLOWS_DIR: str = "workflows"
    
    def __init__(self, config: dict, service_name: str, core=None):
        """
        初始化 ComfyUI 基础服务，设置服务配置、全局配置和服务标识

        Args:
            config: 完整应用配置字典
            service_name: 配置中的服务名称（如 "tts", "image"）
            core: PixelleVideoCore 实例（用于访问共享的 ComfyKit）

        Side Effects:
            设置 self.config, self.global_config, self.service_name, self._workflows_cache, self.core
        """
        # Service-specific config (e.g., config["comfyui"]["tts"])
        comfyui_config = config.get("comfyui", {})
        self.config = comfyui_config.get(service_name, {})
        
        # Global ComfyUI config (for comfyui_url and runninghub_api_key)
        self.global_config = comfyui_config
        
        self.service_name = service_name
        self._workflows_cache: Optional[List[str]] = None
        
        # Reference to core (for accessing shared ComfyKit)
        self.core = core
    
    def _scan_workflows(self) -> List[Dict[str, Any]]:
        """
        扫描所有源目录中匹配前缀的 JSON 工作流文件（合并 workflows/ 和 data/workflows/）

        首次扫描后缓存结果到 self._workflows_cache，避免重复文件系统 I/O。

        Returns:
            工作流信息字典列表（按 key 排序），示例：
            [
                {
                    "name": "image_flux.json",
                    "display_name": "image_flux.json - Selfhost",
                    "source": "selfhost",
                    "path": "workflows/selfhost/image_flux.json",
                    "key": "selfhost/image_flux.json"
                },
                {
                    "name": "image_flux.json",
                    "display_name": "image_flux.json - Runninghub",
                    "source": "runninghub",
                    "path": "workflows/runninghub/image_flux.json",
                    "key": "runninghub/image_flux.json",
                    "workflow_id": "123456"
                }
            ]

        Side Effects:
            缓存结果到 self._workflows_cache
        """
        if self._workflows_cache is not None:
            return self._workflows_cache

        workflows = []
        
        # Get all workflow source directories (merged from workflows/ and data/workflows/)
        source_dirs = list_resource_dirs("workflows")
        
        if not source_dirs:
            logger.warning("No workflow source directories found")
            return workflows
        
        # Scan each source directory for workflow files
        for source_name in source_dirs:
            # Get all JSON files for this source (merged from both locations)
            workflow_files = list_resource_files("workflows", source_name)
            
            # Filter to only files matching the prefix
            matching_files = [
                f for f in workflow_files 
                if f.startswith(self.WORKFLOW_PREFIX) and f.endswith('.json')
            ]
            
            for filename in matching_files:
                try:
                    # Get actual file path (custom > default)
                    file_path = Path(get_resource_path("workflows", source_name, filename))
                    workflow_info = self._parse_workflow_file(file_path, source_name)
                    workflows.append(workflow_info)
                    logger.debug(f"Found workflow: {workflow_info['key']}")
                except Exception as e:
                    logger.error(f"Failed to parse workflow {source_name}/{filename}: {e}")
        
        # Sort by key (source/name)
        self._workflows_cache = sorted(workflows, key=lambda w: w["key"])
        return self._workflows_cache
    
    def _parse_workflow_file(self, file_path: Path, source: str) -> Dict[str, Any]:
        """
        解析工作流 JSON 文件并提取元数据，包括名称、来源、路径和可选的工作流 ID

        Args:
            file_path: 工作流 JSON 文件路径
            source: 源目录名称（如 "selfhost", "runninghub"）

        Returns:
            工作流信息字典，结构如下：
            {
                "name": "image_flux.json",
                "display_name": "image_flux.json - Runninghub",
                "source": "runninghub",
                "path": "workflows/runninghub/image_flux.json",
                "key": "runninghub/image_flux.json",
                "workflow_id": "123456"  # 仅 RunningHub 包装格式
            }
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        # Build base info
        workflow_info = {
            "name": file_path.name,
            "display_name": f"{file_path.name} - {source.title()}",
            "source": source,
            "path": str(file_path),
            "key": f"{source}/{file_path.name}"
        }
        
        # Check if it's a wrapper format (RunningHub, etc.)
        if "source" in content:
            # Wrapper format: {"source": "runninghub", "workflow_id": "xxx", ...}
            if "workflow_id" in content:
                workflow_info["workflow_id"] = content["workflow_id"]
        
        return workflow_info
    
    def _get_default_workflow(self) -> str:
        """
        从配置中获取默认工作流 key（必须配置，无回退值）

        Returns:
            默认工作流 key（如 "runninghub/image_flux.json"）

        Raises:
            ValueError: 未配置 default_workflow 时抛出，提示可用工作流列表
        """
        default_workflow = self.config.get("default_workflow")
        
        if not default_workflow:
            raise ValueError(
                f"No default workflow configured for {self.service_name}. "
                f"Please set 'default_workflow' in config.yaml under '{self.service_name}' section. "
                f"Available workflows: {', '.join(self.available)}"
            )
        
        return default_workflow
    
    def _resolve_workflow(self, workflow: Optional[str] = None) -> Dict[str, Any]:
        """
        将工作流 key 解析为对应的工作流信息字典，未指定时使用配置中的默认值

        Args:
            workflow: 工作流 key（如 "runninghub/image_flux.json"），None 时使用配置中的默认工作流

        Returns:
            工作流信息字典，结构如下：
            {
                "name": "image_flux.json",
                "display_name": "image_flux.json - Runninghub",
                "source": "runninghub",
                "path": "workflows/runninghub/image_flux.json",
                "key": "runninghub/image_flux.json",
                "workflow_id": "123456"  # 仅 RunningHub
            }

        Raises:
            ValueError: 工作流未找到时抛出，提示所有可用工作流 key 列表
        """
        # 1. If not specified, use default from config
        if workflow is None:
            workflow = self._get_default_workflow()
        
        # 2. Scan available workflows
        available_workflows = self._scan_workflows()
        
        # 3. Find matching workflow by key
        for wf_info in available_workflows:
            if wf_info["key"] == workflow:
                logger.info(f"🎬 Using {self.service_name} workflow: {workflow}")
                return wf_info
        
        # 4. Not found - generate error message
        available_keys = [wf["key"] for wf in available_workflows]
        available_str = ", ".join(available_keys) if available_keys else "none"
        raise ValueError(
            f"Workflow '{workflow}' not found. "
            f"Available workflows: {available_str}"
        )
    
    def _prepare_comfykit_config(
        self,
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        runninghub_instance_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        准备 ComfyKit 配置字典，按优先级合并参数、全局配置和环境变量

        Args:
            comfyui_url: ComfyUI URL（可选，优先级：参数 > 全局配置 > 环境变量 COMFYUI_BASE_URL > 默认值）
            runninghub_api_key: RunningHub API 密钥（可选，优先级：参数 > 全局配置 > 环境变量 RUNNINGHUB_API_KEY）
            runninghub_instance_type: RunningHub 实例类型（可选，优先级：参数 > 全局配置 > 环境变量 RUNNINGHUB_INSTANCE_TYPE）

        Returns:
            ComfyKit 配置字典，包含 comfyui_url 及可选的 runninghub_api_key、runninghub_instance_type

        Side Effects:
            读取环境变量 COMFYUI_BASE_URL, RUNNINGHUB_API_KEY, RUNNINGHUB_INSTANCE_TYPE
        """
        kit_config = {}
        
        # ComfyUI URL (priority: param > global config > env > default)
        final_comfyui_url = (
            comfyui_url 
            or self.global_config.get("comfyui_url")
            or os.getenv("COMFYUI_BASE_URL")
            or "http://127.0.0.1:8188"
        )
        kit_config["comfyui_url"] = final_comfyui_url
        
        # RunningHub API key (priority: param > global config > env)
        final_rh_key = (
            runninghub_api_key
            or self.global_config.get("runninghub_api_key")
            or os.getenv("RUNNINGHUB_API_KEY")
        )
        if final_rh_key:
            kit_config["runninghub_api_key"] = final_rh_key
        
        # RunningHub instance type (priority: param > global config > env)
        # Only pass if non-empty value
        final_instance_type = (
            runninghub_instance_type
            or self.global_config.get("runninghub_instance_type")
            or os.getenv("RUNNINGHUB_INSTANCE_TYPE")
        )
        if final_instance_type and final_instance_type.strip():
            kit_config["runninghub_instance_type"] = final_instance_type
        
        logger.debug(f"ComfyKit config: {kit_config}")
        return kit_config
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """
        列出所有可用工作流及完整元数据（名称、来源、路径、key 等）

        Returns:
            工作流信息字典列表（按 key 排序），每个字典包含 name, display_name, source, path, key 及可选的 workflow_id
        """
        return self._scan_workflows()
    
    @property
    def available(self) -> List[str]:
        """
        列出所有可用工作流的 key 列表

        Returns:
            可用工作流 key 列表（如 ["runninghub/image_flux.json", "selfhost/image_flux.json", ...]）
        """
        workflows = self.list_workflows()
        return [wf["key"] for wf in workflows]
    
    def __repr__(self) -> str:
        """
        返回服务的字符串表示，包含类名、默认工作流和可用工作流列表

        Returns:
            格式为 <ClassName default='key' available=[key1, key2, ...]> 的字符串
        """
        default = self._get_default_workflow()
        available = ", ".join(self.available) if self.available else "none"
        return (
            f"<{self.__class__.__name__} "
            f"default={default!r} "
            f"available=[{available}]>"
        )

