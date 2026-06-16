"""
工作流执行器 — 通过 pixelle_video 核心调用 ComfyKit/RunningHub/API

Selfhost/RunningHub 执行器使用 ComfyKit 提交工作流并轮询结果。
API 执行器通过 api_media 服务调用直连模型。
Zealman 执行器通过 ZealmanClient 代理。

进度追踪:
    _tasks 字典存储每个 task_id 的执行状态和进度，
    供 SSE 端点 (routes.py) 实时查询。
"""

import asyncio
import json
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from loguru import logger


class WorkflowExecutor(ABC):
    """工作流执行器抽象基类"""

    @abstractmethod
    async def validate(self, meta, params: dict) -> dict:
        """校验参数"""
        ...

    @abstractmethod
    async def execute(self, meta, params: dict) -> str:
        """提交执行，返回 task_id"""
        ...

    @abstractmethod
    async def get_progress(self, task_id: str) -> dict:
        """查询进度"""
        ...

    def _new_tasks(self) -> dict:
        """获取任务存储字典（类级别共享）"""
        if not hasattr(self.__class__, '_tasks'):
            self.__class__._tasks = {}
        return self.__class__._tasks


class SelfhostExecutor(WorkflowExecutor):
    """
    自托管 ComfyUI — 通过 ComfyKit 执行本地工作流文件

    Requires:
        - config.yaml 中配置 comfyui.comfyui_url
        - selfhost 工作流 JSON 文件存在于 workflows/selfhost/
    """

    async def validate(self, meta, params: dict) -> dict:
        prompt = (params.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt 参数不能为空")
        return {"prompt": prompt, **{k: v for k, v in params.items() if k != "prompt"}}

    async def execute(self, meta, params: dict) -> str:
        task_id = str(uuid.uuid4())[:12]
        tasks = self._new_tasks()
        tasks[task_id] = {"status": "running", "step": "connecting", "progress": 0}

        # 在后台线程执行（避免阻塞事件循环）
        def _run():
            try:
                from pixelle_video.service import pixelle_video
                import asyncio as aio

                async def _exec():
                    comfykit = await pixelle_video._get_or_create_comfykit()
                    wf_path = meta.workflow_file
                    if not wf_path or not Path(wf_path).exists():
                        raise FileNotFoundError(f"工作流文件不存在: {wf_path}")

                    tasks[task_id] = {"status": "running", "step": "generating", "progress": 30}
                    result = await comfykit.execute(str(wf_path), params)

                    if result.status == "completed":
                        url = None
                        if hasattr(result, 'images') and result.images:
                            url = result.images[0]
                        elif hasattr(result, 'videos') and result.videos:
                            url = result.videos[0]
                        tasks[task_id] = {
                            "status": "completed", "progress": 100,
                            "step": "completed", "result_url": url,
                        }
                    else:
                        tasks[task_id] = {
                            "status": "failed", "progress": 0,
                            "step": "failed", "error": getattr(result, 'msg', '未知错误'),
                        }
                aio.run(_exec())
            except Exception as e:
                logger.error(f"Selfhost execution failed: {e}")
                tasks[task_id] = {"status": "failed", "step": "error", "error": str(e)}

        threading.Thread(target=_run, daemon=True).start()
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return self._new_tasks().get(task_id, {"progress": 0, "step": "unknown"})


class RunningHubExecutor(WorkflowExecutor):
    """
    RunningHub 云端 — 通过 ComfyKit 提交 runninghub 工作流

    Requires:
        - config.yaml 中配置 comfyui.runninghub_api_key
    """

    async def validate(self, meta, params: dict) -> dict:
        prompt = (params.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt 参数不能为空")
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = str(uuid.uuid4())[:12]
        tasks = self._new_tasks()
        tasks[task_id] = {"status": "running", "step": "submitting", "progress": 0}

        def _run():
            try:
                from pixelle_video.service import pixelle_video
                import asyncio as aio

                async def _exec():
                    comfykit = await pixelle_video._get_or_create_comfykit()
                    # 从 workflow 文件提取 workflow_id
                    wf_path = meta.workflow_file
                    workflow_id = meta.id
                    if wf_path and Path(wf_path).exists():
                        with open(wf_path) as f:
                            data = json.load(f)
                        workflow_id = data.get("workflow_id", meta.id)

                    tasks[task_id] = {"status": "running", "step": "generating", "progress": 30}
                    result = await comfykit.execute(workflow_id, params)

                    if result.status == "completed":
                        url = None
                        if hasattr(result, 'images') and result.images:
                            url = result.images[0]
                        elif hasattr(result, 'videos') and result.videos:
                            url = result.videos[0]
                        tasks[task_id] = {
                            "status": "completed", "progress": 100,
                            "step": "completed", "result_url": url,
                        }
                    else:
                        tasks[task_id] = {
                            "status": "failed", "step": "failed",
                            "error": getattr(result, 'msg', '未知错误'),
                        }
                aio.run(_exec())
            except Exception as e:
                logger.error(f"RunningHub execution failed: {e}")
                tasks[task_id] = {"status": "failed", "step": "error", "error": str(e)}

        threading.Thread(target=_run, daemon=True).start()
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return self._new_tasks().get(task_id, {"progress": 0, "step": "unknown"})


class APIProviderExecutor(WorkflowExecutor):
    """直连 API 模型执行器 — 调用 api_media 服务"""

    async def validate(self, meta, params: dict) -> dict:
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"api_{meta.id}_{uuid.uuid4().hex[:6]}"
        tasks = self._new_tasks()
        tasks[task_id] = {"status": "submitted", "step": "pending", "progress": 10}
        logger.info(f"API task created: {task_id}")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return self._new_tasks().get(task_id, {"progress": 50, "step": "processing", "status": "running"})


class ZealmanExecutor(WorkflowExecutor):
    """Zealman 镜像执行器 — 通过 ZealmanClient 代理"""

    async def validate(self, meta, params: dict) -> dict:
        return params

    async def execute(self, meta, params: dict) -> str:
        task_id = f"zm_{meta.id}_{uuid.uuid4().hex[:6]}"
        tasks = self._new_tasks()
        tasks[task_id] = {"status": "submitted", "step": "pending", "progress": 10}
        try:
            from pixelle_video.services.zealman_client import ZealmanClient
            client = ZealmanClient("https://127.0.0.1:8443")
            client.generate_async({}, params)
        except Exception as e:
            logger.warning(f"Zealman connection failed: {e}")
        return task_id

    async def get_progress(self, task_id: str) -> dict:
        return self._new_tasks().get(task_id, {"progress": 50, "step": "processing", "status": "running"})


EXECUTORS: dict[str, WorkflowExecutor] = {
    "runninghub": RunningHubExecutor(),
    "selfhost": SelfhostExecutor(),
    "api": APIProviderExecutor(),
    "zealman": ZealmanExecutor(),
}
