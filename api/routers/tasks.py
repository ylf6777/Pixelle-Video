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
任务管理端点

提供异步任务的查询、列举和取消接口。
任务由 TaskManager 在内存中管理，状态包括：
pending → running → completed/failed/cancelled
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.error_handler import map_exception
from api.tasks import task_manager, Task, TaskStatus

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None, description="按状态过滤"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回数量")
):
    """
    列出任务

    检索任务列表，支持按状态过滤和数量限制。

    入参:
        - **status** (Optional[TaskStatus]): 按状态过滤。
            可选值: pending / running / completed / failed / cancelled。
            不传则返回所有任务。
        - **limit** (int): 最大返回数量 (1-1000)。默认: 100

    Returns:
        List[Task]: 任务列表，按创建时间降序排列（最新的在前）。

    Raises:
        HTTPException 500: 内部服务错误 — 任务管理器查询失败

    Requires:
        - task_manager  — 全局任务管理器单例（api.tasks.task_manager）

    Side Effects:
        - 无（纯查询端点）
    """
    try:
        tasks = task_manager.list_tasks(status=status, limit=limit)
        return tasks

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "tasks")


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """
    获取任务详情

    检索指定任务的详细信息，包括状态、进度和结果（如果已完成）。

    入参:
        - **task_id** (str): 任务 ID（UUID v4 格式）

    Returns:
        Task: 任务对象，包含 task_id、status、progress、result、error 等字段。
            如果 result 不为 None，说明任务已完成并有成功结果。
            如果 error 不为 None，说明任务已失败。

    Raises:
        HTTPException 404: 任务不存在 — task_id 未在任务管理器中找到

    Requires:
        - task_manager  — 全局任务管理器单例

    Side Effects:
        - 无（纯查询端点）
    """
    try:
        task = task_manager.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

        return task

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "tasks")


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """
    取消任务

    取消正在运行或等待中的任务。已完成、已失败或已取消的任务无法再次取消。

    入参:
        - **task_id** (str): 任务 ID

    Returns:
        dict: ``{"success": True, "message": "..."}`` 表示取消成功。

    Raises:
        HTTPException 404: 任务不存在 — task_id 未找到

    Requires:
        - task_manager  — 全局任务管理器单例

    Side Effects:
        - 如果任务正在运行：取消对应的 asyncio Task（触发 CancelledError）
        - 更新任务状态为 "cancelled"
        - 记录 info 级别操作日志
    """
    try:
        success = task_manager.cancel_task(task_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

        return {
            "success": True,
            "message": f"任务 {task_id} 已成功取消"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "tasks")
