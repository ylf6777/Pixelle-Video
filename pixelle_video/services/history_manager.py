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
History Manager Service

Business logic for history management (UI-agnostic).
Provides high-level operations on top of PersistenceService.
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger

from pixelle_video.services.persistence import PersistenceService


class HistoryManager:
    """
    历史记录管理服务，提供 UI 无关的业务逻辑

    封装对 PersistenceService 的高层操作，包括任务列表/详情/删除/复制/统计。

    Requires:
        PersistenceService 实例
    """
    
    def __init__(self, persistence: PersistenceService):
        """
        初始化历史记录管理器

        Args:
            persistence: PersistenceService 实例

        Side Effects:
            保存 persistence 引用到 self.persistence
        """
        self.persistence = persistence
    
    async def get_task_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        获取分页任务列表

        Args:
            page: 页码（从 1 开始）
            page_size: 每页条目数
            status: 按状态筛选（可选）
            sort_by: 排序字段（created_at, completed_at, title, duration）
            sort_order: 排序方向（asc, desc）

        Returns:
            分页结果字典：{"tasks": [...], "total": N, "page": N, "page_size": N, "total_pages": N}
        """
        return await self.persistence.list_tasks_paginated(
            page=page,
            page_size=page_size,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order
        )
    
    async def get_task_detail(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务完整详情（含故事板数据）

        Args:
            task_id: 任务 ID

        Returns:
            {"metadata": {...}, "storyboard": {...}} 字典，任务不存在时返回 None
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            return None
        
        storyboard = await self.persistence.load_storyboard(task_id)
        
        return {
            "metadata": metadata,
            "storyboard": storyboard,
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取所有任务的统计信息

        Returns:
            统计字典：{"total_tasks", "completed", "failed", "total_duration"（秒）, "total_size"（字节）}
        """
        return await self.persistence.get_statistics()
    
    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其所有关联文件

        Args:
            task_id: 要删除的任务 ID

        Returns:
            成功返回 True，否则返回 False
        """
        return await self.persistence.delete_task(task_id)
    
    async def duplicate_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        复制任务的输入参数以供重新生成使用

        可用于：1) 复制之前任务的所有生成参数，2) 预填生成表单，3) 用相同/修改后的参数重新生成

        Args:
            task_id: 要复制的任务 ID

        Returns:
            输入参数字典（含 text, mode, title, n_scenes, tts_inference_mode 等），任务不存在时返回 None
        """
        metadata = await self.persistence.load_task_metadata(task_id)
        if not metadata:
            logger.warning(f"Task {task_id} not found for duplication")
            return None
        
        # Extract input parameters
        input_params = metadata.get("input", {})
        logger.info(f"Duplicated task {task_id} parameters")
        
        return input_params
    
    async def rebuild_index(self):
        """
        重建任务索引（用于维护或手动修改后同步）

        Side Effects:
            调用 persistence.rebuild_index() 重新扫描任务目录
        """
        await self.persistence.rebuild_index()
    
    # ========================================================================
    # Future Extensions (Phase 3)
    # ========================================================================
    
    async def regenerate_frame(
        self,
        task_id: str,
        frame_index: int,
        **override_params
    ) -> Optional[str]:
        """
        重新生成指定帧（未来功能，阶段3实现）

        Args:
            task_id: 原始任务 ID
            frame_index: 要重新生成的帧索引（从 0 开始）
            **override_params: 要覆写的参数（image_prompt, style 等）

        Returns:
            新帧图片路径，失败时返回 None（当前始终返回 None，功能未实现）
        """
        logger.warning("regenerate_frame is not implemented yet (Phase 3 feature)")
        return None
    
    async def export_task(self, task_id: str, export_path: str) -> Optional[str]:
        """
        将任务导出为打包文件（元数据 + 视频 + 帧）（未来功能，阶段3实现）

        Args:
            task_id: 要导出的任务 ID
            export_path: 导出文件路径（如 "exports/task.zip"）

        Returns:
            导出文件路径，失败时返回 None（当前始终返回 None，功能未实现）
        """
        logger.warning("export_task is not implemented yet (Phase 3 feature)")
        return None

