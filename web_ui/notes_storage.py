"""纯文本记录存储 — JSON 文件持久化"""
import json
import uuid
from datetime import datetime
from pathlib import Path

NOTES_FILE = Path("data/notes.json")
NOTES_FILE.parent.mkdir(exist_ok=True)


def _load() -> list[dict]:
    if not NOTES_FILE.exists():
        return []
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(notes: list[dict]) -> None:
    NOTES_FILE.parent.mkdir(exist_ok=True)
    NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def list_notes() -> list[dict]:
    """按时间倒序返回所有记录"""
    notes = _load()
    notes.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    return notes


def add_note(title: str, content: str) -> dict:
    """新增记录"""
    note = {
        "id": str(uuid.uuid4())[:12],
        "title": title.strip(),
        "content": content.strip(),
        "created_at": datetime.now().isoformat(),
    }
    notes = _load()
    notes.append(note)
    _save(notes)
    return note


def update_note(note_id: str, title: str, content: str) -> dict | None:
    """编辑记录"""
    notes = _load()
    for n in notes:
        if n["id"] == note_id:
            n["title"] = title.strip()
            n["content"] = content.strip()
            _save(notes)
            return n
    return None


def delete_note(note_id: str) -> bool:
    """删除记录"""
    notes = _load()
    filtered = [n for n in notes if n["id"] != note_id]
    if len(filtered) < len(notes):
        _save(filtered)
        return True
    return False
