"""
工作流执行器模块 — 定义抽象执行器接口及按来源路由的适配器骨架。

架构：
    WorkflowExecutor (ABC)
    ├── RunningHubExecutor   → 来源 "runninghub"
    ├── SelfhostExecutor     → 来源 "selfhost"
    ├── APIProviderExecutor  → 来源 "api"
    └── ZealmanExecutor      → 来源 "zealman"

    路由表 EXECUTORS 按来源字符串分发到对应适配器。

Usage::

    from web_ui.workflow_executor import EXECUTORS
    from web_ui.workflow_registry import workflow_registry

    wf = workflow_registry.get_by_id("image_flux")
    executor = EXECUTORS[wf.source]
    params = await executor.validate(wf, raw_params)
    task_id = await executor.execute(wf, params)
    status = await executor.get_progress(task_id)
"""

from abc import ABC, abstractmethod


class WorkflowExecutor(ABC):
    """
    工作流执行器抽象基类。

    定义 validate → execute → get_progress 三阶段生命周期。
    所有具体适配器必须实现这三个方法。

    职责边界：
        - 不负责参数校验逻辑（由子类实现）
        - 不负责持久化任务状态（由调用方管理）
        - 仅负责与外部系统的通信抽象
    """

    @abstractmethod
    async def validate(self, meta, params: dict) -> dict:
        """
        校验并规范化用户提交的参数。

        在 execute 之前调用，确保参数合法性。
        可在此阶段补全默认值、转换格式、校验必填项。

        Args:
            meta:   WorkflowMeta 实例 — 描述目标工作流。
            params: 用户提交的原始参数字典。

        Returns:
            校验/补全后的参数字典。校验失败应抛出异常。

        Raises:
            ValueError: 参数不合法或缺失必填字段时抛出。
            NotImplementedError: 子类未实现时抛出。
        """
        ...

    @abstractmethod
    async def execute(self, meta, params: dict) -> str:
        """
        向外部系统提交执行任务。

        提交成功后返回一个用于追踪进度的唯一任务 ID。

        Args:
            meta:   WorkflowMeta 实例 — 描述目标工作流。
            params: 经 validate 校验后的参数字典。

        Returns:
            str: 外部系统分配的任务 ID（用于 get_progress 查询）。

        Raises:
            ConnectionError:  与外部系统通信失败时抛出。
            RuntimeError:     提交被外部系统拒绝时抛出。
            NotImplementedError: 子类未实现时抛出。

        SideEffects:
            - 可能触发网络 I/O
            - 可能在外部系统创建异步任务
        """
        ...

    @abstractmethod
    async def get_progress(self, task_id: str) -> dict:
        """
        查询异步任务的当前进度与状态。

        Args:
            task_id: execute 返回的任务 ID。

        Returns:
            进度字典，至少包含以下字段::

                {
                    "progress": int,   # 0-100 进度百分比
                    "step": str,       # 当前步骤描述
                }

            任务完成时可额外包含::

                {
                    "status": "completed" | "failed" | "running",
                    "result_url": str,     # 结果文件 URL
                    "error": str,          # 失败时的错误信息
                }

        Raises:
            KeyError:          task_id 不存在于外部系统中。
            ConnectionError:   与外部系统通信失败。
            NotImplementedError: 子类未实现时抛出。
        """
        ...


# ────────────────────────────────────────────────────────────────
# 具体适配器实现（骨架 — 待接入实际 API 后完善）
# ────────────────────────────────────────────────────────────────


class RunningHubExecutor(WorkflowExecutor):
    """
    RunningHub 平台适配器。

    负责与 RunningHub API 通信，提交工作流并轮询任务状态。
    当前为骨架实现，所有方法返回占位值。

    Requires:
        - RunnningHub API 密钥配置
        - 网络可达 RunnningHub 服务端点
    """

    async def validate(self, meta, params: dict) -> dict:
        """
        校验 RunningHub 工作流参数。

        Args:
            meta:   WorkflowMeta 实例。
            params: 原始参数字典。

        Returns:
            原样返回 params（骨架实现）。

        Note:
            当前为骨架：直接返回原始参数，不做校验。
            接入实际 API 后需实现：必填字段检查、类型转换、默认值补全。
        """
        # TODO: 接入 RunningHub API 后实现参数校验逻辑
        return params

    async def execute(self, meta, params: dict) -> str:
        """
        向 RunningHub 提交工作流执行任务。

        Args:
            meta:   WorkflowMeta 实例。
            params: 校验后的参数字典。

        Returns:
            模拟的任务 ID，格式为 "rh_<workflow_id>"。

        SideEffects:
            - 无（骨架实现，无实际 I/O）
        """
        # TODO: 接入 RunningHub API 后实现实际任务提交
        return "rh_" + meta.id

    async def get_progress(self, task_id: str) -> dict:
        """
        查询 RunningHub 任务进度。

        Args:
            task_id: execute 返回的任务 ID。

        Returns:
            固定的占位进度字典 {"progress": 0, "step": ""}。
        """
        # TODO: 接入 RunningHub API 后实现实际进度轮询
        return {"progress": 0, "step": ""}


class SelfhostExecutor(WorkflowExecutor):
    """
    自托管 ComfyUI 适配器。

    负责与本机或内网 ComfyUI 实例通信，提交工作流并轮询任务状态。
    当前为骨架实现，所有方法返回占位值。

    Requires:
        - ComfyUI 服务地址配置
        - 网络可达自托管 ComfyUI 实例
    """

    async def validate(self, meta, params: dict) -> dict:
        """
        校验自托管工作流参数。

        Args:
            meta:   WorkflowMeta 实例。
            params: 原始参数字典。

        Returns:
            原样返回 params（骨架实现）。

        Note:
            当前为骨架：直接返回原始参数，不做校验。
            接入实际 ComfyUI API 后需实现：节点 ID 映射、prompt 注入、seed 处理等。
        """
        # TODO: 接入 ComfyUI API 后实现参数校验逻辑
        return params

    async def execute(self, meta, params: dict) -> str:
        """
        向自托管 ComfyUI 提交工作流执行任务。

        Args:
            meta:   WorkflowMeta 实例。
            params: 校验后的参数字典（应包含 ComfyUI prompt JSON）。

        Returns:
            模拟的任务 ID，格式为 "sh_<workflow_id>"。

        SideEffects:
            - 无（骨架实现，无实际 I/O）
        """
        # TODO: 接入 ComfyUI API 后实现实际任务提交
        return "sh_" + meta.id

    async def get_progress(self, task_id: str) -> dict:
        """
        查询自托管 ComfyUI 任务进度。

        Args:
            task_id: execute 返回的任务 ID（对应 ComfyUI 的 prompt_id）。

        Returns:
            固定的占位进度字典 {"progress": 0, "step": ""}。

        Note:
            接入后应调用 ComfyUI /history/{prompt_id} 或 /queue 端点。
        """
        # TODO: 接入 ComfyUI API 后实现实际进度轮询
        return {"progress": 0, "step": ""}


class APIProviderExecutor(WorkflowExecutor):
    """
    云 API 提供商适配器（即梦/Jimeng、Seedance 等）。

    负责与云端 AI 服务 API 通信，提交生成任务并轮询结果。
    当前为骨架实现，所有方法返回占位值。

    Requires:
        - API 密钥/Token 配置
        - 网络可达云 API 端点
    """

    async def validate(self, meta, params: dict) -> dict:
        """
        校验云 API 工作流参数。

        Args:
            meta:   WorkflowMeta 实例。
            params: 原始参数字典。

        Returns:
            原样返回 params（骨架实现）。

        Note:
            当前为骨架：直接返回原始参数，不做校验。
            接入实际云 API 后需实现：模型参数校验、图片转 base64、尺寸限制等。
        """
        # TODO: 接入云 API 后实现参数校验逻辑
        return params

    async def execute(self, meta, params: dict) -> str:
        """
        向云 API 提交生成任务。

        Args:
            meta:   WorkflowMeta 实例。
            params: 校验后的参数字典。

        Returns:
            模拟的任务 ID，格式为 "api_<workflow_id>"。

        SideEffects:
            - 无（骨架实现，无实际 I/O）
        """
        # TODO: 接入云 API 后实现实际任务提交
        return "api_" + meta.id

    async def get_progress(self, task_id: str) -> dict:
        """
        查询云 API 任务进度。

        Args:
            task_id: execute 返回的任务 ID。

        Returns:
            固定的占位进度字典 {"progress": 0, "step": ""}。

        Note:
            接入后应调用云 API 的任务状态查询端点。
        """
        # TODO: 接入云 API 后实现实际进度轮询
        return {"progress": 0, "step": ""}


class ZealmanExecutor(WorkflowExecutor):
    """
    Zealman 工作流适配器。

    负责与 Zealman ComfyUI 代理服务通信，提交工作流并轮询任务状态。
    当前为骨架实现，所有方法返回占位值。

    Requires:
        - Zealman 代理服务地址配置
        - 网络可达 Zealman 服务端点
    """

    async def validate(self, meta, params: dict) -> dict:
        """
        校验 Zealman 工作流参数。

        Args:
            meta:   WorkflowMeta 实例。
            params: 原始参数字典。

        Returns:
            原样返回 params（骨架实现）。

        Note:
            当前为骨架：直接返回原始参数，不做校验。
            接入实际 Zealman API 后需实现：key 映射、参数转换等。
        """
        # TODO: 接入 Zealman API 后实现参数校验逻辑
        return params

    async def execute(self, meta, params: dict) -> str:
        """
        向 Zealman 代理服务提交工作流执行任务。

        Args:
            meta:   WorkflowMeta 实例。
            params: 校验后的参数字典。

        Returns:
            模拟的任务 ID，格式为 "zm_<workflow_id>"。

        SideEffects:
            - 无（骨架实现，无实际 I/O）
        """
        # TODO: 接入 Zealman API 后实现实际任务提交
        return "zm_" + meta.id

    async def get_progress(self, task_id: str) -> dict:
        """
        查询 Zealman 任务进度。

        Args:
            task_id: execute 返回的任务 ID。

        Returns:
            固定的占位进度字典 {"progress": 0, "step": ""}。

        Note:
            接入后应调用 Zealman 的任务状态查询端点。
        """
        # TODO: 接入 Zealman API 后实现实际进度轮询
        return {"progress": 0, "step": ""}


# ────────────────────────────────────────────────────────────────
# 执行器路由表 — 按 WorkflowMeta.source 分发
# ────────────────────────────────────────────────────────────────

EXECUTORS: dict[str, WorkflowExecutor] = {
    "runninghub": RunningHubExecutor(),
    "selfhost": SelfhostExecutor(),
    "api": APIProviderExecutor(),
    "zealman": ZealmanExecutor(),
}
