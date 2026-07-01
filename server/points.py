"""
points.py
---------
Scoring engine and leaderboard for DoubtNet. Scoped per room, persists in data/rooms/<room_code>/points.json.
"""

import json
import os
import threading

_lock = threading.Lock()

BASE_PARTICIPATION = 5
K_RARITY_BONUS = 20


def _ensure_store(room_code: str):
    import rooms
    d_dir = rooms.room_data_dir(room_code)
    path = os.path.join(d_dir, "points.json")
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)


def _load(room_code: str) -> dict:
    _ensure_store(room_code)
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "points.json")
    with open(path, "r") as f:
        return json.load(f)


def _save(data: dict, room_code: str):
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "points.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def compute_points(clusters: dict, doubts: list, week_start: str, room_code: str):
    """
    Compute points for each student based on cluster sizes.
    Points = BASE_PARTICIPATION + (K / cluster_size)
    Only approved doubts in finalized clusters earn points.
    """
    doubt_points = {}

    for cid, cluster in clusters.items():
        size = cluster.get("size", 1)
        points_per_doubt = BASE_PARTICIPATION + round(K_RARITY_BONUS / size, 1)

        for did in cluster.get("doubt_ids", []):
            doubt_points[did] = points_per_doubt

    with _lock:
        all_points = _load(room_code)
        # Always recalculate from scratch for the week
        all_points[week_start] = {}

        for doubt in doubts:
            did = doubt["id"]
            username = doubt["username"]
            pts = doubt_points.get(did, 0)
            if pts > 0:
                week_data = all_points[week_start]
                if username not in week_data:
                    week_data[username] = {"points": 0, "doubts": []}
                week_data[username]["points"] += pts
                week_data[username]["doubts"].append({
                    "doubt_id": did,
                    "cluster_id": doubt.get("cluster_id"),
                    "points": pts,
                })

        _save(all_points, room_code)


def get_leaderboard(week_start: str = None, room_code: str = None) -> list:
    """
    Returns [{ handle, total_points, rank, real_name, show_real_name }]
    Sorted by total_points descending.
    If week_start is None, aggregate all weeks.
    """
    if not room_code:
        return []

    with _lock:
        all_points = _load(room_code)

    from users import get_real_name, get_show_real_name

    user_totals = {}

    for week, week_data in all_points.items():
        if week_start is not None and week != week_start:
            continue
        for username, data in week_data.items():
            if username not in user_totals:
                user_totals[username] = 0
            user_totals[username] += data.get("points", 0)

    sorted_users = sorted(user_totals.items(), key=lambda x: -x[1])
    entries = []
    for rank, (handle, total) in enumerate(sorted_users, 1):
        real_name = get_real_name(handle)
        show_real = get_show_real_name(handle)
        entry = {
            "handle": handle,
            "total_points": total,
            "rank": rank,
        }
        if show_real and real_name:
            entry["real_name"] = real_name
        entries.append(entry)

    return entries


def get_student_points(username: str, room_code: str) -> dict:
    """
    Returns per-student point breakdown across all weeks in their room.
    Private view — no other handles or doubt text exposed.
    """
    if not room_code:
        return {"total": 0, "weeks": {}}

    with _lock:
        all_points = _load(room_code)

    result = {"total": 0, "weeks": {}}
    for week, week_data in all_points.items():
        if username in week_data:
            pts = week_data[username].get("points", 0)
            count = len(week_data[username].get("doubts", []))
            result["weeks"][week] = {"points": pts, "doubt_count": count}
            result["total"] += pts

    return result


def clear_week(week_start: str, room_code: str):
    """No-op for now — points are cumulative, never cleared."""
    pass
