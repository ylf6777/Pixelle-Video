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
任务数据模型

定义异步任务管理所需的所有 Pydantic 数据模型和枚举类型。

状态流转::

    PENDING ──→ RUNNING ──→ COMPLETED
                   │
                   ├──→ FAILED
                   │
                   └──→ CANCELLED
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """
    任务状态枚举

    Values:
        PENDING (pending):   任务已创建，等待执行
        RUNNING (running):   任务正在执行中
        COMPLETED (completed): 任务已成功完成
        FAILED (failed):     任务执行失败
        CANCELLED (cancelled): 任务被手动取消
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """
    任务类型枚举

    Values:
        VIDEO_GENERATION (video_generation): 视频生成任务
    """
    VIDEO_GENERATION = "video_generation"


class TaskProgress(BaseModel):
    """
    任务进度信息模型

    Attributes:
        current (int): 当前进度步数。默认: 0
        total (int): 总步数。默认: 0
        percentage (float): 完成百分比 (0.0-100.0)。默认: 0.0
        message (str): 进度描述信息。默认: ""
    """
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    message: str = ""


class Task(BaseModel):
    """
    任务模型

    表示一个异步任务的完整信息，包括标识、状态、进度和结果。
    也用作 FastAPI 的响应模型（response_model=Task）。

    Attributes:
        task_id (str): 任务唯一标识（UUID v4 格式字符串）
        task_type (TaskType): 任务类型
        status (TaskStatus): 当前状态。默认: PENDING
        progress (Optional[TaskProgress]): 进度信息。运行时更新
        result (Optional[Any]): 任务成功完成后的结果数据。None 表示无结果
        error (Optional[str]): 任务失败时的错误信息。None 表示无错误
        created_at (datetime): 任务创建时间。默认: 当前 UTC 时间
        started_at (Optional[datetime]): 任务开始执行时间。None 表示尚未开始
        completed_at (Optional[datetime]): 任务完成/失败/取消时间。None 表示未结束
        request_params (Optional[dict]): 原始请求参数（供调试和重新提交使用）

    Requires:
        - Pydantic: 用于模型序列化和 JSON Schema 生成
        - datetime: datetime 序列化为 ISO 8601 格式
    """
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING

    # 进度追踪
    progress: Optional[TaskProgress] = None

    # 执行结果
    result: Optional[Any] = None
    error: Optional[str] = None

    # 时间元数据
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 原始请求参数（供参考/重新提交）
    request_params: Optional[dict] = None

    class Config:
        """Pydantic 模型配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
