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
配置加载器 — 纯 YAML 读写

负责从 YAML 文件加载配置字典以及将配置字典保存到 YAML 文件。
所有函数为纯 I/O 操作，不涉及配置校验或类型转换。
"""

from pathlib import Path
import yaml
from loguru import logger


def load_config_dict(config_path: str = "config.yaml") -> dict:
    """
    从 YAML 文件加载配置字典

    文件不存在或解析失败时返回空字典（不抛出异常），上游
    使用 Pydantic 默认值填空。

    Args:
        config_path (str): YAML 配置文件路径。默认: "config.yaml"

    Returns:
        dict: 配置键值对字典。文件不存在或解析失败时返回 {}。

    Raises:
        - 不抛出。所有异常内部捕获并返回空字典。

    Requires:
        - yaml (PyYAML): YAML 解析库。
        - 文件系统读取权限。

    Side Effects:
        - 读取磁盘文件。
        - 写入日志（info/warning/error）。

    Examples:
        >>> data = load_config_dict("config.yaml")
        >>> print(data.get("project_name"))
        "Pixelle-Video"
    """
    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}")
        logger.info("Using default configuration")
        return {}

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        logger.info(f"Configuration loaded from {config_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def save_config_dict(config: dict, config_path: str = "config.yaml") -> None:
    """
    将配置字典保存到 YAML 文件

    使用 UTF-8 编码，保留 Unicode 字符，不排序 key（保持
    用户自定义顺序）。

    Args:
        config (dict): 待保存的配置字典。
        config_path (str): 目标 YAML 文件路径。默认: "config.yaml"

    Returns:
        None

    Raises:
        Exception: 文件写入失败时向上抛出（让调用方决定如何处理）。

    Requires:
        - yaml (PyYAML): YAML 序列化库。
        - 文件系统写入权限。

    Side Effects:
        - 覆盖写入磁盘文件。
        - 写入日志（info/error）。

    Examples:
        >>> save_config_dict({"llm": {"model": "qwen-max"}}, "config.yaml")
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                config, f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False
            )
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise
