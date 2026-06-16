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
健康检查端点

提供服务存活检测和版本查询接口。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """
    健康检查响应模型

    Attributes:
        status (str): 服务状态。正常时为 "healthy"
        version (str): API 版本号，格式 "major.minor.patch"
        service (str): 服务名称标识
    """
    status: str = "healthy"
    version: str = "0.1.0"
    service: str = "ylf_Video API"


class CapabilitiesResponse(BaseModel):
    """
    能力查询响应模型

    Attributes:
        success (bool): 请求是否成功
        capabilities (dict): 系统可用能力的键值对描述
    """
    success: bool = True
    capabilities: dict


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查端点

    用于负载均衡器、容器编排系统和监控工具检测服务是否存活。

    Returns:
        HealthResponse: 包含服务状态和版本信息的响应。

    Raises:
        无 — 此端点不产生异常，始终返回健康状态。

    Side Effects:
        - 无（纯查询端点）
    """
    return HealthResponse()


@router.get("/version", response_model=HealthResponse)
async def get_version():
    """
    获取 API 版本号

    Returns:
        HealthResponse: 包含版本信息的响应。当前版本固定为 0.1.0。

    Side Effects:
        - 无（纯查询端点）
    """
    return HealthResponse()
