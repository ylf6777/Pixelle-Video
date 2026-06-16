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
异步任务管理器

基于内存的异步任务管理，支持任务生命周期管理、进度追踪和自动清理。

特性:
    - 纯内存存储（可后续替换为 Redis）
    - 任务全生命周期管理（创建 → 执行 → 完成/失败/取消）
    - 实时进度追踪
    - 自动清理过期任务
    - 并发任务数量限制
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from loguru import logger

from api.tasks.models import Task, TaskStatus, TaskType, TaskProgress
from api.config import api_config


class TaskManager:
    """
    异步视频生成任务管理器

    核心数据结构:
        - _tasks (dict): task_id → Task 的映射（持久存储）
        - _task_futures (dict): task_id → asyncio.Task 的映射（运行时）
        - _cleanup_task (asyncio.Task): 后台清理定时任务的句柄

    线程安全: 不保证。当前设计为单 asyncio 事件循环内运行。

    Requires:
        - api_config            — API 配置（任务清理间隔、保留时间等）
        - asyncio              — 用于异步任务调度
        - uuid                 — 生成任务 ID
        - datetime             — 时间戳和清理逻辑
        - loguru               — 结构化日志

    Side Effects:
        - start(): 创建后台 asyncio 定时任务用于自动清理
        - stop(): 取消所有正在运行的任务，清理内存数据结构
    """

    def __init__(self):
        """
        初始化任务管理器

        所有数据结构初始为空，需调用 start() 启动调度器。

        Side Effects:
            - 无（纯内存初始化）
        """
        self._tasks: Dict[str, Task] = {}
        self._task_futures: Dict[str, asyncio.Task] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """
        启动任务管理器及后台清理定时器

        启动后，管理器开始接受新任务，并启动后台清理循环。
        重复调用时记录警告并跳过（幂等）。

        Raises:
            RuntimeError: 如果 asyncio.create_task 失败（事件循环未运行）。

        Requires:
            - asyncio 事件循环   — 必须在运行中的事件循环内调用
            - api_config.task_cleanup_interval — 清理间隔配置

        Side Effects:
            - 设置 self._running = True
            - 创建后台 asyncio 定时任务 self._cleanup_task
            - 记录 info 级别启动日志
        """
        if self._running:
            logger.warning("任务管理器已在运行中")
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("✅ 任务管理器已启动")

    async def stop(self):
        """
        停止任务管理器并取消所有任务

        按以下顺序执行清理：
        1. 取消后台清理定时器
        2. 取消所有正在运行的任务
        3. 清空内存中的任务和 Future 字典

        重复调用时，因为 _running 已为 False，清理循环自动退出。

        Raises:
            asyncio.CancelledError: 在等待 _cleanup_task 时可能被传播（内部捕获）。

        Requires:
            - _running             — 必须先通过 start() 设置为 True

        Side Effects:
            - 设置 self._running = False
            - 取消并等待 _cleanup_task 退出
            - 取消所有 _task_futures 中的 asyncio Task
            - 清空 self._tasks 和 self._task_futures
            - 记录 info 级别关闭日志
        """
        self._running = False

        # 取消清理定时器
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 取消所有正在运行的任务
        for task_id, future in self._task_futures.items():
            if not future.done():
                future.cancel()
                logger.info(f"已取消任务: {task_id}")

        self._tasks.clear()
        self._task_futures.clear()
        logger.info("✅ 任务管理器已停止")

    def create_task(
        self,
        task_type: TaskType,
        request_params: Optional[dict] = None
    ) -> Task:
        """
        创建新任务

        生成 UUID v4 作为任务 ID，创建初始状态为 PENDING 的任务对象，
        存入内存字典并返回。

        Args:
            task_type (TaskType): 任务类型。
                目前仅支持 TaskType.VIDEO_GENERATION。
            request_params (Optional[dict]): 原始请求参数。
                存入 task.request_params 供调试和重新提交使用。
                默认值: None

        Returns:
            Task: 新创建的任务对象，状态为 PENDING。
                task_id 为 UUID v4 格式（如 "a1b2c3d4-..."）。

        Raises:
            Exception: 如果 uuid.uuid4() 生成失败（极罕见）。

        Requires:
            - uuid                     — 标准库，生成唯一任务 ID
            - self._tasks             — 内存字典，存储任务

        Side Effects:
            - 向 self._tasks 写入一条新记录
            - 记录 info 级别创建日志
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            request_params=request_params,
        )

        self._tasks[task_id] = task
        logger.info(f"已创建任务 {task_id} ({task_type})")
        return task

    async def execute_task(
        self,
        task_id: str,
        coro_func: Callable,
        *args,
        **kwargs
    ):
        """
        异步执行指定任务

        将任务状态更新为 RUNNING，在后台 asyncio Task 中执行传入的协程函数，
        完成后根据结果自动更新任务状态和结果。

        Args:
            task_id (str): 要执行的任务 ID。必须已通过 create_task() 创建。
            coro_func (Callable): 要执行的异步函数（协程）。
                函数应返回可序列化的结果（dict/str/int 等）。
            *args: 传递给 coro_func 的位置参数。
            **kwargs: 传递给 coro_func 的关键字参数。

        Raises:
            无 — 内部异常会被捕获并设置 task.error，不会向上传播。

        Requires:
            - task_id                — 必须在 self._tasks 中存在
            - coro_func              — 必须是一个可 await 的协程函数
            - asyncio.create_task    — 用于创建后台 asyncio Task

        Side Effects:
            - 更新任务状态: PENDING → RUNNING → COMPLETED/FAILED
            - 更新 task.started_at、task.completed_at、task.result、task.error
            - 在 self._task_futures 中注册 asyncio Task
            - 记录 info/error 级别执行日志
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"任务 {task_id} 未找到")
            return

        # 创建后台 asyncio Task 执行实际工作
        async def _execute():
            """
            后台任务执行包装器

            自动管理任务状态转换和异常捕获。
            无论成功还是失败，都会记录 task.completed_at 时间戳。
            """
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                logger.info(f"任务 {task_id} 开始执行")

                # 执行实际的协程函数
                result = await coro_func(*args, **kwargs)

                # 更新任务为已完成
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                logger.info(f"任务 {task_id} 已完成")

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()
                logger.error(f"任务 {task_id} 失败: {e}")

        # 启动后台执行
        future = asyncio.create_task(_execute())
        self._task_futures[task_id] = future

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        按 ID 获取任务

        Args:
            task_id (str): 任务 ID。

        Returns:
            Optional[Task]: 任务对象。如果 task_id 不存在，返回 None。

        Side Effects:
            - 无（纯查询方法）
        """
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        列出任务（支持按状态过滤和数量限制）

        Args:
            status (Optional[TaskStatus]): 按状态过滤。
                如果提供，仅返回匹配该状态的任务。
                默认值: None（返回所有任务）
            limit (int): 最大返回数量。
                默认值: 100。注意：超过此数量的任务会被截断。

        Returns:
            List[Task]: 任务列表，按创建时间降序排列（最新的在前）。

        Side Effects:
            - 无（纯查询方法）
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # 按创建时间降序排列
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[:limit]

    def update_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str = ""
    ):
        """
        更新任务进度

        创建或更新 TaskProgress 对象，计算完成百分比。

        Args:
            task_id (str): 任务 ID。
            current (int): 当前进度步数。应 <= total。
            total (int): 总步数。必须 > 0 才能计算百分比。
            message (str): 进度描述信息。默认值: ""

        Side Effects:
            - 更新 task.progress 字段
            - 如果 task_id 不存在，静默忽略（不报错）
        """
        task = self._tasks.get(task_id)
        if not task:
            return

        percentage = (current / total * 100) if total > 0 else 0
        task.progress = TaskProgress(
            current=current,
            total=total,
            percentage=percentage,
            message=message
        )

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        将运行中或等待中的任务设置为已取消状态。
        已完成、已失败或已取消的任务无法再次取消。

        Args:
            task_id (str): 任务 ID。

        Returns:
            bool: True — 任务已成功取消。
                  False — 任务不存在或已处于终态（COMPLETED/FAILED/CANCELLED）。

        Side Effects:
            - 如果任务正在运行：取消对应的 asyncio Task（触发 CancelledError）
            - 更新 task.status 为 CANCELLED
            - 设置 task.completed_at
            - 记录 info 级别取消日志
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 不允许取消已处于终态的任务
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        # 如果任务正在运行，取消其 Future
        future = self._task_futures.get(task_id)
        if future and not future.done():
            future.cancel()

        # 更新任务状态
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        logger.info(f"已取消任务 {task_id}")
        return True

    async def _cleanup_loop(self):
        """
        后台定时清理过期任务的循环

        每隔 api_config.task_cleanup_interval 秒执行一次清理。
        清理标准：任务状态为 COMPLETED/FAILED/CANCELLED 且
        completed_at 早于当前时间减去 api_config.task_retention_time。

        Raises:
            asyncio.CancelledError: 当 _running 变为 False 且 cleanup_task 被取消时。
                CancelledError 会终止循环（不向上传播）。

        Requires:
            - api_config.task_cleanup_interval — 清理间隔（秒）。默认: 3600（1小时）
            - api_config.task_retention_time  — 保留时间（秒）。默认: 86400（24小时）

        Side Effects:
            - 定期从 self._tasks 和 self._task_futures 中删除过期任务
            - 有清理时记录 info 级别日志
        """
        while self._running:
            try:
                await asyncio.sleep(api_config.task_cleanup_interval)
                self._cleanup_old_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环出错: {e}")

    def _cleanup_old_tasks(self):
        """
        删除过期的已完成/失败/取消任务

        检查所有任务的 completed_at 时间戳，
        删除超过保留时间的任务记录及其 Future。

        Requires:
            - api_config.task_retention_time — 任务保留时长（秒）

        Side Effects:
            - 从 self._tasks 删除过期任务
            - 从 self._task_futures 删除对应的 Future
            - 有清理时记录 info 级别日志
        """
        cutoff_time = datetime.now() - timedelta(seconds=api_config.task_retention_time)

        tasks_to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at and task.completed_at < cutoff_time:
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self._tasks[task_id]
            if task_id in self._task_futures:
                del self._task_futures[task_id]

        if tasks_to_remove:
            logger.info(f"已清理 {len(tasks_to_remove)} 个过期任务")


# 全局任务管理器单例 — 所有 API 模块通过此实例访问
task_manager = TaskManager()
