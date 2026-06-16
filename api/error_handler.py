"""
共享的 API 错误处理工具

将所有路由器中常见的内部异常统一映射为 HTTP 状态码，
避免重复的 try/except 样板代码。

用法::

    from api.error_handler import map_exception

    try:
        ...
    except HTTPException:
        raise  # 已经是 HTTPException，直接透传
    except Exception as e:
        raise map_exception(e, "video_generate")
"""

from fastapi import HTTPException
from loguru import logger


def map_exception(e: Exception, context: str = "") -> HTTPException:
    """
    将内部异常映射为合适的 HTTP 状态码，并自动记录日志

    映射规则:
        - ValueError / TypeError      → 400 Bad Request
        - FileNotFoundError           → 404 Not Found
        - PermissionError             → 403 Forbidden
        - NotImplementedError         → 501 Not Implemented
        - HTTPException（直接传入）      → 原样返回，不做转换
        - 其他所有异常                  → 500 Internal Server Error

    Args:
        e (Exception): 需要映射的原始异常对象。
        context (str): 错误发生的上下文标识（如 "video_generate"、"llm"）。
            会出现在日志消息中，方便定位问题。默认值: ""

    Returns:
        HTTPException: 对应的 HTTP 异常对象，可直接用 ``raise`` 抛出。
            如果是 HTTPException 类型，返回原始对象（不做转换）。

    Side Effects:
        - 通过 logger.opt(exception=e).error() 记录完整的堆栈跟踪日志
    """
    if isinstance(e, HTTPException):
        return e

    logger.opt(exception=e).error(f"API 错误 [{context}]: {e}")

    if isinstance(e, (ValueError, TypeError)):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, NotImplementedError):
        return HTTPException(status_code=501, detail=str(e))
    return HTTPException(status_code=500, detail="Internal server error")
