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
LLM utility functions for model discovery and connection testing.

Uses the OpenAI-compatible models endpoint to fetch available models
and verify API connectivity with Bearer token authentication.
"""

import re
from typing import List, Tuple
import httpx
from loguru import logger


def _build_models_url(base_url: str) -> str:
    """从用户输入的 API Base URL 构建 /models 端点。

    处理多种 URL 格式：
    - 已包含 /models 后缀的直接返回
    - 含 /v1 等版本号的追加 /models
    - 其他情况追加 /v1/models

    Args:
        base_url: 用户输入的 API 基础 URL

    Returns:
        构建好的完整 /models 端点 URL

    Requires:
        无（纯函数）

    Side Effects:
        无
    """
    raw = (base_url or "").strip().rstrip("/")
    if raw.endswith("/models"):
        return raw

    normalized = normalize_openai_base_url(base_url)

    if re.search(r"/v\d+(?:\.\d+)?$", normalized):
        return f"{normalized}/models"

    return f"{normalized}/v1/models"


def normalize_openai_base_url(base_url: str) -> str:
    """规范化用户输入的 OpenAI 兼容 Base URL。

    用户有时会粘贴具体的端点路径（如 /chat/completions 或 /models），
    OpenAI SDK 期望的是 API 根路径，因此需要剥离具体的端点后缀。

    Args:
        base_url: 用户输入的 API URL（可能包含具体端点路径）

    Returns:
        规范化后的 API 根 URL（去除尾部斜杠和已知端点后缀）

    Requires:
        无（纯函数）

    Side Effects:
        无
    """
    normalized = (base_url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/responses", "/models"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].rstrip("/")
            break
    return normalized


def fetch_available_models(api_key: str, base_url: str, timeout: float = 10.0) -> List[str]:
    """
    从 OpenAI 兼容 API 端点获取可用模型列表。

    使用 Bearer token 认证方式调用 /models 端点，返回按名称排序的模型 ID 列表。

    Args:
        api_key: API 认证密钥
        base_url: API 基础 URL（如 https://api.openai.com/v1），会自动规范化
        timeout: HTTP 请求超时时间（秒），默认 10.0

    Returns:
        按字母排序的模型 ID 列表

    Raises:
        httpx.HTTPStatusError: API 返回错误状态码
        httpx.RequestError: 网络连接错误

    Requires:
        - api_key 为非空字符串
        - base_url 为有效的 HTTP(S) URL

    Side Effects:
        - 发起 HTTP GET 请求到 /models 端点
        - 输出 debug 级别日志
    """
    models_url = _build_models_url(base_url)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.debug(f"Fetching models from: {models_url}")

    with httpx.Client(timeout=timeout) as client:
        response = client.get(models_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        models = [model["id"] for model in data.get("data", [])]

        # Sort models alphabetically for better UX
        models.sort()

        logger.debug(f"Fetched {len(models)} models")
        return models


def test_llm_connection(api_key: str, base_url: str, timeout: float = 10.0) -> Tuple[bool, str, int]:
    """
    测试 LLM API 连接是否可用。

    通过调用 /models 端点来验证连接。对常见错误码（401/403/404）提供
    友好的人类可读提示信息。

    Args:
        api_key: API 认证密钥
        base_url: API 基础 URL
        timeout: HTTP 请求超时时间（秒），默认 10.0

    Returns:
        (success, message, model_count) 三元组：
        - success (bool): True 表示连接成功
        - message (str): 人类可读的状态描述
        - model_count (int): 可用模型数量，失败时为 0

    Raises:
        无（所有异常在内部捕获并转换为 False 返回）

    Requires:
        - api_key 为非空字符串
        - base_url 为有效的 HTTP(S) URL

    Side Effects:
        - 发起 HTTP GET 请求到 /models 端点
        - 输出 debug/error 级别日志
    """
    try:
        models = fetch_available_models(api_key, base_url, timeout)
        return True, f"Connection successful! {len(models)} models available.", len(models)
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 401:
            return False, "Authentication failed: Invalid API Key", 0
        elif status_code == 403:
            return False, "Access forbidden: Check your API Key permissions", 0
        elif status_code == 404:
            return False, "API endpoint not found: Check your Base URL", 0
        else:
            return False, f"API error: HTTP {status_code}", 0
    except httpx.ConnectError:
        return False, "Connection failed: Cannot reach the server", 0
    except httpx.TimeoutException:
        return False, "Connection timeout: Server did not respond in time", 0
    except Exception as e:
        logger.error(f"LLM connection test error: {e}")
        return False, f"Error: {str(e)}", 0
