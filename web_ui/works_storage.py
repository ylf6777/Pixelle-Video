"""
作品存储模块 — 管理用户上传作品的审核与展示

作品状态流转:
    pending → approved (审核通过，进入展示队列)
    pending → rejected (审核拒绝)
    系统自动生成的内容不会进入此存储

存储位置: works/ 目录
    works/.index.json  — 作品元数据索引
    works/{work_id}/   — 作品文件目录
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

WORKS_DIR = Path("works")
WORKS_DIR.mkdir(exist_ok=True)
INDEX_FILE = WORKS_DIR / ".index.json"


def _load_index() -> list[dict]:
    """加载作品索引"""
    if not INDEX_FILE.exists():
        return []
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load works index: {e}")
        return []


def _save_index(works: list[dict]) -> None:
    """保存作品索引"""
    WORKS_DIR.mkdir(exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(works, f, ensure_ascii=False, indent=2)


def add_work(title: str, author: str, file_path: str, media_type: str) -> dict:
    """
    添加作品到待审核队列

    Args:
        title: 作品标题
        author: 作者/上传者
        file_path: 作品文件路径
        media_type: image 或 video

    Returns:
        作品元数据字典，含 work_id 和 status=pending
    """
    work_id = str(uuid.uuid4())[:12]
    works = _load_index()

    work = {
        "work_id": work_id,
        "title": title,
        "author": author,
        "file_path": file_path,
        "media_type": media_type,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "reviewed_at": None,
    }
    works.insert(0, work)
    _save_index(works)
    logger.info(f"Work submitted: {work_id} — {title}")
    return work


def approve_work(work_id: str) -> Optional[dict]:
    """审核通过作品"""
    works = _load_index()
    for w in works:
        if w["work_id"] == work_id and w["status"] == "pending":
            w["status"] = "approved"
            w["reviewed_at"] = datetime.now().isoformat()
            _save_index(works)
            logger.info(f"Work approved: {work_id}")
            return w
    return None


def reject_work(work_id: str) -> Optional[dict]:
    """拒绝作品"""
    works = _load_index()
    for w in works:
        if w["work_id"] == work_id and w["status"] == "pending":
            w["status"] = "rejected"
            w["reviewed_at"] = datetime.now().isoformat()
            _save_index(works)
            logger.info(f"Work rejected: {work_id}")
            return w
    return None


def get_approved(page: int = 1, page_size: int = 12) -> dict:
    """
    分页获取已审核通过的作品

    Args:
        page: 页码（从1开始）
        page_size: 每页数量

    Returns:
        {"works": list, "total": int, "page": int, "total_pages": int}
    """
    works = _load_index()
    approved = [w for w in works if w["status"] == "approved"]
    total = len(approved)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    return {
        "works": approved[start:start + page_size],
        "total": total,
        "page": page,
        "total_pages": total_pages,
    }


def get_pending() -> list[dict]:
    """获取待审核作品列表"""
    return [w for w in _load_index() if w["status"] == "pending"]


def get_work(work_id: str) -> Optional[dict]:
    """获取单个作品"""
    for w in _load_index():
        if w["work_id"] == work_id:
            return w
    return None
