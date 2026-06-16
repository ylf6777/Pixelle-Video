"""
工作流注册表模块 — 启动时扫描 workflows/ 目录，构建工作流元数据缓存。

职责：
1. 定义 WorkflowMeta 数据类 — 新工作流接入的唯一契约
2. 定义 WorkflowRegistry 单例 — 扫描、缓存、查询工作流元数据
3. 通过前缀命名约定自动推断分类与媒体类型
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class WorkflowMeta:
    """
    工作流元数据 — 新工作流接入的唯一契约。

    一个工作流由此结构完整描述其标识、分类、来源、输入输出等信息。
    前端和路由层仅依赖此数据类，不关心底层 JSON 文件或 API 格式。

    Attributes:
        id:              工作流唯一标识符，如 "image_flux"。通常等同于文件名（不含扩展名）。
        name:            工作流展示名称，如 "Flux 文生图"。
        category:        分类 — image | video | audio | digital_human | action | analysis | none。
        source:          来源 — runninghub | selfhost | api | zealman。
        description:     工作流功能描述（可选）。
        tags:            标签列表，用于搜索与筛选（可选）。
        media_type:      媒体类型 — image | video | audio | none（默认 "image"）。
        version:         语义化版本号（默认 "1.0.0"）。
        author:          作者名称（可选）。
        thumbnail:       缩略图路径（可选）。
        workflow_file:   工作流 JSON 文件名或完整路径。
        inputs_schema:   输入参数 JSON Schema 定义（可选）。
        outputs_schema:  输出结果 JSON Schema 定义（可选）。
    """

    id: str
    name: str
    category: str  # image | video | audio | digital_human | action | analysis | none
    source: str  # runninghub | selfhost | api | zealman
    description: str = ""
    tags: list[str] = field(default_factory=list)
    media_type: str = "image"
    version: str = "1.0.0"
    author: str = ""
    thumbnail: str = ""
    workflow_file: str = ""
    inputs_schema: dict = field(default_factory=dict)
    outputs_schema: dict = field(default_factory=dict)


class WorkflowRegistry:
    """
    工作流注册表 — 启动时扫描一次 workflows/ 目录，结果缓存于内存。

    实现为单例模式（模块级实例 workflow_registry），所有查询操作均为 O(n)
    的内存扫描，m 不触发任何 I/O（缓存命中时）。

    只有 reload() 和首次 get_all() 会触发磁盘扫描。

    Usage::

        from web_ui.workflow_registry import workflow_registry

        all_workflows = workflow_registry.get_all()
        image_workflows = workflow_registry.by_category("image")
        rh_workflows = workflow_registry.by_source("runninghub")
        results = workflow_registry.search("flux")
        wf = workflow_registry.get_by_id("image_flux")

    Requires:
        - workflows/ 目录存在，含 runninghub/ 和 selfhost/ 子目录
        - 每个子目录包含 *.json 工作流文件（以下划线开头的文件会被跳过）
        - workflows/selfhost/_zealman_index.json 可选，存在时会被解析为 zealman 条目
    """

    # 文件名前缀 → (分类, 媒体类型) 映射表
    # 用于从文件名自动推断元信息
    _CATEGORY_PREFIX_MAP: dict[str, tuple[str, str]] = {
        "image_": ("image", "image"),
        "video_": ("video", "video"),
        "tts_": ("audio", "audio"),
        "digital_": ("digital_human", "video"),
        "i2v_": ("video", "video"),
        "af_": ("action", "image"),
        "analyse_": ("analysis", "none"),
    }

    def __init__(self, workflows_root: str = "workflows") -> None:
        """
        初始化注册表。

        Args:
            workflows_root: workflows 目录路径（相对于项目根目录）。
                            默认 "workflows"。

        SideEffects:
            - 无（仅存储配置，不触发扫描）
        """
        self._root = Path(workflows_root)
        self._cache: Optional[list[WorkflowMeta]] = None

    # ── 公共查询接口 ────────────────────────────────────────────

    def get_all(self) -> list[WorkflowMeta]:
        """
        获取全部已注册的工作流列表。

        首次调用时触发全量磁盘扫描并写入缓存；后续调用直接返回缓存副本。

        Returns:
            所有 WorkflowMeta 实例的列表。若 workflows/ 目录不存在或为空，
            返回空列表。

        SideEffects:
            - 首次调用：扫描磁盘，创建缓存
            - 后续调用：无 I/O
        """
        if self._cache is None:
            self._cache = self._scan_all()
        return list(self._cache)

    def reload(self) -> list[WorkflowMeta]:
        """
        强制重新扫描并刷新缓存。

        Returns:
            刷新后的全部工作流列表。

        SideEffects:
            - 清除现有缓存
            - 重新扫描磁盘 I/O
        """
        logger.info("WorkflowRegistry: 强制刷新缓存...")
        self._cache = None
        return self.get_all()

    def by_category(self, category: str) -> list[WorkflowMeta]:
        """
        按分类筛选工作流。

        Args:
            category: 分类名称。有效值: image, video, audio, digital_human, action, analysis, none。

        Returns:
            匹配分类的 WorkflowMeta 列表。

        Requires:
            - 若缓存未初始化，会触发首次扫描
        """
        return [w for w in self.get_all() if w.category == category]

    def by_source(self, source: str) -> list[WorkflowMeta]:
        """
        按来源筛选工作流。

        Args:
            source: 来源名称。有效值: runninghub, selfhost, api, zealman。

        Returns:
            匹配来源的 WorkflowMeta 列表。

        Requires:
            - 若缓存未初始化，会触发首次扫描
        """
        return [w for w in self.get_all() if w.source == source]

    def search(self, keyword: str) -> list[WorkflowMeta]:
        """
        模糊搜索工作流 — 匹配名称、描述与标签。

        搜索大小写不敏感，匹配 name、description 和 tags 字段中的任意
        关键字出现。

        Args:
            keyword: 搜索关键词。

        Returns:
            匹配的 WorkflowMeta 列表（可能为空）。

        Requires:
            - 若缓存未初始化，会触发首次扫描
        """
        kw = keyword.lower()
        return [
            w
            for w in self.get_all()
            if kw in w.name.lower()
            or kw in w.description.lower()
            or any(kw in t.lower() for t in w.tags)
        ]

    def get_by_id(self, workflow_id: str) -> Optional[WorkflowMeta]:
        """
        按 ID 精确查找单个工作流。

        Args:
            workflow_id: 工作流唯一标识符。

        Returns:
            匹配的 WorkflowMeta，不存在则返回 None。

        Requires:
            - 若缓存未初始化，会触发首次扫描
        """
        for w in self.get_all():
            if w.id == workflow_id:
                return w
        return None

    # ── 内部扫描逻辑 ────────────────────────────────────────────

    def _scan_all(self) -> list[WorkflowMeta]:
        """
        全量扫描 workflows/ 目录，返回所有工作流元数据。

        扫描顺序：
        1. runninghub/ 子目录 — 来源标记为 "runninghub"
        2. selfhost/ 子目录 — 来源标记为 "selfhost"
        3. selfhost/_zealman_index.json — 解析后来源标记为 "zealman"

        以下划线开头的 JSON 文件（如 _zealman_index.json）会被跳过，
        不作为独立工作流处理。

        Returns:
            合并后的 WorkflowMeta 列表。

        SideEffects:
            - 磁盘 I/O：遍历目录、读取 _zealman_index.json
            - logger.info：记录扫描到的条目数量

        Raises:
            无 — 所有异常均被捕获并记录日志，不会中断扫描。
        """
        results: list[WorkflowMeta] = []

        for subdir in ["runninghub", "selfhost"]:
            d = self._root / subdir
            if not d.is_dir():
                logger.warning(f"WorkflowRegistry: 目录不存在，跳过: {d}")
                continue
            for f in d.glob("*.json"):
                # 跳过以下划线开头的索引/元数据文件
                if f.name.startswith("_"):
                    continue
                try:
                    results.append(self._parse_file(f, subdir))
                except Exception:
                    logger.exception(
                        f"WorkflowRegistry: 解析失败，跳过文件: {f}"
                    )

        # 解析 zealman 索引文件
        idx = self._root / "selfhost" / "_zealman_index.json"
        if idx.exists():
            try:
                zealman_entries = self._parse_zealman_index(idx)
                results.extend(zealman_entries)
                logger.info(
                    f"WorkflowRegistry: 从 zealman 索引加载 {len(zealman_entries)} 个工作流"
                )
            except Exception:
                logger.exception(
                    "WorkflowRegistry: 解析 zealman 索引失败，跳过"
                )

        logger.info(
            f"WorkflowRegistry: 扫描完成，共 {len(results)} 个工作流"
        )
        return results

    def _parse_file(self, filepath: Path, source: str) -> WorkflowMeta:
        """
        从单个 JSON 文件名解析 WorkflowMeta。

        不读取文件内容 — 所有元信息通过文件名（stem）推断。
        若需要更丰富的元信息（描述、标签等），后续可扩展为读取 JSON 内部字段。

        Args:
            filepath: JSON 文件路径。
            source:   来源标识（"runninghub" 或 "selfhost"）。

        Returns:
            构建的 WorkflowMeta 实例。

        SideEffects:
            - 无 I/O（仅使用文件名）
        """
        stem = filepath.stem
        category, media_type = self._infer_from_name(stem)
        # 将下划线分隔的文件名转换为首字母大写的展示名称
        display = stem.replace("_", " ").title()
        return WorkflowMeta(
            id=stem,
            name=display,
            category=category,
            source=source,
            media_type=media_type,
            workflow_file=str(filepath),
        )

    def _parse_zealman_index(self, idx_path: Path) -> list[WorkflowMeta]:
        """
        解析 zealman 索引文件，返回 WorkflowMeta 列表。

        zealman 索引是一个 JSON 数组，每个条目包含 key、display_name、
        media_type、source 等字段。

        Args:
            idx_path: _zealman_index.json 文件路径。

        Returns:
            WorkflowMeta 列表。若 JSON 解析失败则返回空列表。

        Raises:
            json.JSONDecodeError: 若 JSON 格式无效（由调用方捕获）。

        SideEffects:
            - 磁盘 I/O：读取 idx_path 文件
        """
        with open(idx_path, "r", encoding="utf-8") as f:
            entries: list[dict] = json.load(f)

        results: list[WorkflowMeta] = []
        for entry in entries:
            key: str = entry.get("key", "")
            if not key:
                continue
            results.append(
                WorkflowMeta(
                    id=key,
                    name=entry.get("display_name", key),
                    category=entry.get("media_type", "image"),
                    source="zealman",
                    media_type=entry.get("media_type", "image"),
                    workflow_file=key,
                )
            )
        return results

    @classmethod
    def _infer_from_name(cls, name: str) -> tuple[str, str]:
        """
        根据文件名前缀推断分类与媒体类型。

        遍历 _CATEGORY_PREFIX_MAP，返回第一个匹配前缀的 (分类, 媒体类型)。
        若无匹配，默认返回 ("image", "image")。

        Args:
            name: 工作流文件名（stem）。

        Returns:
            (category, media_type) 元组。

        Example:
            >>> WorkflowRegistry._infer_from_name("video_wan2.2")
            ("video", "video")
            >>> WorkflowRegistry._infer_from_name("tts_edge")
            ("audio", "audio")
            >>> WorkflowRegistry._infer_from_name("unknown_workflow")
            ("image", "image")
        """
        for prefix, (cat, mt) in cls._CATEGORY_PREFIX_MAP.items():
            if name.startswith(prefix):
                return (cat, mt)
        return ("image", "image")


# 模块级单例 — 工作流注册表的唯一入口
workflow_registry = WorkflowRegistry()
