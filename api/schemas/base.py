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
基础 Schema 模型

定义所有 API 响应共用的基础 Pydantic 模型。
具体业务响应模型应继承或参考这些基础模型的结构。
"""

from typing import Any, Optional
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """
    基础 API 响应模型

    提供所有成功响应共用的标准字段结构。

    Attributes:
        success (bool): 请求是否成功。默认: True
        message (str): 响应消息。默认: "Success"
        data (Optional[Any]): 响应数据载体。可以是任意类型。默认: None
    """
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """
    错误响应模型

    用于统一返回错误信息的格式。可由全局异常处理器使用。

    Attributes:
        success (bool): 固定为 False
        message (str): 面向用户的错误描述信息
        error (Optional[str]): 面向开发者的详细错误信息。默认: None
    """
    success: bool = False
    message: str
    error: Optional[str] = None
