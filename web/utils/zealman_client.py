"""
zealman ComfyUI 镜像 API 客户端
直接调用 8443 端口的 REST API，无需 SSH 隧道
"""
import json, time, ssl, base64
import urllib.request
from pathlib import Path
from typing import Optional
from loguru import logger


class ZealmanClient:
    """zealman 镜像 API 客户端"""

    def __init__(self, base_url: str):
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
        """提交工作流并等待生成完成，返回 results 列表"""
        prompt_id = self._submit(workflow, input_values)
        return self._wait(prompt_id, poll_interval, max_wait)

    def generate_async(self, workflow: dict, input_values: dict) -> str:
        """提交工作流，立即返回 prompt_id（不等待）"""
        return self._submit(workflow, input_values)

    def get_result(self, prompt_id: str) -> list[dict]:
        """根据 prompt_id 查询结果"""
        return self._wait(prompt_id, poll_interval=0, max_wait=0)

    # ── 内部方法 ────────────────────────────────────

    def _submit(self, workflow: dict, input_values: dict) -> str:
        """POST /api/workflow/generate"""
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

    def _wait(self, prompt_id: str, poll_interval: float, max_wait: float) -> list[dict]:
        """GET /api/workflow/result 轮询直到完成或超时"""
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
        """统一请求处理"""
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
        """本地图片转 base64 data URL"""
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
        """URL 图片直接传入（zealman 自动下载）"""
        return url

    def health(self) -> dict:
        """GET /api/health"""
        return self._request(urllib.request.Request(f"{self.base_url}/api/health"))

    def gpu_info(self) -> dict:
        """GET /api/gpu/info"""
        return self._request(urllib.request.Request(f"{self.base_url}/api/gpu/info"))

    def comfy_status(self) -> dict:
        """GET /api/comfy/status"""
        return self._request(urllib.request.Request(f"{self.base_url}/api/comfy/status"))

    def start_comfy(self, use_proxy: bool = True) -> dict:
        """POST /api/comfy/start"""
        data = json.dumps({"useProxy": use_proxy}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/comfy/start",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return self._request(req)
