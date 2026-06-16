"""
Web 安全模块 — 速率限制、上传校验、CSP、异常监控

提供可复用的安全中间件和工具函数，保护 API 端点免受滥用。
所有组件通过 api/app.py 集成，无需修改业务逻辑。

安全层次:
    1. 速率限制 — 防止 API 滥用和资源耗尽
    2. 文件上传校验 — 类型白名单 + 大小限制
    3. CSP Header — 限制浏览器可加载的资源来源
    4. 异常监控 — 统一错误日志和请求追踪
"""

import time
import uuid
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


# ==================== 速率限制 ====================

class RateLimiter:
    """
    基于内存的令牌桶速率限制器

    按客户端 IP 追踪请求频率，超过限制返回 429。
    生产环境建议替换为 Redis 实现。

    Requires:
        - 无外部依赖。纯内存实现。

    Side Effects:
        - 修改内存中的请求计数字典（有内存增长风险，
          生产环境需定期清理过期条目）。
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """
        Args:
            max_requests (int): 时间窗口内允许的最大请求数。默认 60。
            window_seconds (int): 时间窗口（秒）。默认 60。
        """
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """
        检查指定 key 是否在速率限制内

        Args:
            key (str): 客户端标识（通常为 IP 地址）。

        Returns:
            bool: 允许通过返回 True，超限返回 False。
        """
        now = time.time()
        bucket = self._buckets[key]

        # 清理过期的时间戳
        cutoff = now - self.window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self.max_requests:
            return False

        bucket.append(now)
        return True

    def remaining(self, key: str) -> int:
        """返回剩余可用请求数"""
        cutoff = time.time() - self.window
        self._buckets[key][:] = [t for t in self._buckets.get(key, []) if t > cutoff]
        return max(0, self.max_requests - len(self._buckets.get(key, [])))


# 预定义限流器
global_limiter = RateLimiter(max_requests=120, window_seconds=60)     # 全局 120/分钟
execute_limiter = RateLimiter(max_requests=5, window_seconds=60)      # 执行 5/分钟
preview_limiter = RateLimiter(max_requests=20, window_seconds=60)     # 预览 20/分钟


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    全局速率限制中间件

    对所有 API 请求施加速率限制，通过 X-RateLimit-* 头告知状态。

    Requires:
        - global_limiter: 全局 RateLimiter 实例。

    Side Effects:
        - 修改内存中的请求计数。
        - 超限时返回 429 响应。
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        if not global_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(global_limiter.remaining(client_ip))
        response.headers["X-RateLimit-Limit"] = str(global_limiter.max_requests)
        return response


def rate_limit_execute(request: Request) -> None:
    """
    执行端点专用速率限制

    在路由处理函数中调用，超限抛出 HTTPException(429)。

    Raises:
        HTTPException(429): 执行频率超限。
    """
    ip = request.client.host if request.client else "unknown"
    if not execute_limiter.is_allowed(ip):
        raise HTTPException(
            429,
            detail="执行请求过于频繁，每分钟最多 5 次。请稍后再试",
            headers={"Retry-After": "60"},
        )


# ==================== 文件上传校验 ====================

ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/flac", "audio/ogg", "audio/mp4"}
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


def validate_upload(
    file: UploadFile,
    allowed_types: set[str],
    max_size: int = MAX_UPLOAD_SIZE,
) -> None:
    """
    校验上传文件的类型和大小

    Args:
        file (UploadFile): FastAPI 上传文件对象。
        allowed_types (set[str]): 允许的 MIME 类型集合。
        max_size (int): 最大文件大小（字节）。默认 50MB。

    Raises:
        HTTPException(415): MIME 类型不在白名单中。
        HTTPException(413): 文件超过大小限制。

    Requires:
        - 文件对象的 content_type 和 size 属性。
    """
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            415,
            f"不支持的文件类型: {file.content_type}。"
            f"允许: {', '.join(sorted(allowed_types))}",
        )

    # FastAPI/Starlette 的 UploadFile 在 SpooledTemporaryFile 模式下
    # 需要先读取才能获取准确大小。此处检查 file size 属性（如果可用）。
    if hasattr(file, "size") and file.size is not None and file.size > max_size:
        raise HTTPException(
            413,
            f"文件大小超过限制 ({max_size // (1024*1024)}MB)",
        )


# ==================== CSP Header ====================

class CSPMiddleware(BaseHTTPMiddleware):
    """
    Content-Security-Policy 中间件

    限制浏览器可加载的脚本、样式、字体和媒体资源来源。
    仅对 HTML 响应添加 CSP header。

    Requires:
        - 无外部依赖。
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "media-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = self.CSP_POLICY
        return response


# ==================== 异常监控 ====================

class ErrorMonitoringMiddleware(BaseHTTPMiddleware):
    """
    异常监控中间件

    捕获未处理的异常，分配 request_id，记录结构化日志，
    返回统一的 500 错误响应（不泄露内部细节）。

    Requires:
        - loguru.logger: 结构化日志记录。

    Side Effects:
        - 写入错误日志（含完整 traceback）。
        - 修改响应的 X-Request-ID header。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            logger.opt(exception=True).error(
                "[{request_id}] {method} {path} — {error}",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "request_id": request_id,
                    "message": "服务器内部错误，请稍后重试",
                },
                headers={"X-Request-ID": request_id},
            )
