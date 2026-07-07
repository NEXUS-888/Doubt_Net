"""
doubts.py
---------
Doubt submission, storage, and retrieval. Scoped per room, persists in data/rooms/<room_code>/doubts.json.
"""

import json
import os
import threading
import uuid
from datetime import datetime
import moderation
from typing import Optional

_lock = threading.RLock()


def _ensure_store(room_code: str):
    import rooms
    d_dir = rooms.room_data_dir(room_code)
    path = os.path.join(d_dir, "doubts.json")
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({"week_start": "", "doubts": [], "clusters": {}, "resolved_clusters": [], "drafts": {}}, f)


def _load(room_code: str) -> dict:
    _ensure_store(room_code)
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "doubts.json")
    with open(path, "r") as f:
        return json.load(f)


def _save(data: dict, room_code: str):
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "doubts.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def _ensure_week(week_start: str, room_code: str):
    if not week_start:
        return
    data = _load(room_code)
    if data.get("week_start") != week_start:
        data["week_start"] = week_start
        data["doubts"] = []
        data["clusters"] = {}
        data["resolved_clusters"] = []
        data["drafts"] = {}
        _save(data, room_code)


def mark_cluster_resolved(cluster_id: str, week_start: str, room_code: str):
    with _lock:
        data = _load(room_code)
        if "resolved_clusters" not in data:
            data["resolved_clusters"] = []
        if cluster_id not in data["resolved_clusters"]:
            data["resolved_clusters"].append(cluster_id)
        _save(data, room_code)


def get_resolved_clusters(week_start: str, room_code: str) -> list:
    with _lock:
        data = _load(room_code)
        if data.get("week_start") != week_start:
            return []
        return data.get("resolved_clusters", [])


def submit_doubt(username: str, text: str, urgency: str, day: int, week_start: str, room_code: str) -> dict:
    """Submit a doubt. Runs moderation filter. Returns result dict."""
    _ensure_week(week_start, room_code)
    with _lock:
        existing = get_doubts_for_week(week_start, room_code)
        mod_result = moderation.check_doubt(text, username, existing)
        doubt_id = f"d_{uuid.uuid4().hex[:8]}"

        entry = {
            "id": doubt_id,
            "text": text,
            "username": username,
            "day": day,
            "ts": datetime.now().timestamp(),
            "urgency": urgency,
            "status": "pending",
            "cluster_id": None,
            "moderation": {
                "auto_flag": mod_result.get("flag"),
                "teacher_approved": None,
            },
        }

        data = _load(room_code)

        if mod_result.get("flagged"):
            entry["status"] = "flagged"
            entry["moderation"]["auto_flag"] = mod_result["flag"]
        else:
            entry["status"] = "approved"

        data["doubts"].append(entry)
        _save(data, room_code)

    return {
        "doubt_id": doubt_id,
        "status": entry["status"],
        "flagged": mod_result.get("flagged", False),
        "flag_reason": mod_result.get("flag"),
    }


def autosave_draft(username: str, text: str, week_start: str, room_code: str):
    """Store in-progress draft so student doesn't lose text at cutoff."""
    _ensure_week(week_start, room_code)
    with _lock:
        data = _load(room_code)
        if "drafts" not in data:
            data["drafts"] = {}
        data["drafts"][username] = {
            "text": text,
            "ts": datetime.now().timestamp(),
        }
        _save(data, room_code)


def get_draft(username: str, week_start: str, room_code: str) -> str:
    _ensure_week(week_start, room_code)
    with _lock:
        data = _load(room_code)
        drafts = data.get("drafts", {})
        entry = drafts.get(username)
        if entry:
            return entry.get("text", "")
        return ""


def get_doubts_for_week(week_start: str, room_code: str) -> list:
    _ensure_week(week_start, room_code)
    with _lock:
        data = _load(room_code)
        return list(data.get("doubts", []))


def get_doubts_by_day(day: int, week_start: str, room_code: str) -> list:
    return [d for d in get_doubts_for_week(week_start, room_code) if d.get("day") == day]


def get_student_doubts(username: str, week_start: str, room_code: str) -> list:
    return [d for d in get_doubts_for_week(week_start, room_code) if d.get("username") == username]


def count_student_doubts_for_day(username: str, day: int, week_start: str, room_code: str) -> int:
    """Count non-rejected doubts submitted by a student for a specific day."""
    return len([
        d for d in get_doubts_for_week(week_start, room_code)
        if d.get("username") == username
        and d.get("day") == day
        and d.get("status") != "rejected"
    ])


def get_pending_moderation(week_start: str, room_code: str) -> list:
    return [d for d in get_doubts_for_week(week_start, room_code) if d.get("status") == "flagged"]


def get_approved_doubts(week_start: str, room_code: str) -> list:
    return [d for d in get_doubts_for_week(week_start, room_code) if d.get("status") == "approved"]


def update_doubt_status(doubt_id: str, status: str, week_start: str, room_code: str) -> bool:
    """Set a doubt's status: approved, rejected, pending. Returns True if found."""
    with _lock:
        data = _load(room_code)
        for d in data.get("doubts", []):
            if d["id"] == doubt_id:
                d["status"] = status
                if status == "approved":
                    d["moderation"]["teacher_approved"] = True
                elif status == "rejected":
                    d["moderation"]["teacher_approved"] = False
                _save(data, room_code)
                return True
        return False


def set_cluster_id(doubt_id: str, cluster_id: str, week_start: str, room_code: str):
    with _lock:
        data = _load(room_code)
        for d in data.get("doubts", []):
            if d["id"] == doubt_id:
                d["cluster_id"] = cluster_id
                _save(data, room_code)
                return


def get_doubt_count(week_start: str, room_code: str) -> int:
    return len(get_approved_doubts(week_start, room_code))


def store_clusters(week_start: str, clusters: dict, room_code: str):
    with _lock:
        data = _load(room_code)
        data["clusters"] = clusters
        _save(data, room_code)


def get_clusters(week_start: str, room_code: str) -> dict:
    with _lock:
        data = _load(room_code)
        return data.get("clusters", {})


def clear_week(week_start: str, room_code: str):
    with _lock:
        data = {"week_start": week_start, "doubts": [], "clusters": {}, "drafts": {}}
        _save(data, room_code)


def get_doubt_by_id(doubt_id: str, room_code: str) -> Optional[dict]:
    with _lock:
        data = _load(room_code)
        for d in data.get("doubts", []):
            if d["id"] == doubt_id:
                return d
        return None
