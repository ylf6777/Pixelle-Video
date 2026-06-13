"""
共享的 API 错误处理工具
所有路由器统一使用，将内部异常映射为合适的 HTTP 状态码
"""

from fastapi import HTTPException
from loguru import logger


def map_exception(e: Exception, context: str = "") -> HTTPException:
    """将内部异常映射为合适的 HTTP 状态码，并记录日志。

    - ValueError / TypeError → 400 Bad Request
    - FileNotFoundError → 404 Not Found
    - PermissionError → 403 Forbidden
    - NotImplementedError → 501 Not Implemented
    - 其他 → 500 Internal Server Error

    Usage:
        try:
            ...
        except HTTPException:
            raise
        except Exception as e:
            raise map_exception(e, "generate_video")
    """
    if isinstance(e, HTTPException):
        return e

    logger.opt(exception=e).error(f"API error [{context}]: {e}")

    if isinstance(e, (ValueError, TypeError)):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, NotImplementedError):
        return HTTPException(status_code=501, detail=str(e))
    return HTTPException(status_code=500, detail="Internal server error")
