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
操作系统工具函数（OS Utilities）

提供 ylf_Video 项目的路径和文件管理工具。

提供:
- get_pixelle_video_root_path: 通过环境变量获取项目根目录
- ensure_pixelle_video_root_path: 确保根目录存在
- get_root_path: 获取根目录下路径
- get_temp_path: 获取临时目录下路径
- get_data_path: 获取用户数据目录下路径
- get_output_path: 获取输出目录下路径
- save_bytes_to_file: 保存二进制数据到文件
- ensure_dir: 确保目录存在

任务目录管理:
- create_task_id: 创建唯一任务 ID
- create_task_output_dir: 创建隔离的任务输出目录
- get_task_path: 获取任务目录下路径
- get_task_frame_path: 获取帧文件路径
- get_task_final_video_path: 获取最终视频路径

资源管理:
- get_resource_path: 获取资源文件路径（自定义覆盖）
- list_resource_files: 列出资源文件（合并默认+自定义）
- list_resource_dirs: 列出资源子目录（合并默认+自定义）
- resource_exists: 检查资源文件是否存在

设计参考 Pixelle-MCP 的 os_util.py。
"""

import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Literal


def get_pixelle_video_root_path() -> str:
    """
    获取 ylf_Video 项目根目录路径。

    优先使用 PIXELLE_VIDEO_ROOT 环境变量，确保在开发和打包
    环境中都能可靠地定位项目根目录。

    Args:
        无

    Returns:
        项目根目录的绝对路径字符串

    Raises:
        无（回退到当前工作目录）

    Requires:
        - 推荐设置 PIXELLE_VIDEO_ROOT 环境变量以获得可靠路径解析

    Side Effects:
        - 读取环境变量 PIXELLE_VIDEO_ROOT
    """
    # 检查环境变量（可靠运行所必需）
    env_root = os.environ.get("PIXELLE_VIDEO_ROOT")
    if env_root and Path(env_root).exists():
        return str(Path(env_root).resolve())

    # 回退到当前工作目录（开发环境可能未设置环境变量）
    return str(Path.cwd())


def ensure_pixelle_video_root_path() -> str:
    """
    确保 ylf_Video 根目录存在，并返回路径。

    如果 output 子目录不存在，会自动创建。

    Args:
        无

    Returns:
        根目录的绝对路径字符串

    Raises:
        OSError: 如果 output 子目录创建失败且根目录不可写

    Requires:
        - 文件系统可写权限

    Side Effects:
        - 如果不存在，创建 output/ 子目录
    """
    root_path = get_pixelle_video_root_path()
    root_path_obj = Path(root_path)
    output_dir = root_path_obj / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    return root_path


def get_root_path(*paths: str) -> str:
    """
    获取相对于项目根目录的路径。

    自动确保根目录存在（调用 ensure_pixelle_video_root_path）。

    Args:
        *paths: 要拼接到根目录后的路径组件

    Returns:
        绝对路径字符串

    Raises:
        OSError: 如果 ensure_pixelle_video_root_path 失败

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 调用 ensure_pixelle_video_root_path 可能创建目录

    Example:
        get_root_path("temp", "audio.mp3")
        # Returns: "/path/to/project/temp/audio.mp3"
    """
    root_path = ensure_pixelle_video_root_path()
    if paths:
        return os.path.join(root_path, *paths)
    return root_path


def get_temp_path(*paths: str) -> str:
    """
    获取相对于项目 temp 目录的路径。

    返回路径前确保 temp 目录存在。

    Args:
        *paths: 要拼接到 temp 目录后的路径组件

    Returns:
        temp 目录或其子文件/目录的绝对路径

    Raises:
        OSError: 如果目录创建失败且父目录不可写

    Requires:
        - 文件系统可写权限（用于创建 temp 目录）

    Side Effects:
        - 如果不存在，创建 temp/ 目录

    Example:
        get_temp_path("audio.mp3")
        # Returns: "/path/to/project/temp/audio.mp3"
    """
    temp_path = get_root_path("temp")

    # 确保 temp 目录存在
    os.makedirs(temp_path, exist_ok=True)

    if paths:
        return os.path.join(temp_path, *paths)
    return temp_path


def get_data_path(*paths: str) -> str:
    """
    获取相对于项目 data 目录的路径。

    返回路径前确保 data 目录存在。data 目录用于存放
    用户自定义资源（模板、BGM、工作流等）。

    Args:
        *paths: 要拼接到 data 目录后的路径组件

    Returns:
        data 目录或其子文件/目录的绝对路径

    Raises:
        OSError: 如果目录创建失败且父目录不可写

    Requires:
        - 文件系统可写权限（用于创建 data 目录）

    Side Effects:
        - 如果不存在，创建 data/ 目录

    Example:
        get_data_path("videos", "output.mp4")
        # Returns: "/path/to/project/data/videos/output.mp4"
    """
    data_path = get_root_path("data")

    # 确保 data 目录存在
    os.makedirs(data_path, exist_ok=True)

    if paths:
        return os.path.join(data_path, *paths)
    return data_path


def get_output_path(*paths: str) -> str:
    """
    获取相对于项目 output 目录的路径。

    返回路径前确保 output 目录存在。

    Args:
        *paths: 要拼接到 output 目录后的路径组件

    Returns:
        output 目录或其子文件/目录的绝对路径

    Raises:
        OSError: 如果目录创建失败且父目录不可写

    Requires:
        - 文件系统可写权限（用于创建 output 目录）

    Side Effects:
        - 如果不存在，创建 output/ 目录

    Example:
        get_output_path("video.mp4")
        # Returns: "/path/to/project/output/video.mp4"
    """
    output_path = get_root_path("output")

    # 确保 output 目录存在
    os.makedirs(output_path, exist_ok=True)

    if paths:
        return os.path.join(output_path, *paths)
    return output_path


def save_bytes_to_file(data: bytes, file_path: str) -> str:
    """
    将字节数据保存到文件。

    如果父目录不存在，会自动创建。

    Args:
        data: 要保存的二进制数据
        file_path: 目标文件路径

    Returns:
        保存后文件的绝对路径

    Raises:
        OSError: 如果目录创建失败或文件写入失败
        IOError: 如果磁盘空间不足或权限不足

    Requires:
        - data 为 bytes 类型
        - file_path 为非空字符串
        - 文件系统可写权限

    Side Effects:
        - 在磁盘上创建父目录和文件
        - 如果文件已存在，会覆盖

    Example:
        save_bytes_to_file(audio_data, get_temp_path("audio.mp3"))
    """
    # 确保父目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 写入二进制数据
    with open(file_path, "wb") as f:
        f.write(data)

    return os.path.abspath(file_path)


def ensure_dir(path: str) -> str:
    """
    确保目录存在，如果不存在则创建。

    Args:
        path: 目录路径

    Returns:
        目录的绝对路径

    Raises:
        OSError: 如果目录创建失败且父目录不可写

    Requires:
        - path 为非空字符串
        - 文件系统可写权限

    Side Effects:
        - 如果目录不存在，递归创建
    """
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


# ========== 任务目录管理（Task Directory Management） ==========

def create_task_id() -> str:
    """
    创建唯一任务 ID。

    格式: {timestamp}_{random_hex}
    示例: "20251028_143052_ab3d"

    碰撞概率: < 0.0001%（每秒 65536 种组合）

    Args:
        无

    Returns:
        任务 ID 字符串

    Raises:
        无

    Requires:
        - Python 标准库 random 模块可用

    Side Effects:
        - 调用 random.randint（消耗熵源）
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = f"{random.randint(0, 0xFFFF):04x}"  # 4 位十六进制 (0000-ffff)
    return f"{timestamp}_{random_suffix}"


def create_task_output_dir(task_id: Optional[str] = None) -> Tuple[str, str]:
    """
    为单个视频生成任务创建隔离的输出目录。

    目录结构:
        output/{task_id}/
        ├── final.mp4           # 最终视频输出
        ├── frames/             # 所有帧相关文件
        │   ├── 01_audio.mp3
        │   ├── 01_image.png
        │   ├── 01_composed.png
        │   ├── 01_segment.mp4
        │   └── ...
        └── metadata.json       # 可选：任务元数据

    Args:
        task_id: 可选任务 ID，为 None 时自动生成

    Returns:
        (task_dir, task_id) 元组：
        - task_dir: 任务目录的绝对路径
        - task_id: 使用的任务 ID

    Raises:
        OSError: 如果目录创建失败

    Requires:
        - 文件系统可写权限

    Side Effects:
        - 在磁盘上创建 output/{task_id}/ 和 output/{task_id}/frames/ 目录

    Example:
        >>> task_dir, task_id = create_task_output_dir()
        >>> # task_dir = "/path/to/project/output/20251028_143052_ab3d"
        >>> # task_id = "20251028_143052_ab3d"
    """
    if task_id is None:
        task_id = create_task_id()

    task_dir = get_output_path(task_id)
    frames_dir = os.path.join(task_dir, "frames")

    # 创建目录
    os.makedirs(frames_dir, exist_ok=True)

    return task_dir, task_id


def get_task_path(task_id: str, *paths: str) -> str:
    """
    获取任务目录下的路径。

    Args:
        task_id: 任务 ID
        *paths: 要拼接到任务目录后的路径组件

    Returns:
        任务目录内文件/子目录的绝对路径

    Raises:
        无（纯路径拼接，不验证目录是否存在）

    Requires:
        - task_id 为非空字符串

    Side Effects:
        无（纯路径拼接）

    Example:
        >>> get_task_path("20251028_143052_ab3d", "final.mp4")
        >>> # Returns: ".../output/20251028_143052_ab3d/final.mp4"
    """
    task_dir = get_output_path(task_id)
    if paths:
        return os.path.join(task_dir, *paths)
    return task_dir


def get_task_frame_path(
    task_id: str,
    frame_index: int,
    file_type: Literal["audio", "image", "video", "composed", "segment"]
) -> str:
    """
    获取任务目录下帧文件的路径。

    帧编号从 01 开始（便于人类阅读）。文件扩展名根据 file_type 自动确定。

    Args:
        task_id: 任务 ID
        frame_index: 帧索引（0-based 内部索引，文件名从 01 开始）
        file_type: 文件类型，决定扩展名：
            - "audio" -> .mp3
            - "image" -> .png
            - "video" -> .mp4
            - "composed" -> .png
            - "segment" -> .mp4

    Returns:
        帧文件的绝对路径

    Raises:
        KeyError: 如果 file_type 不在支持的类型列表中

    Requires:
        - task_id 为非空字符串
        - frame_index >= 0

    Side Effects:
        无（纯路径拼接）

    Example:
        >>> get_task_frame_path("20251028_143052_ab3d", 0, "audio")
        >>> # Returns: ".../output/20251028_143052_ab3d/frames/01_audio.mp3"
    """
    ext_map = {
        "audio": "mp3",
        "image": "png",
        "video": "mp4",
        "composed": "png",
        "segment": "mp4"
    }

    # 帧编号从 01 开始，便于人类阅读
    filename = f"{frame_index + 1:02d}_{file_type}.{ext_map[file_type]}"
    return get_task_path(task_id, "frames", filename)


def get_task_final_video_path(task_id: str) -> str:
    """
    获取任务目录下最终视频文件的路径。

    Args:
        task_id: 任务 ID

    Returns:
        最终视频文件的绝对路径（output/{task_id}/final.mp4）

    Raises:
        无（纯路径拼接）

    Requires:
        - task_id 为非空字符串

    Side Effects:
        无（纯路径拼接）

    Example:
        >>> get_task_final_video_path("20251028_143052_ab3d")
        >>> # Returns: ".../output/20251028_143052_ab3d/final.mp4"
    """
    return get_task_path(task_id, "final.mp4")


# ========== 资源管理（Resource Management） ==========

def get_resource_path(resource_type: Literal["bgm", "templates", "workflows"], *paths: str) -> str:
    """
    获取资源文件路径，支持自定义覆盖。

    搜索优先级:
        1. data/{resource_type}/*paths  （用户自定义，高优先级）
        2. {resource_type}/*paths       （默认，回退）

    Args:
        resource_type: 资源类型（"bgm"、"templates"、"workflows"）
        *paths: 相对于资源目录的路径组件

    Returns:
        资源文件的绝对路径（优先返回自定义路径，否则返回默认路径）

    Raises:
        FileNotFoundError: 如果在两个位置都找不到文件

    Requires:
        - resource_type 为有效类型

    Side Effects:
        - 读取文件系统检查文件是否存在

    Examples:
        >>> get_resource_path("bgm", "happy.mp3")
        # Returns: "data/bgm/happy.mp3" (if exists) or "bgm/happy.mp3"

        >>> get_resource_path("templates", "1080x1920", "default.html")
        # Returns: "data/templates/1080x1920/default.html" or "templates/1080x1920/default.html"

        >>> get_resource_path("workflows", "selfhost", "image_flux.json")
        # Returns: "data/workflows/selfhost/image_flux.json" or "workflows/selfhost/image_flux.json"
    """
    # 构建自定义路径 (data/*)
    custom_path = get_data_path(resource_type, *paths)

    # 构建默认路径 (root/*)
    default_path = get_root_path(resource_type, *paths)

    # 优先级：自定义 > 默认
    if os.path.exists(custom_path):
        return custom_path

    if os.path.exists(default_path):
        return default_path

    # 两个位置均未找到
    raise FileNotFoundError(
        f"Resource not found: {os.path.join(resource_type, *paths)}\n"
        f"  Searched locations:\n"
        f"    1. {custom_path} (custom)\n"
        f"    2. {default_path} (default)"
    )


def list_resource_files(
    resource_type: Literal["bgm", "templates", "workflows"],
    subdir: str = ""
) -> list[str]:
    """
    列出资源文件，合并默认和自定义位置。

    合并策略：
        - 先扫描 {resource_type}/* （默认，低优先级）
        - 再扫描 data/{resource_type}/* （自定义，高优先级，覆盖同名文件）

    Args:
        resource_type: 资源类型（"bgm"、"templates"、"workflows"）
        subdir: 可选子目录（如 templates 的 "1080x1920"）

    Returns:
        去重后排序的文件名列表（自定义覆盖默认同名文件）

    Raises:
        无（目录不存在时返回空列表）

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容

    Examples:
        >>> list_resource_files("bgm")
        # Returns: ["custom.mp3", "default.mp3", "happy.mp3"]

        >>> list_resource_files("templates", "1080x1920")
        # Returns: ["custom.html", "default.html", "modern.html"]
    """
    files = {}  # 用字典追踪来源优先级: {filename: path}

    # 构建目录路径
    default_dir = Path(get_root_path(resource_type, subdir)) if subdir else Path(get_root_path(resource_type))
    custom_dir = Path(get_data_path(resource_type, subdir)) if subdir else Path(get_data_path(resource_type))

    # 先扫描默认目录（低优先级）
    if default_dir.exists() and default_dir.is_dir():
        for item in default_dir.iterdir():
            if item.is_file():
                files[item.name] = str(item)

    # 再扫描自定义目录（高优先级，覆盖同名）
    if custom_dir.exists() and custom_dir.is_dir():
        for item in custom_dir.iterdir():
            if item.is_file():
                files[item.name] = str(item)  # 覆盖已存在的

    return sorted(files.keys())


def list_resource_dirs(
    resource_type: Literal["bgm", "templates", "workflows"]
) -> list[str]:
    """
    列出资源目录下的子目录，合并默认和自定义位置。

    合并策略与 list_resource_files 相同：自定义覆盖默认。

    Args:
        resource_type: 资源类型（"bgm"、"templates"、"workflows"）

    Returns:
        去重后排序的子目录名列表

    Raises:
        无（目录不存在时返回空列表）

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容

    Examples:
        >>> list_resource_dirs("templates")
        # Returns: ["1080x1080", "1080x1920", "1920x1080"]

        >>> list_resource_dirs("workflows")
        # Returns: ["runninghub", "selfhost"]
    """
    dirs = set()

    # 构建目录路径
    default_dir = Path(get_root_path(resource_type))
    custom_dir = Path(get_data_path(resource_type))

    # 扫描默认目录
    if default_dir.exists() and default_dir.is_dir():
        for item in default_dir.iterdir():
            if item.is_dir():
                dirs.add(item.name)

    # 扫描自定义目录
    if custom_dir.exists() and custom_dir.is_dir():
        for item in custom_dir.iterdir():
            if item.is_dir():
                dirs.add(item.name)

    return sorted(dirs)


def resource_exists(resource_type: Literal["bgm", "templates", "workflows"], *paths: str) -> bool:
    """
    检查资源文件是否存在（在自定义或默认位置中）。

    Args:
        resource_type: 资源类型（"bgm"、"templates"、"workflows"）
        *paths: 相对于资源目录的路径组件

    Returns:
        True 表示文件在任一位置存在，False 表示都不存在

    Raises:
        无

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统检查文件是否存在

    Examples:
        >>> resource_exists("bgm", "happy.mp3")
        True

        >>> resource_exists("templates", "1080x1920", "default.html")
        True
    """
    custom_path = get_data_path(resource_type, *paths)
    default_path = get_root_path(resource_type, *paths)

    return os.path.exists(custom_path) or os.path.exists(default_path)
