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
配置管理器 — 单例模式

提供统一的配置访问、更新、保存、重载接口。
ConfigManager 是全局唯一入口，维护 PixelleVideoConfig 的完整生命周期。

设计原则:
    - 单例：整个应用共享一个 ConfigManager 实例
    - 延迟校验：仅在 load/update 时创建 Pydantic 模型，访问时直接读属性
    - 深度合并：update() 递归合并嵌套字典，保留未修改的字段
"""

from pathlib import Path
from typing import Any, Optional
from loguru import logger
from .schema import PixelleVideoConfig
from .loader import load_config_dict, save_config_dict


def _deep_merge(base: dict, updates: dict) -> dict:
    """
    递归深度合并两个字典

    对 updates 中的每个 key：
    - 如果 base 和 updates 的值都是 dict → 递归合并
    - 否则 → updates 的值直接覆盖 base

    Args:
        base (dict): 基础字典（会被修改）。
        updates (dict): 要合并的更新字典。

    Returns:
        dict: 合并后的 base 字典（原地修改 + 返回）。

    Requires:
        - 无外部依赖。

    Side Effects:
        - 修改 base 字典（原地操作）。

    Examples:
        >>> base = {"a": 1, "b": {"x": 1}}
        >>> updates = {"b": {"y": 2}, "c": 3}
        >>> _deep_merge(base, updates)
        {"a": 1, "b": {"x": 1, "y": 2}, "c": 3}
    """
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class ConfigManager:
    """
    配置管理器（单例）

    提供统一的配置访问、更新、保存、重载接口。整个应用只存在一个
    实例，通过 ConfigManager() 获取同一对象。

    Requires:
        - pixelle_video.config.schema: Pydantic 配置模型。
        - pixelle_video.config.loader: YAML 读写函数。
        - pixelle_video.utils.template_util.resolve_template_path: 模板路径校验。

    Side Effects:
        - 首次实例化时读取 config.yaml 文件。
        - save() 写入 config.yaml 文件。
        - reload() 重新读取 config.yaml。

    Examples:
        >>> cm = ConfigManager()
        >>> cm.config.llm.model
        'qwen-max'
        >>> cm.update({"llm": {"model": "gpt-4o"}})
        >>> cm.save()
    """

    _instance: Optional['ConfigManager'] = None

    def __new__(cls, config_path: str = "config.yaml") -> 'ConfigManager':
        """
        单例构造：全局只创建一个实例

        Args:
            config_path (str): YAML 配置文件路径。仅首次调用时使用。

        Returns:
            ConfigManager: 全局唯一实例。
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置管理器（仅首次执行）

        Args:
            config_path (str): YAML 配置文件路径。默认: "config.yaml"

        Side Effects:
            - 读取磁盘上的 config.yaml 文件。
            - 设置 self._initialized 防止重复初始化。
        """
        if hasattr(self, '_initialized'):
            return

        self.config_path = Path(config_path)
        self.config: PixelleVideoConfig = self._load()
        self._initialized = True

    def _load(self) -> PixelleVideoConfig:
        """
        从 YAML 文件加载并构建校验后的配置对象

        Returns:
            PixelleVideoConfig: 校验后的 Pydantic 配置对象。

        Requires:
            - load_config_dict: 从 YAML 读取原始字典。
            - PixelleVideoConfig: Pydantic 模型构造。

        Side Effects:
            - 读取磁盘文件。
            - 校验模板路径（_validate_template）。
        """
        data = load_config_dict(str(self.config_path))
        config = PixelleVideoConfig(**data)
        self._validate_template(config.template.default_template)
        return config

    def _validate_template(self, template_path: str) -> None:
        """
        校验配置的默认模板路径是否存在

        模板不存在时仅记录警告，不阻止启动（运行时可能使用其他模板）。

        Args:
            template_path (str): 待校验的模板路径。

        Requires:
            - pixelle_video.utils.template_util.resolve_template_path: 模板路径解析。

        Side Effects:
            - 写入日志（debug/warning）。
        """
        from pixelle_video.utils.template_util import resolve_template_path

        try:
            resolved_path = resolve_template_path(template_path)
            logger.debug(f"Template validation passed: {template_path} -> {resolved_path}")
        except FileNotFoundError as e:
            logger.warning(
                f"Configured default template '{template_path}' not found. "
                f"Will fall back to '1080x1920/default.html' if needed. Error: {e}"
            )

    def reload(self) -> None:
        """
        重新从 YAML 文件加载配置

        用于热重载场景（如 Web UI 保存配置后刷新）。

        Requires:
            - self._load(): 读取并校验 YAML 文件。

        Side Effects:
            - 读取磁盘文件。
            - 覆盖 self.config。
        """
        self.config = self._load()
        logger.info("Configuration reloaded")

    def save(self) -> None:
        """
        将当前配置保存到 YAML 文件

        Requires:
            - save_config_dict: YAML 写入函数。
            - PixelleVideoConfig.to_dict(): 模型序列化。

        Side Effects:
            - 覆盖写入 config.yaml 文件。
        """
        save_config_dict(self.config.to_dict(), str(self.config_path))

    def update(self, updates: dict) -> None:
        """
        深度合并更新配置

        将 updates 合并到当前配置中：嵌套字典递归合并，非字典值直接覆盖。
        合并后重建 Pydantic 模型以触发校验。

        Args:
            updates (dict): 要合并的配置更新。支持嵌套结构。

        Raises:
            pydantic.ValidationError: 合并后的数据不符合 Schema 时抛出。

        Requires:
            - _deep_merge: 递归字典合并函数。
            - PixelleVideoConfig: Pydantic 模型重建。

        Side Effects:
            - 修改 self.config（替换为新对象）。

        Examples:
            >>> cm.update({"llm": {"api_key": "sk-xxx", "model": "gpt-4o"}})
            >>> cm.update({"comfyui": {"comfyui_url": "http://192.168.1.1:8188"}})
        """
        current = self.config.to_dict()
        merged = _deep_merge(current, updates)
        self.config = PixelleVideoConfig(**merged)

    def get(self, key: str, default: Any = None) -> Any:
        """
        字典式配置访问（向后兼容旧代码）

        Args:
            key (str): 配置键名（顶层 key）。
            default (Any): key 不存在时的默认值。

        Returns:
            Any: 配置值，或 default。

        Requires:
            - PixelleVideoConfig.to_dict(): 序列化为字典。

        Examples:
            >>> cm.get("project_name")
            "Pixelle-Video"
        """
        return self.config.to_dict().get(key, default)

    def validate(self) -> bool:
        """
        验证配置完整性

        Returns:
            bool: 所有必要配置项均有效时返回 True。

        Requires:
            - PixelleVideoConfig.validate_required: 必要项检查。
        """
        return self.config.validate_required()

    # ==================== LLM 配置 ====================

    def get_llm_config(self) -> dict:
        """
        获取 LLM 配置字典

        Returns:
            dict: {"api_key": str, "base_url": str, "model": str}

        Requires:
            - 无外部依赖。纯属性读取。
        """
        return {
            "api_key": self.config.llm.api_key,
            "base_url": self.config.llm.base_url,
            "model": self.config.llm.model,
        }

    def set_llm_config(self, api_key: str, base_url: str, model: str) -> None:
        """
        设置 LLM 配置并自动规范化 base_url

        Args:
            api_key (str): LLM API 密钥。
            base_url (str): API 端点地址。自动规范化（补全 /v1 后缀等）。
            model (str): 模型名称。

        Requires:
            - pixelle_video.utils.llm_util.normalize_openai_base_url: URL 规范化。

        Side Effects:
            - 修改 self.config.llm。
        """
        from pixelle_video.utils.llm_util import normalize_openai_base_url

        self.update({
            "llm": {
                "api_key": api_key,
                "base_url": normalize_openai_base_url(base_url),
                "model": model,
            }
        })

    # ==================== ComfyUI 配置 ====================

    def get_comfyui_config(self) -> dict:
        """
        获取 ComfyUI 及子服务完整配置字典

        Returns:
            dict: 包含 comfyui_url, api_key, runninghub 配置及各子服务默认值。

        Requires:
            - 无外部依赖。纯属性读取。
        """
        return {
            "comfyui_url": self.config.comfyui.comfyui_url,
            "comfyui_api_key": self.config.comfyui.comfyui_api_key,
            "runninghub_api_key": self.config.comfyui.runninghub_api_key,
            "runninghub_concurrent_limit": self.config.comfyui.runninghub_concurrent_limit,
            "runninghub_instance_type": self.config.comfyui.runninghub_instance_type,
            "tts": {
                "default_workflow": self.config.comfyui.tts.default_workflow,
            },
            "image": {
                "default_workflow": self.config.comfyui.image.default_workflow,
                "prompt_prefix": self.config.comfyui.image.prompt_prefix,
            },
            "video": {
                "default_workflow": self.config.comfyui.video.default_workflow,
                "prompt_prefix": self.config.comfyui.video.prompt_prefix,
            }
        }

    def set_comfyui_config(
        self,
        comfyui_url: Optional[str] = None,
        comfyui_api_key: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        runninghub_concurrent_limit: Optional[int] = None,
        runninghub_instance_type: Optional[str] = None
    ) -> None:
        """
        设置 ComfyUI 全局连接配置

        仅更新传入的非 None 参数，其余保持不变。

        Args:
            comfyui_url (Optional[str]): ComfyUI 服务地址。
            comfyui_api_key (Optional[str]): ComfyUI API Key。
            runninghub_api_key (Optional[str]): RunningHub API Key。
            runninghub_concurrent_limit (Optional[int]): 并发执行上限（1-10）。
            runninghub_instance_type (Optional[str]): 实例类型。空字符串表示清除。

        Requires:
            - self.update: 深度合并配置。

        Side Effects:
            - 修改 self.config.comfyui 的对应字段。
        """
        updates = {}
        if comfyui_url is not None:
            updates["comfyui_url"] = comfyui_url
        if comfyui_api_key is not None:
            updates["comfyui_api_key"] = comfyui_api_key
        if runninghub_api_key is not None:
            updates["runninghub_api_key"] = runninghub_api_key
        if runninghub_concurrent_limit is not None:
            updates["runninghub_concurrent_limit"] = runninghub_concurrent_limit
        if runninghub_instance_type is not None:
            updates["runninghub_instance_type"] = (
                runninghub_instance_type if runninghub_instance_type else None
            )

        if updates:
            self.update({"comfyui": updates})

    # ==================== API Provider 配置 ====================

    def get_api_providers_config(self) -> dict:
        """
        获取所有直连 API 供应商的配置字典

        Returns:
            dict: APIProvidersConfig 的完整字典表示。

        Requires:
            - 无外部依赖。纯属性读取。
        """
        return self.config.api_providers.model_dump()

    def set_api_provider_config(self, provider: str, updates: dict) -> None:
        """
        设置指定供应商的配置

        Args:
            provider (str): 供应商名称。如 "openai", "dashscope", "kling"。
            updates (dict): 要更新的配置字段。

        Requires:
            - self.update: 深度合并配置。

        Side Effects:
            - 修改 self.config.api_providers.<provider> 的对应字段。
        """
        self.update({"api_providers": {provider: updates}})
