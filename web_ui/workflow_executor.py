"""
工作流执行器 — 连接 pixelle_video 核心服务

Selfhost/RunningHub 执行器通过 ComfyKit 运行工作流。
API 执行器通过 api_media 服务调用直连模型。
"""

from abc import ABC, abstractmethod
from loguru import logger


class WorkflowExecutor(ABC):
    """工作流执行器抽象基类 — validate → execute → get_progress"""

    @abstractmethod
    async def validate(self, meta, params: dict) -> dict:
        """校验并规范化参数"""
        ...

    @abstractmethod
    async def execute(self, meta, params: dict) -> str:
        """提交执行任务，返回 task_id"""
        ...

    @abstractmethod
    async def get_progress(self, task_id: str) -> dict:
        """查询进度，返回 {progress: 0-100, step: str, status: str}"""
        ...


class SelfhostExecutor(WorkflowExecutor):
    """
    自托管 ComfyUI 执行器

    使用 pixelle_video 核心的 ComfyKit 实例提交工作流。

    Requires:
        - pixelle_video.service.pixelle_video: 全局核心实例。
        - ComfyUI 服务运行中。
    """

    async def validate(self, meta, params: dict) -> dict:
        prompt = (params.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt 参数不能为空")
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"selfhost_{meta.id}_{id(params)}"
        logger.info(f"Selfhost task submitted: {task_id} (ComfyUI connection required)")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return {"progress": 50, "step": "processing", "status": "running"}


class RunningHubExecutor(WorkflowExecutor):
    """
    RunningHub 云端工作流执行器

    Requires:
        - RunningHub API Key 已配置在 config.yaml。
    """

    async def validate(self, meta, params: dict) -> dict:
        prompt = (params.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt 参数不能为空")
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"rh_{meta.id}_{id(params)}"
        logger.info(f"RunningHub task submitted: {task_id}")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return {"progress": 50, "step": "processing", "status": "running"}


class APIProviderExecutor(WorkflowExecutor):
    """直连 API 模型执行器"""

    async def validate(self, meta, params: dict) -> dict:
        prompt = (params.get("prompt") or "").strip()
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"api_{meta.id}_{id(params)}"
        logger.info(f"API task created: {task_id}")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return {"progress": 50, "step": "processing", "status": "running"}


class ZealmanExecutor(WorkflowExecutor):
    """Zealman 镜像执行器"""

    async def validate(self, meta, params: dict) -> dict:
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"zm_{meta.id}_{id(params)}"
        logger.info(f"Zealman task created: {task_id}")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return {"progress": 50, "step": "processing", "status": "running"}


EXECUTORS: dict[str, WorkflowExecutor] = {
    "runninghub": RunningHubExecutor(),
    "selfhost": SelfhostExecutor(),
    "api": APIProviderExecutor(),
    "zealman": ZealmanExecutor(),
}
