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
API 配置模块

定义 FastAPI 服务的所有运行时配置项，使用 Pydantic BaseModel
进行类型校验和默认值管理。全局单例 `api_config` 被所有 API 模块导入使用。
"""

from typing import Optional
from pydantic import BaseModel


class APIConfig(BaseModel):
    """
    API 配置模型

    集中管理服务器、CORS、任务、文件上传等所有 API 相关配置。
    所有字段都有合理的默认值，可直接使用或通过环境变量覆盖。

    Requires:
        - Pydantic: 用于配置模型的类型校验和序列化。
        - FastAPI: 消耗此配置（docs_url, redoc_url, openapi_url）来配置 Swagger/ReDoc。

    Side Effects:
        - 无（纯数据模型，不产生副作用）
    """

    # === 服务器设置 ===
    host: str = "0.0.0.0"
    """服务器绑定的主机地址。默认: 0.0.0.0（监听所有接口）"""

    port: int = 8000
    """服务器绑定的端口号。默认: 8000"""

    reload: bool = False
    """是否启用自动重载（开发模式）。默认: False"""

    # === CORS 设置 ===
    cors_enabled: bool = True
    """是否启用 CORS 中间件。默认: True"""

    cors_origins: list[str] = ["*"]
    """CORS 允许的来源列表。默认: ["*"]（允许所有来源）"""

    # === 任务设置 ===
    max_concurrent_tasks: int = 5
    """最大并发任务数。默认: 5"""

    task_cleanup_interval: int = 3600
    """已完成任务的清理间隔（秒）。默认: 3600（每小时清理一次）"""

    task_retention_time: int = 86400
    """已完成任务的保留时间（秒）。默认: 86400（24 小时）"""

    # === 文件上传设置 ===
    max_upload_size: int = 100 * 1024 * 1024
    """文件上传的最大大小（字节）。默认: 100MB"""

    # === API 端点设置 ===
    api_prefix: str = "/api"
    """API 路由的统一前缀。默认: "/api" """

    docs_url: Optional[str] = "/docs"
    """Swagger UI 文档的 URL 路径。设为 None 可禁用。默认: "/docs" """

    redoc_url: Optional[str] = "/redoc"
    """ReDoc 文档的 URL 路径。设为 None 可禁用。默认: "/redoc" """

    openapi_url: Optional[str] = "/openapi.json"
    """OpenAPI Schema JSON 的 URL 路径。设为 None 可禁用。默认: "/openapi.json" """


# 全局配置实例
api_config = APIConfig()
