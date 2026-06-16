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
模板工具函数（Template Utilities）

提供模板尺寸解析、列表、分组和路径解析功能。

提供:
- parse_template_size: 从路径解析 WIDTHxHEIGHT 尺寸
- list_available_sizes: 列出所有可用的视频尺寸
- list_templates_for_size: 列出指定尺寸下的模板文件
- get_template_full_path: 根据尺寸和模板名获取完整路径
- format_template_display_info: 格式化模板展示信息供 UI 使用
- get_all_templates_with_info: 获取所有模板及其展示信息
- get_templates_grouped_by_size: 按尺寸分组模板列表
- resolve_template_path: 解析模板输入并返回验证后的完整路径
- get_template_type: 从模板文件名检测模板类型
- filter_templates_by_type: 按类型过滤模板列表
- get_templates_grouped_by_size_and_type: 按尺寸和类型筛选分组模板
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Literal
from pydantic import BaseModel, Field
from loguru import logger

from pixelle_video.utils.os_util import (
    get_resource_path,
    list_resource_files,
    list_resource_dirs,
    resource_exists
)



def parse_template_size(template_path: str) -> Tuple[int, int]:
    """
    从模板路径中解析视频尺寸。

    期望路径格式如 "templates/1080x1920/default.html" 或 "1080x1920/default.html"，
    从父目录名中提取 WIDTHxHEIGHT 尺寸。

    Args:
        template_path: 模板路径（如 "templates/1080x1920/default.html"
                      或 "1080x1920/default.html"）

    Returns:
        (width, height) 像素尺寸元组

    Raises:
        ValueError: 如果路径格式无效、目录名不含 'x' 分隔符、
                   或解析后的尺寸超出合理范围（<100 或 >10000）

    Requires:
        - template_path 为非空字符串
        - 路径格式符合 WIDTHxHEIGHT/template.html 约定

    Side Effects:
        无（纯解析函数）

    Examples:
        >>> parse_template_size("templates/1080x1920/default.html")
        (1080, 1920)
        >>> parse_template_size("1920x1080/modern.html")
        (1920, 1080)
    """
    path = Path(template_path)

    # 获取父目录名（应为 "1080x1920" 格式）
    dir_name = path.parent.name

    # 特殊情况：如果父目录是 "templates"，再上一级
    if dir_name == "templates":
        # 新结构中不应出现，但仍处理
        raise ValueError(
            f"Invalid template path format: {template_path}. "
            f"Expected format: 'WIDTHxHEIGHT/template.html' or 'templates/WIDTHxHEIGHT/template.html'"
        )

    # 从目录名解析尺寸
    if 'x' not in dir_name:
        raise ValueError(
            f"Invalid size format in path: {template_path}. "
            f"Directory name should be 'WIDTHxHEIGHT' (e.g., '1080x1920')"
        )

    try:
        width_str, height_str = dir_name.split('x')
        width = int(width_str)
        height = int(height_str)

        # 合理性检查
        if width < 100 or height < 100 or width > 10000 or height > 10000:
            raise ValueError(f"Invalid size dimensions: {width}x{height}")

        return (width, height)
    except ValueError as e:
        raise ValueError(
            f"Failed to parse size from path: {template_path}. "
            f"Expected format: 'WIDTHxHEIGHT/template.html' (e.g., '1080x1920/default.html'). "
            f"Error: {e}"
        )


def list_available_sizes() -> List[str]:
    """
    列出所有可用的视频尺寸。

    合并 templates/ 和 data/templates/ 目录，只返回有效 WIDTHxHEIGHT 格式的目录。

    Args:
        无

    Returns:
        尺寸字符串列表，如 ["1080x1920", "1920x1080", "1080x1080"]，已排序

    Raises:
        无（目录不存在或有无效目录时静默跳过）

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容（通过 list_resource_dirs）

    Examples:
        >>> list_available_sizes()
        ['1080x1920', '1920x1080', '1080x1080']
    """
    # 使用资源 API 合并默认和自定义目录
    all_dirs = list_resource_dirs("templates")

    # 仅保留有效的 WIDTHxHEIGHT 格式
    sizes = []
    for dir_name in all_dirs:
        if 'x' in dir_name:
            try:
                width, height = dir_name.split('x')
                int(width)
                int(height)
                sizes.append(dir_name)
            except (ValueError, AttributeError):
                # 跳过无效目录
                continue

    return sorted(sizes)


def list_templates_for_size(size: str) -> List[str]:
    """
    列出指定尺寸下所有可用的模板文件名。

    合并 templates/ 和 data/templates/ 目录。

    Args:
        size: 尺寸字符串，如 "1080x1920"

    Returns:
        HTML 模板文件名列表（不含路径），如 ["default.html", "modern.html"]，已排序

    Raises:
        无（目录不存在时返回空列表）

    Requires:
        - 文件系统可读权限
        - size 为有效的 WIDTHxHEIGHT 格式

    Side Effects:
        - 读取文件系统目录内容（通过 list_resource_files）

    Examples:
        >>> list_templates_for_size("1080x1920")
        ['cartoon.html', 'default.html', 'elegant.html', 'modern.html', ...]
    """
    # 使用资源 API 合并默认和自定义模板
    all_files = list_resource_files("templates", size)

    # 仅保留 HTML 文件
    templates = [f for f in all_files if f.endswith('.html')]

    return sorted(templates)


def get_template_full_path(size: str, template_name: str) -> str:
    """
    根据尺寸和模板名获取完整模板路径。

    优先返回 data/templates/ 下的自定义模板，否则返回 templates/ 下的默认模板。

    Args:
        size: 尺寸字符串，如 "1080x1920"
        template_name: 模板文件名，如 "default.html"

    Returns:
        模板文件的绝对路径（自定义优先，否则默认）

    Raises:
        FileNotFoundError: 如果在 data/templates/ 和 templates/ 中都找不到文件

    Requires:
        - 文件系统可读权限
        - size 和 template_name 为非空字符串

    Side Effects:
        - 读取文件系统检查文件存在性（通过 get_resource_path）

    Examples:
        >>> get_template_full_path("1080x1920", "default.html")
        'templates/1080x1920/default.html'
    """
    # 使用资源 API 先搜索自定义模板，再回退到默认模板
    try:
        return get_resource_path("templates", size, template_name)
    except FileNotFoundError:
        available_templates = list_templates_for_size(size)
        raise FileNotFoundError(
            f"Template not found: {size}/{template_name}\n"
            f"Available templates for size {size}: {available_templates}"
        )


class TemplateDisplayInfo(BaseModel):
    """模板展示信息，供 UI 层使用。

    Attributes:
        name: 模板名（不含扩展名）
        size: 尺寸字符串（如 "1080x1920"）
        width: 宽度（像素）
        height: 高度（像素）
        orientation: 视频方向（"portrait" / "landscape" / "square"）
        is_standard: True 仅对标准尺寸（1080x1920, 1920x1080, 1080x1080）
    """

    name: str = Field(..., description="Template name without extension")
    size: str = Field(..., description="Size string like '1080x1920'")
    width: int = Field(..., description="Width in pixels")
    height: int = Field(..., description="Height in pixels")
    orientation: Literal['portrait', 'landscape', 'square'] = Field(
        ...,
        description="Video orientation"
    )
    is_standard: bool = Field(
        ...,
        description="True only for standard sizes: 1080x1920, 1920x1080, 1080x1080"
    )


class TemplateInfo(BaseModel):
    """完整模板信息，包含路径和展示数据。

    Attributes:
        template_path: 完整模板相对路径（如 "1080x1920/default.html"）
        display_info: TemplateDisplayInfo 展示信息对象
    """

    template_path: str = Field(..., description="Full template path like '1080x1920/default.html'")
    display_info: TemplateDisplayInfo = Field(..., description="Display information")


def format_template_display_info(template_name: str, size: str) -> TemplateDisplayInfo:
    """
    格式化模板展示信息，供 UI 层使用。

    自动检测视频方向（竖屏/横屏/方形）和是否为标准尺寸。

    Args:
        template_name: 模板文件名（如 "default.html"）
        size: 尺寸字符串（如 "1080x1920"）

    Returns:
        TemplateDisplayInfo 对象，包含 name, size, width, height, orientation, is_standard

    Raises:
        ValueError: 如果 size 格式无效（不含 'x' 或无法解析为整数）

    Requires:
        - template_name 为非空字符串
        - size 为有效的 WIDTHxHEIGHT 格式

    Side Effects:
        无（纯计算函数）

    Examples:
        >>> info = format_template_display_info("default.html", "1080x1920")
        >>> info.name
        'default'
        >>> info.is_standard
        True

        >>> info = format_template_display_info("custom.html", "1080x1921")
        >>> info.orientation
        'portrait'
        >>> info.is_standard
        False
    """
    # 保留完整模板名（含 .html 扩展名）
    name = template_name

    # 解析尺寸
    width, height = map(int, size.split('x'))

    # 检测方向
    if height > width:
        orientation = 'portrait'
    elif width > height:
        orientation = 'landscape'
    else:
        orientation = 'square'

    # 检查是否为标准尺寸（仅以下三种）
    is_standard = (width, height) in [(1080, 1920), (1920, 1080), (1080, 1080)]

    return TemplateDisplayInfo(
        name=name,
        size=size,
        width=width,
        height=height,
        orientation=orientation,
        is_standard=is_standard
    )


def get_all_templates_with_info() -> List[TemplateInfo]:
    """
    获取所有模板及其展示信息。

    遍历所有可用尺寸和模板，为每个模板生成 TemplateInfo 对象。

    Args:
        无

    Returns:
        TemplateInfo 对象列表

    Raises:
        无（如果某尺寸下无模板则跳过）

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容（通过 list_available_sizes, list_templates_for_size）

    Example:
        >>> templates = get_all_templates_with_info()
        >>> for t in templates:
        ...     print(f"{t.display_info.name} - {t.display_info.orientation}")
        ...     print(f"  Path: {t.template_path}")
        ...     print(f"  Standard: {t.display_info.is_standard}")
    """
    result = []
    sizes = list_available_sizes()

    for size in sizes:
        templates = list_templates_for_size(size)
        for template in templates:
            display_info = format_template_display_info(template, size)
            full_path = f"{size}/{template}"
            result.append(TemplateInfo(
                template_path=full_path,
                display_info=display_info
            ))

    return result


def get_templates_grouped_by_size() -> dict:
    """
    获取按尺寸分组的模板列表。

    按方向优先级排序：竖屏 > 横屏 > 方形。

    Args:
        无

    Returns:
        以 size 为键、TemplateInfo 列表为值的字典，已按方向优先级排序

    Raises:
        无

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容（通过 get_all_templates_with_info）

    Example:
        >>> grouped = get_templates_grouped_by_size()
        >>> for size, templates in grouped.items():
        ...     print(f"Size: {size}")
        ...     for t in templates:
        ...         print(f"  - {t.display_info.name}")
    """
    from collections import defaultdict

    templates = get_all_templates_with_info()
    grouped = defaultdict(list)

    for t in templates:
        grouped[t.display_info.size].append(t)

    # 按方向优先级排序：竖屏 > 横屏 > 方形
    orientation_priority = {'portrait': 0, 'landscape': 1, 'square': 2}

    sorted_grouped = {}
    for size in sorted(grouped.keys(), key=lambda s: (
        orientation_priority.get(grouped[s][0].display_info.orientation, 3),
        s
    )):
        sorted_grouped[size] = sorted(grouped[size], key=lambda t: t.display_info.name)

    return sorted_grouped


def resolve_template_path(template_input: Optional[str]) -> str:
    """
    解析模板输入并返回经过验证的完整路径。

    支持多种输入格式，优先检查 data/templates/ 自定义模板，
    否则回退到 templates/ 默认模板。

    Args:
        template_input: 支持以下格式：
            - None: 使用默认 "1080x1920/image_default.html"
            - "template.html": 使用默认尺寸 + 此模板名
            - "1080x1920/template.html": 完整相对路径
            - "templates/1080x1920/template.html": 旧版完整路径
            - "data/templates/1080x1920/template.html": 自定义路径（旧版）

    Returns:
        解析后的完整模板路径（自定义优先，否则默认）

    Raises:
        FileNotFoundError: 如果在 data/templates/ 和 templates/ 中都找不到模板

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统检查文件存在性
        - 输出 info/warning 级别日志（向后兼容迁移时）

    Examples:
        >>> resolve_template_path(None)
        'templates/1080x1920/image_default.html'
        >>> resolve_template_path("image_modern.html")
        'templates/1080x1920/image_modern.html'
        >>> resolve_template_path("1920x1080/image_default.html")
        'templates/1920x1080/image_default.html'
    """
    # 默认情况
    if template_input is None:
        template_input = "1080x1920/image_default.html"

    # 解析输入，提取尺寸和模板名
    size = None
    template_name = None

    # 处理不同的输入格式
    if template_input.startswith("templates/") or template_input.startswith("data/templates/"):
        # 旧版完整路径格式 — 提取尺寸和模板名
        parts = Path(template_input).parts
        if len(parts) >= 3:
            size = parts[-2]
            template_name = parts[-1]
    elif '/' in template_input and 'x' in template_input.split('/')[0]:
        # "1080x1920/template.html" 格式
        size, template_name = template_input.split('/', 1)
    else:
        # 仅模板名 — 使用默认尺寸
        size = "1080x1920"
        template_name = template_input

    # 向后兼容：将 "default.html" 迁移为 "image_default.html"
    if template_name == "default.html":
        migrated_name = "image_default.html"
        try:
            # 先尝试迁移后的名称
            path = get_resource_path("templates", size, migrated_name)
            logger.info(f"Backward compatibility: migrated '{template_input}' to '{size}/{migrated_name}'")
            return path
        except FileNotFoundError:
            # 回退尝试原始名称
            logger.warning(f"Migrated template '{size}/{migrated_name}' not found, trying original name")

    # 使用资源 API 解析路径（自定义 > 默认）
    try:
        return get_resource_path("templates", size, template_name)
    except FileNotFoundError:
        available_sizes = list_available_sizes()
        raise FileNotFoundError(
            f"Template not found: {size}/{template_name}\n"
            f"Available sizes: {available_sizes}\n"
            f"Hint: Use format 'SIZExSIZE/template.html' (e.g., '1080x1920/image_default.html')"
        )


def get_template_type(template_name: str) -> Literal['static', 'image', 'video']:
    """
    从模板文件名检测模板类型。

    命名约定：
    - static_*.html: 静态风格模板（无 AI 生成媒体）
    - image_*.html: 需要 AI 生成图像的模板
    - video_*.html: 需要 AI 生成视频的模板

    Args:
        template_name: 模板文件名（如 "image_default.html" 或 "video_simple.html"）

    Returns:
        模板类型字符串：'static'、'image' 或 'video'

    Raises:
        无（不符合命名约定时默认返回 'image'）

    Requires:
        - template_name 为非空字符串

    Side Effects:
        - 输出 warning 级别日志（不符合命名约定时）

    Examples:
        >>> get_template_type("static_simple.html")
        'static'
        >>> get_template_type("image_default.html")
        'image'
        >>> get_template_type("video_simple.html")
        'video'
    """
    name = Path(template_name).name

    if name.startswith("static_"):
        return "static"
    elif name.startswith("video_"):
        return "video"
    elif name.startswith("image_"):
        return "image"
    else:
        # 回退：尝试从旧命名中检测
        logger.warning(
            f"Template '{template_name}' doesn't follow naming convention (static_/image_/video_). "
            f"Defaulting to 'image' type."
        )
        return "image"


def filter_templates_by_type(
    templates: List[TemplateInfo],
    template_type: Literal['static', 'image', 'video']
) -> List[TemplateInfo]:
    """
    按类型过滤模板列表。

    Args:
        templates: TemplateInfo 对象列表
        template_type: 过滤类型（'static'、'image' 或 'video'）

    Returns:
        过滤后的 TemplateInfo 对象列表

    Raises:
        无

    Requires:
        - templates 为有效的 TemplateInfo 列表

    Side Effects:
        无（纯过滤函数）

    Examples:
        >>> all_templates = get_all_templates_with_info()
        >>> image_templates = filter_templates_by_type(all_templates, 'image')
        >>> len(image_templates) > 0
        True
    """
    filtered = []
    for t in templates:
        template_name = t.display_info.name
        if get_template_type(template_name) == template_type:
            filtered.append(t)
    return filtered


def get_templates_grouped_by_size_and_type(
    template_type: Optional[Literal['static', 'image', 'video']] = None
) -> dict:
    """
    获取按尺寸和（可选）类型筛选与分组的模板列表。

    按方向优先级排序：竖屏 > 横屏 > 方形。

    Args:
        template_type: 可选类型过滤（'static'、'image' 或 'video'）。
                      None 表示不按类型过滤。

    Returns:
        以 size 为键、TemplateInfo 列表为值的字典，已按方向优先级排序

    Raises:
        无

    Requires:
        - 文件系统可读权限

    Side Effects:
        - 读取文件系统目录内容（通过 get_all_templates_with_info）

    Examples:
        >>> # 获取所有模板
        >>> all_grouped = get_templates_grouped_by_size_and_type()

        >>> # 仅获取图像模板
        >>> image_grouped = get_templates_grouped_by_size_and_type('image')
    """
    from collections import defaultdict

    templates = get_all_templates_with_info()

    # 按类型过滤（如果指定了类型）
    if template_type is not None:
        templates = filter_templates_by_type(templates, template_type)

    grouped = defaultdict(list)

    for t in templates:
        grouped[t.display_info.size].append(t)

    # 按方向优先级排序：竖屏 > 横屏 > 方形
    orientation_priority = {'portrait': 0, 'landscape': 1, 'square': 2}

    sorted_grouped = {}
    for size in sorted(grouped.keys(), key=lambda s: (
        orientation_priority.get(grouped[s][0].display_info.orientation, 3),
        s
    )):
        sorted_grouped[size] = sorted(grouped[size], key=lambda t: t.display_info.name)

    return sorted_grouped
