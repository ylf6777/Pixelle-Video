"""
Zealman ComfyUI 镜像 API 客户端

直接调用 Zealman 镜像 8443 端口的 REST API，无需 SSH 隧道。
提供工作流提交、轮询结果、健康检查和 GPU 状态查询。

Requires:
    - urllib.request: 标准库 HTTP 客户端。
    - ssl: TLS/SSL 上下文（自签名证书环境需禁用证书校验）。
    - loguru.logger: 日志记录。

注意: 该类不使用 requests/httpx，使用标准库以最大化兼容性。
"""

import json
import time
import ssl
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from loguru import logger


class ZealmanClient:
    """
    Zealman ComfyUI 镜像 API 客户端

    通过 HTTPS 直接调用 Zealman 镜像的 REST API，支持:
    - 同步/异步工作流提交
    - 轮询查询生成结果
    - GPU 和 ComfyUI 状态检查
    - 本地图片转 base64 输入

    Requires:
        - Zealman 镜像服务运行中（默认端口 8443）。
        - 网络可达镜像地址。

    Side Effects:
        - 发送 HTTPS 请求（网络 I/O）。
        - 读取本地文件（image_to_input）。
    """

    def __init__(self, base_url: str):
        """
        初始化 Zealman 客户端

        Args:
            base_url (str): Zealman 镜像基础 URL。如 "https://192.168.1.1:8443"。

        Side Effects:
            - 创建 SSL 上下文（禁用证书校验，适配自签名证书环境）。
        """
        self.base_url = base_url.rstrip("/")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._ctx = ctx

    # ── 提交 + 轮询结果 ──────────────────────────────

    def generate(
        self,
        workflow: dict,
        input_values: dict,
        poll_interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> list[dict]:
        """
        提交工作流并同步等待生成完成

        Args:
            workflow (dict): ComfyUI 工作流 JSON（API 格式）。
            input_values (dict): 工作流输入参数键值对。
            poll_interval (float): 轮询间隔（秒）。默认 3.0。
            max_wait (float): 最大等待时间（秒）。默认 600.0（10 分钟）。

        Returns:
            list[dict]: 生成结果列表。超时返回空列表。

        Raises:
            RuntimeError: 提交失败或结果查询返回错误。

        Requires:
            - self._submit: POST 提交工作流。
            - self._wait: 轮询等待结果。

        Side Effects:
            - 发送多个 HTTPS 请求（提交 + 轮询）。
        """
        prompt_id = self._submit(workflow, input_values)
        return self._wait(prompt_id, poll_interval, max_wait)

    def generate_async(self, workflow: dict, input_values: dict) -> str:
        """
        异步提交工作流，立即返回 prompt_id

        Args:
            workflow (dict): ComfyUI 工作流 JSON。
            input_values (dict): 工作流输入参数。

        Returns:
            str: 用于后续查询结果的 prompt_id。

        Requires:
            - self._submit: POST 提交。

        Side Effects:
            - 发送 1 个 HTTPS 请求。
        """
        return self._submit(workflow, input_values)

    def get_result(self, prompt_id: str) -> list[dict]:
        """
        根据 prompt_id 查询生成结果（不等待）

        Args:
            prompt_id (str): generate_async 返回的 ID。

        Returns:
            list[dict]: 生成结果列表。仍在处理中时返回空列表。

        Requires:
            - self._wait: 底层轮询（poll_interval=0 不等待）。
        """
        return self._wait(prompt_id, poll_interval=0, max_wait=0)

    # ── 内部方法 ────────────────────────────────────

    def _submit(self, workflow: dict, input_values: dict) -> str:
        """
        POST /api/workflow/generate 提交工作流

        Args:
            workflow (dict): 工作流 JSON。
            input_values (dict): 输入参数。

        Returns:
            str: prompt_id。

        Raises:
            RuntimeError: 服务器返回 success=False 时抛出。

        Requires:
            - self._request: 统一 HTTP 请求处理。
        """
        data = json.dumps({
            "workflow_template": workflow,
            "input_values": input_values,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/workflow/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        resp = self._request(req)
        if not resp.get("success"):
            raise RuntimeError(f"zealman submit failed: {resp.get('error', resp)}")

        prompt_id = resp["prompt_id"]
        logger.info(f"zealman: submitted prompt_id={prompt_id}")
        return prompt_id

    def _wait(
        self, prompt_id: str, poll_interval: float, max_wait: float
    ) -> list[dict]:
        """
        轮询 GET /api/workflow/result 直到完成或超时

        Args:
            prompt_id (str): 任务 ID。
            poll_interval (float): 轮询间隔（秒）。
            max_wait (float): 最大等待时间（秒）。

        Returns:
            list[dict]: 结果列表。超时返回空列表。

        Raises:
            RuntimeError: 服务器返回 success=False 时抛出。

        Requires:
            - self._request: HTTP 请求处理。
            - time.sleep: 轮询间隔等待。
        """
        elapsed = 0.0
        while True:
            req = urllib.request.Request(
                f"{self.base_url}/api/workflow/result?prompt_id={prompt_id}"
            )
            resp = self._request(req)
            if not resp.get("success"):
                raise RuntimeError(f"zealman result error: {resp}")

            pending = resp.get("pending", True)
            results = resp.get("results", [])

            if not pending:
                return results

            if max_wait and elapsed >= max_wait:
                logger.warning(f"zealman: timeout waiting for {prompt_id}")
                return []

            time.sleep(poll_interval)
            elapsed += poll_interval

    def _request(self, req: urllib.request.Request) -> dict:
        """
        统一 HTTP 请求处理（含错误处理和日志）

        Args:
            req (urllib.request.Request): HTTP 请求对象。

        Returns:
            dict: JSON 响应字典。

        Raises:
            urllib.error.HTTPError: HTTP 错误状态码时向上抛出。

        Requires:
            - urllib.request.urlopen: 标准库 HTTP 客户端。
            - self._ctx: SSL 上下文。

        Side Effects:
            - 发送 HTTPS 请求。
            - 写入日志（error）。
        """
        try:
            with urllib.request.urlopen(req, timeout=60, context=self._ctx) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            logger.error(f"zealman HTTP {e.code}: {body[:500]}")
            raise

    # ── 辅助方法 ────────────────────────────────────

    @staticmethod
    def image_to_input(image_path: str) -> str:
        """
        将本地图片文件转换为 base64 data URL

        Args:
            image_path (str): 本地图片文件路径。

        Returns:
            str: "data:{mime};base64,{b64}" 格式的 data URL。

        Raises:
            FileNotFoundError: 文件不存在时抛出。

        Requires:
            - base64: 标准库 Base64 编码。
            - 文件系统读取权限。

        Side Effects:
            - 读取磁盘文件。
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        ext = path.suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def url_to_input(url: str) -> str:
        """
        URL 图片直接传入（Zealman 服务端自动下载）

        Args:
            url (str): 图片 URL。

        Returns:
            str: 原始 URL（透传）。
        """
        return url

    def health(self) -> dict:
        """
        健康检查

        GET /api/health

        Returns:
            dict: 健康状态响应。
        """
        return self._request(urllib.request.Request(f"{self.base_url}/api/health"))

    def gpu_info(self) -> dict:
        """
        查询 GPU 信息

        GET /api/gpu/info

        Returns:
            dict: GPU 信息响应。
        """
        return self._request(urllib.request.Request(f"{self.base_url}/api/gpu/info"))

    def comfy_status(self) -> dict:
        """
        查询 ComfyUI 运行状态

        GET /api/comfy/status

        Returns:
            dict: ComfyUI 状态响应。
        """
        return self._request(urllib.request.Request(f"{self.base_url}/api/comfy/status"))

    def start_comfy(self, use_proxy: bool = True) -> dict:
        """
        启动 ComfyUI 服务

        POST /api/comfy/start

        Args:
            use_proxy (bool): 是否使用代理。默认 True。

        Returns:
            dict: 启动结果响应。
        """
        data = json.dumps({"useProxy": use_proxy}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/comfy/start",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return self._request(req)
