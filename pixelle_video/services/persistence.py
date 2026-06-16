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
持久化服务 — 基于文件系统的任务数据存储

管理 output/ 目录下的任务元数据 (metadata.json)、分镜数据 (storyboard.json)
和任务索引 (.index.json)。所有数据以 JSON 格式存储，UTF-8 编码。

文件结构:
    output/
    ├── .index.json              # 任务索引（快速列表查询）
    └── {task_id}/
        ├── metadata.json         # 任务元数据
        ├── storyboard.json       # 分镜数据
        ├── final.mp4             # 最终视频
        └── frames/
            ├── 01_audio.mp3
            ├── 01_image.png
            └── ...
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from pixelle_video.models.storyboard import (
    Storyboard, StoryboardFrame, StoryboardConfig, ContentMetadata
)


class PersistenceService:
    """
    基于文件系统的任务持久化服务

    提供任务的完整 CRUD 操作、分页查询、统计和索引管理。
    所有操作为同步 I/O（方法标记 async 以保持与调用方一致的接口）。

    Requires:
        - pixelle_video.models.storyboard: Storyboard 及相关数据模型。
        - 文件系统读写权限（output_dir 及其子目录）。
        - json 标准库 + shutil（delete_task 时）。

    Side Effects:
        - 读写 output/ 目录下的 JSON 文件。
        - 维护 .index.json 索引文件。
    """

    def __init__(self, output_dir: str = "output"):
        """
        初始化持久化服务

        Args:
            output_dir (str): 输出根目录路径。默认: "output"。

        Side Effects:
            - 创建 output_dir 目录（如不存在）。
            - 创建 .index.json 索引文件（如不存在）。
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.index_file = self.output_dir / ".index.json"
        self._ensure_index()

    # ========================================================================
    # 路径辅助方法
    # ========================================================================

    def get_task_dir(self, task_id: str) -> Path:
        """
        获取任务目录路径

        Args:
            task_id (str): 任务 ID（UUID）。

        Returns:
            Path: output/{task_id} 的 Path 对象（不保证目录存在）。

        Requires:
            - 无外部依赖。纯路径拼接。
        """
        return self.output_dir / task_id

    def get_metadata_path(self, task_id: str) -> Path:
        """
        获取任务元数据文件路径

        Args:
            task_id (str): 任务 ID。

        Returns:
            Path: output/{task_id}/metadata.json 的 Path 对象。

        Requires:
            - self.get_task_dir: 任务目录路径。
        """
        return self.get_task_dir(task_id) / "metadata.json"

    def get_storyboard_path(self, task_id: str) -> Path:
        """
        获取分镜数据文件路径

        Args:
            task_id (str): 任务 ID。

        Returns:
            Path: output/{task_id}/storyboard.json 的 Path 对象。

        Requires:
            - self.get_task_dir: 任务目录路径。
        """
        return self.get_task_dir(task_id) / "storyboard.json"

    # ========================================================================
    # 元数据操作
    # ========================================================================

    async def save_task_metadata(self, task_id: str, metadata: Dict[str, Any]) -> None:
        """
        将任务元数据保存到文件系统

        datetime 对象自动转换为 ISO 格式字符串。

        Args:
            task_id (str): 任务 ID。
            metadata (dict): 元数据字典。结构:
                {
                    "task_id": str,
                    "created_at": str | datetime,
                    "completed_at": str | datetime (optional),
                    "status": str,           # pending/running/completed/failed/cancelled
                    "input": dict,
                    "result": dict (optional),
                    "config": dict
                }

        Raises:
            Exception: JSON 序列化或文件写入失败时向上抛出。

        Requires:
            - json.dump: JSON 序列化。
            - self._update_index_for_task: 同步更新索引。

        Side Effects:
            - 创建 output/{task_id}/ 目录。
            - 写入 metadata.json 文件。
            - 更新 .index.json 索引。
        """
        try:
            task_dir = self.get_task_dir(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)

            metadata_path = self.get_metadata_path(task_id)
            metadata["task_id"] = task_id

            # datetime → ISO 格式字符串
            if "created_at" in metadata and isinstance(metadata["created_at"], datetime):
                metadata["created_at"] = metadata["created_at"].isoformat()
            if "completed_at" in metadata and isinstance(metadata["completed_at"], datetime):
                metadata["completed_at"] = metadata["completed_at"].isoformat()

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved task metadata: {task_id}")
            await self._update_index_for_task(task_id, metadata)

        except Exception as e:
            logger.error(f"Failed to save task metadata {task_id}: {e}")
            raise

    async def load_task_metadata(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        从文件系统加载任务元数据

        Args:
            task_id (str): 任务 ID。

        Returns:
            Optional[dict]: 元数据字典。文件不存在或读取失败返回 None。

        Requires:
            - json.load: JSON 反序列化。
            - 文件系统读取权限。

        Side Effects:
            - 读取磁盘文件。
            - 写入日志（debug/error）。
        """
        try:
            metadata_path = self.get_metadata_path(task_id)
            if not metadata_path.exists():
                return None

            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load task metadata {task_id}: {e}")
            return None

    async def update_task_status(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """
        更新任务的运行状态

        终态（completed/failed/cancelled）自动设置 completed_at 时间戳。

        Args:
            task_id (str): 任务 ID。
            status (str): 新状态。合法值: pending, running, completed, failed, cancelled。
            error (Optional[str]): 错误信息。仅 failed 状态使用。

        Requires:
            - self.load_task_metadata: 读取当前元数据。
            - self.save_task_metadata: 写回更新后的元数据。

        Side Effects:
            - 读写 metadata.json。
            - 任务不存在时仅记录 warning，不抛异常。
        """
        try:
            metadata = await self.load_task_metadata(task_id)
            if not metadata:
                logger.warning(f"Cannot update status: task {task_id} not found")
                return

            metadata["status"] = status

            if status in ["completed", "failed", "cancelled"]:
                metadata["completed_at"] = datetime.now().isoformat()

            if error:
                metadata["error"] = error

            await self.save_task_metadata(task_id, metadata)

        except Exception as e:
            logger.error(f"Failed to update task status {task_id}: {e}")

    # ========================================================================
    # 分镜操作
    # ========================================================================

    async def save_storyboard(self, task_id: str, storyboard: Storyboard) -> None:
        """
        将 Storyboard 对象序列化为 JSON 保存

        Args:
            task_id (str): 任务 ID。
            storyboard (Storyboard): 完整分镜表对象。

        Raises:
            Exception: JSON 序列化或文件写入失败时向上抛出。

        Requires:
            - self._storyboard_to_dict: Storyboard → dict 转换。
            - json.dump: JSON 序列化。

        Side Effects:
            - 创建 output/{task_id}/ 目录。
            - 写入 storyboard.json 文件。
        """
        try:
            task_dir = self.get_task_dir(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)

            storyboard_path = self.get_storyboard_path(task_id)
            storyboard_dict = self._storyboard_to_dict(storyboard)

            with open(storyboard_path, "w", encoding="utf-8") as f:
                json.dump(storyboard_dict, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved storyboard: {task_id}")

        except Exception as e:
            logger.error(f"Failed to save storyboard {task_id}: {e}")
            raise

    async def load_storyboard(self, task_id: str) -> Optional[Storyboard]:
        """
        从 JSON 文件加载 Storyboard 对象

        Args:
            task_id (str): 任务 ID。

        Returns:
            Optional[Storyboard]: 反序列化的 Storyboard 对象。文件不存在或读取失败返回 None。

        Requires:
            - self._dict_to_storyboard: dict → Storyboard 转换。
            - json.load: JSON 反序列化。

        Side Effects:
            - 读取磁盘文件。
        """
        try:
            storyboard_path = self.get_storyboard_path(task_id)
            if not storyboard_path.exists():
                return None

            with open(storyboard_path, "r", encoding="utf-8") as f:
                storyboard_dict = json.load(f)

            return self._dict_to_storyboard(storyboard_dict)

        except Exception as e:
            logger.error(f"Failed to load storyboard {task_id}: {e}")
            return None

    # ========================================================================
    # 任务列表与查询
    # ========================================================================

    async def list_tasks(
        self, status: Optional[str] = None,
        limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出任务（支持状态筛选和分页）

        从 .index.json 索引文件读取，不扫描磁盘目录。

        Args:
            status (Optional[str]): 状态筛选。None 表示不过滤。
            limit (int): 返回条数上限。默认 50。
            offset (int): 跳过条数。默认 0。

        Returns:
            List[dict]: 按 created_at 降序排列的任务摘要列表。

        Requires:
            - self._load_index: 加载 .index.json。

        Side Effects:
            - 读取 .index.json 文件。
        """
        try:
            index = self._load_index()
            tasks = index.get("tasks", [])

            if status:
                tasks = [t for t in tasks if t.get("status") == status]

            tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
            return tasks[offset:offset + limit]

        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    async def task_exists(self, task_id: str) -> bool:
        """
        检查任务目录是否存在

        Args:
            task_id (str): 任务 ID。

        Returns:
            bool: 任务目录存在时返回 True。

        Requires:
            - 文件系统访问权限。
        """
        return self.get_task_dir(task_id).exists()

    # ========================================================================
    # 序列化辅助（Storyboard ↔ dict）
    # ========================================================================

    def _storyboard_to_dict(self, storyboard: Storyboard) -> Dict[str, Any]:
        """
        Storyboard 对象 → JSON 字典

        Args:
            storyboard (Storyboard): 完整分镜表。

        Returns:
            dict: 可 JSON 序列化的字典（datetime → ISO 格式字符串）。

        Requires:
            - self._config_to_dict, self._frame_to_dict, self._content_metadata_to_dict。
        """
        return {
            "title": storyboard.title,
            "config": self._config_to_dict(storyboard.config),
            "frames": [self._frame_to_dict(frame) for frame in storyboard.frames],
            "content_metadata": (
                self._content_metadata_to_dict(storyboard.content_metadata)
                if storyboard.content_metadata else None
            ),
            "final_video_path": storyboard.final_video_path,
            "total_duration": storyboard.total_duration,
            "created_at": (
                storyboard.created_at.isoformat() if storyboard.created_at else None
            ),
            "completed_at": (
                storyboard.completed_at.isoformat() if storyboard.completed_at else None
            ),
        }

    def _dict_to_storyboard(self, data: Dict[str, Any]) -> Storyboard:
        """
        JSON 字典 → Storyboard 对象

        Args:
            data (dict): 从 storyboard.json 加载的字典。

        Returns:
            Storyboard: 反序列化的分镜表对象。

        Requires:
            - self._dict_to_config, self._dict_to_frame, self._dict_to_content_metadata。
        """
        return Storyboard(
            title=data["title"],
            config=self._dict_to_config(data["config"]),
            frames=[self._dict_to_frame(fd) for fd in data["frames"]],
            content_metadata=(
                self._dict_to_content_metadata(data["content_metadata"])
                if data.get("content_metadata") else None
            ),
            final_video_path=data.get("final_video_path"),
            total_duration=data.get("total_duration", 0.0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at") else None
            ),
        )

    def _config_to_dict(self, config: StoryboardConfig) -> Dict[str, Any]:
        """StoryboardConfig → dict"""
        return {f.name: getattr(config, f.name)
                for f in StoryboardConfig.__dataclass_fields__.values()
                if not f.name.startswith("_")}

    def _dict_to_config(self, data: Dict[str, Any]) -> StoryboardConfig:
        """dict → StoryboardConfig（含向后兼容字段映射）"""
        return StoryboardConfig(
            task_id=data.get("task_id"),
            n_storyboard=data.get("n_storyboard", 5),
            min_narration_words=data.get("min_narration_words", 5),
            max_narration_words=data.get("max_narration_words", 20),
            min_image_prompt_words=data.get("min_image_prompt_words", 30),
            max_image_prompt_words=data.get("max_image_prompt_words", 60),
            video_fps=data.get("video_fps", 30),
            tts_inference_mode=data.get("tts_inference_mode", "local"),
            voice_id=data.get("voice_id"),
            tts_workflow=data.get("tts_workflow"),
            tts_speed=data.get("tts_speed"),
            ref_audio=data.get("ref_audio"),
            media_width=data.get("media_width", data.get("image_width", 1024)),
            media_height=data.get("media_height", data.get("image_height", 1024)),
            media_workflow=data.get("media_workflow", data.get("image_workflow")),
            frame_template=data.get("frame_template", "1080x1920/default.html"),
            template_params=data.get("template_params"),
        )

    def _frame_to_dict(self, frame: StoryboardFrame) -> Dict[str, Any]:
        """StoryboardFrame → dict（datetime → ISO 格式字符串）"""
        return {
            "index": frame.index,
            "narration": frame.narration,
            "image_prompt": frame.image_prompt,
            "audio_path": frame.audio_path,
            "media_type": frame.media_type,
            "image_path": frame.image_path,
            "video_path": frame.video_path,
            "composed_image_path": frame.composed_image_path,
            "video_segment_path": frame.video_segment_path,
            "duration": frame.duration,
            "created_at": (
                frame.created_at.isoformat() if frame.created_at else None
            ),
        }

    def _dict_to_frame(self, data: Dict[str, Any]) -> StoryboardFrame:
        """dict → StoryboardFrame"""
        return StoryboardFrame(
            index=data["index"],
            narration=data["narration"],
            image_prompt=data["image_prompt"],
            audio_path=data.get("audio_path"),
            media_type=data.get("media_type"),
            image_path=data.get("image_path"),
            video_path=data.get("video_path"),
            composed_image_path=data.get("composed_image_path"),
            video_segment_path=data.get("video_segment_path"),
            duration=data.get("duration", 0.0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at") else None
            ),
        )

    def _content_metadata_to_dict(
        self, metadata: ContentMetadata
    ) -> Dict[str, Any]:
        """ContentMetadata → dict"""
        return {
            "title": metadata.title,
            "author": metadata.author,
            "subtitle": metadata.subtitle,
            "genre": metadata.genre,
            "summary": metadata.summary,
            "publication_year": metadata.publication_year,
            "cover_url": metadata.cover_url,
        }

    def _dict_to_content_metadata(
        self, data: Dict[str, Any]
    ) -> ContentMetadata:
        """dict → ContentMetadata"""
        return ContentMetadata(
            title=data["title"],
            author=data.get("author"),
            subtitle=data.get("subtitle"),
            genre=data.get("genre"),
            summary=data.get("summary"),
            publication_year=data.get("publication_year"),
            cover_url=data.get("cover_url"),
        )

    # ========================================================================
    # 索引管理
    # ========================================================================

    def _ensure_index(self) -> None:
        """
        确保 .index.json 文件存在，不存在则创建空索引

        Side Effects:
            - 可能创建 .index.json 文件。
        """
        if not self.index_file.exists():
            self._save_index({"version": "1.0", "tasks": []})

    def _load_index(self) -> Dict[str, Any]:
        """
        从 .index.json 加载索引数据

        Returns:
            dict: 索引数据 {"version": str, "tasks": list}。
            文件读取失败时返回空索引。

        Side Effects:
            - 读取 .index.json 文件。
            - 写入日志（error）。
        """
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return {"version": "1.0", "tasks": []}

    def _save_index(self, index_data: Dict[str, Any]) -> None:
        """
        将索引数据保存到 .index.json

        Args:
            index_data (dict): 索引数据字典。

        Side Effects:
            - 覆盖写入 .index.json 文件。
            - 自动添加 last_updated 时间戳。
        """
        try:
            index_data["last_updated"] = datetime.now().isoformat()
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    async def _resolve_task_title(
        self, task_id: str, metadata: Dict[str, Any]
    ) -> str:
        """
        从多个来源解析任务标题（三级回退）

        1. metadata.input.title
        2. storyboard.title
        3. metadata.input.text 的前 30 个字符
        4. "Untitled"

        Args:
            task_id (str): 任务 ID。
            metadata (dict): 任务元数据。

        Returns:
            str: 解析后的任务标题。

        Requires:
            - self.load_storyboard: 第 2 级回退时加载分镜数据。
        """
        title = metadata.get("input", {}).get("title")
        if title:
            return title

        storyboard = await self.load_storyboard(task_id)
        if storyboard and storyboard.title:
            return storyboard.title

        input_text = metadata.get("input", {}).get("text", "")
        if input_text:
            return input_text[:30] + ("..." if len(input_text) > 30 else "")

        return "Untitled"

    async def _update_index_for_task(
        self, task_id: str, metadata: Dict[str, Any]
    ) -> None:
        """
        更新 .index.json 中对应任务的条目

        如果任务 ID 已存在于索引中则更新，否则追加。

        Args:
            task_id (str): 任务 ID。
            metadata (dict): 任务元数据。

        Requires:
            - self._resolve_task_title: 标题解析。
            - self._load_index / self._save_index: 索引读写。

        Side Effects:
            - 读写 .index.json 文件。
        """
        index = self._load_index()
        title = await self._resolve_task_title(task_id, metadata)

        index_entry = {
            "task_id": task_id,
            "created_at": metadata.get("created_at"),
            "completed_at": metadata.get("completed_at"),
            "status": metadata.get("status", "unknown"),
            "title": title,
            "duration": metadata.get("result", {}).get("duration", 0),
            "n_frames": metadata.get("result", {}).get("n_frames", 0),
            "file_size": metadata.get("result", {}).get("file_size", 0),
            "video_path": metadata.get("result", {}).get("video_path"),
        }

        tasks = index.get("tasks", [])
        existing_idx = next(
            (i for i, t in enumerate(tasks) if t["task_id"] == task_id), None
        )

        if existing_idx is not None:
            tasks[existing_idx] = index_entry
        else:
            tasks.append(index_entry)

        index["tasks"] = tasks
        self._save_index(index)

    async def rebuild_index(self) -> None:
        """
        通过扫描所有任务目录重建索引

        用于索引文件损坏或手动删除目录后的恢复场景。

        Requires:
            - self.load_task_metadata: 加载每个任务的元数据。
            - self._resolve_task_title: 标题解析。
            - self._save_index: 写入新索引。

        Side Effects:
            - 扫描 output/ 下所有子目录。
            - 覆盖 .index.json 文件。
        """
        logger.info("Rebuilding task index...")
        index = {"version": "1.0", "tasks": []}

        for task_dir in self.output_dir.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith("."):
                continue

            task_id = task_dir.name
            metadata = await self.load_task_metadata(task_id)

            if metadata:
                title = await self._resolve_task_title(task_id, metadata)
                index["tasks"].append({
                    "task_id": task_id,
                    "created_at": metadata.get("created_at"),
                    "completed_at": metadata.get("completed_at"),
                    "status": metadata.get("status", "unknown"),
                    "title": title,
                    "duration": metadata.get("result", {}).get("duration", 0),
                    "n_frames": metadata.get("result", {}).get("n_frames", 0),
                    "file_size": metadata.get("result", {}).get("file_size", 0),
                    "video_path": metadata.get("result", {}).get("video_path"),
                })

        self._save_index(index)
        logger.info(f"Index rebuilt: {len(index['tasks'])} tasks")

    # ========================================================================
    # 分页列表
    # ========================================================================

    async def list_tasks_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        分页列出任务（支持筛选和排序）

        Args:
            page (int): 页码（从 1 开始）。默认 1。
            page_size (int): 每页条数。默认 20。
            status (Optional[str]): 状态筛选。None = 全部。
            sort_by (str): 排序字段。created_at / completed_at / title / duration / n_frames。
            sort_order (str): 排序方向。"asc" 或 "desc"。默认 "desc"。

        Returns:
            dict: {
                "tasks": list,       # 当前页任务列表
                "total": int,        # 总匹配数
                "page": int,         # 当前页码
                "page_size": int,    # 每页条数
                "total_pages": int   # 总页数
            }

        Requires:
            - self._load_index: 从 .index.json 读取。
        """
        index = self._load_index()
        tasks = index.get("tasks", [])

        if status:
            tasks = [t for t in tasks if t.get("status") == status]

        reverse = (sort_order == "desc")
        if sort_by in ["created_at", "completed_at"]:
            tasks.sort(
                key=lambda t: datetime.fromisoformat(
                    t.get(sort_by, "1970-01-01T00:00:00")
                ),
                reverse=reverse
            )
        elif sort_by in ["title", "duration", "n_frames"]:
            tasks.sort(key=lambda t: t.get(sort_by, ""), reverse=reverse)

        total = len(tasks)
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        return {
            "tasks": tasks[start_idx:end_idx],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ========================================================================
    # 统计
    # ========================================================================

    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取所有任务的汇总统计

        Returns:
            dict: {
                "total_tasks": int,       # 总任务数
                "completed": int,         # 已完成数
                "failed": int,            # 失败数
                "total_duration": float,  # 总时长（秒）
                "total_size": int         # 总文件大小（字节）
            }

        Requires:
            - self._load_index: 从 .index.json 读取。
        """
        index = self._load_index()
        tasks = index.get("tasks", [])

        return {
            "total_tasks": len(tasks),
            "completed": len([t for t in tasks if t.get("status") == "completed"]),
            "failed": len([t for t in tasks if t.get("status") == "failed"]),
            "total_duration": sum(t.get("duration", 0) for t in tasks),
            "total_size": sum(t.get("file_size", 0) for t in tasks),
        }

    # ========================================================================
    # 删除
    # ========================================================================

    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其所有关联文件

        Args:
            task_id (str): 待删除的任务 ID。

        Returns:
            bool: 删除成功返回 True，失败返回 False。

        Requires:
            - shutil.rmtree: 递归删除目录。
            - self._load_index / self._save_index: 索引更新。

        Side Effects:
            - 删除 output/{task_id}/ 目录及其所有内容。
            - 从 .index.json 中移除该任务条目。
        """
        try:
            import shutil

            task_dir = self.get_task_dir(task_id)
            if task_dir.exists():
                shutil.rmtree(task_dir)
                logger.info(f"Deleted task directory: {task_dir}")

            index = self._load_index()
            tasks = [t for t in index.get("tasks", []) if t["task_id"] != task_id]
            index["tasks"] = tasks
            self._save_index(index)

            return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False
