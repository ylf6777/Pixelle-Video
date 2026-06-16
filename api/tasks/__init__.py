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
异步任务管理子包

提供视频生成等异步操作的任务生命周期管理。
所有 API 模块通过 ``from api.tasks import task_manager`` 获取全局单例。

导出:
    - Task           — 任务 Pydantic 数据模型
    - TaskStatus     — 任务状态枚举（PENDING/RUNNING/COMPLETED/FAILED/CANCELLED）
    - TaskType       — 任务类型枚举（VIDEO_GENERATION）
    - task_manager   — 全局 TaskManager 单例
"""

from api.tasks.models import Task, TaskStatus, TaskType
from api.tasks.manager import task_manager

__all__ = ["Task", "TaskStatus", "TaskType", "task_manager"]
