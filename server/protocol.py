"""
protocol.py
-----------
Message schema for DoubtNet WebSocket protocol.
All messages are JSON objects with a "type" field.
"""

import json
import time


def now_ts() -> float:
    return time.time()


def encode(obj: dict) -> str:
    return json.dumps(obj)


REQUIRED_FIELDS = {
    "register": ["username", "password", "role"],
    "login": ["username", "password"],
    "select_room": ["room_code"],
    "create_room": ["room_name"],
    "join_room": ["room_code"],
    "submit_doubt": ["text", "urgency"],
    "autosave_draft": ["text"],
    "pin_doubt": [],
    "moderate_doubt": ["doubt_id", "action"],
    "set_schedule": ["schedule"],
    "resolve_doubt": ["cluster_id"],
    "merge_clusters": ["cluster_a", "cluster_b"],
    "split_cluster": ["cluster_id", "doubt_ids"],
}


def decode(raw: str) -> dict:
    obj = json.loads(raw)
    if not isinstance(obj, dict) or "type" not in obj:
        raise ValueError("Message must be a JSON object with a 'type' field")
    msg_type = obj["type"]
    if msg_type in REQUIRED_FIELDS:
        for field in REQUIRED_FIELDS[msg_type]:
            if field not in obj:
                raise ValueError(f"Message of type '{msg_type}' missing required field: '{field}'")
    return obj


# ---- Server -> Client message builders ----

PROTOCOL_VERSION = "v1.2"


def msg_auth_ok(username: str, role: str, state: dict, room_code: str = None, room_name: str = None) -> str:
    return encode({
        "type": "auth_ok",
        "username": username,
        "role": role,
        "state": state,
        "room_code": room_code,
        "room_name": room_name,
        "protocol_version": PROTOCOL_VERSION,
    })


def msg_needs_room(role: str) -> str:
    """Sent when a legacy user logs in but has no room assigned."""
    return encode({
        "type": "needs_room",
        "role": role,
    })


def msg_rooms_list(username: str, role: str, rooms: list) -> str:
    """Sent after login/register with user's room list for the room picker."""
    return encode({
        "type": "rooms_list",
        "username": username,
        "role": role,
        "rooms": rooms,
    })


def msg_room_entered(username: str, role: str, state: dict, room_code: str, room_name: str) -> str:
    """Sent when a user selects a room from the picker."""
    return encode({
        "type": "room_entered",
        "username": username,
        "role": role,
        "state": state,
        "room_code": room_code,
        "room_name": room_name,
        "protocol_version": PROTOCOL_VERSION,
    })


def msg_auth_error(message: str) -> str:
    return encode({"type": "auth_error", "message": message})


def msg_state_update(state: dict) -> str:
    return encode({"type": "state_update", **state})


def msg_doubt_submitted(doubt_id: str, status: str) -> str:
    return encode({"type": "doubt_submitted", "doubt_id": doubt_id, "status": status})


def msg_doubt_count(count: int) -> str:
    return encode({"type": "doubt_count", "count": count})


def msg_draft_saved() -> str:
    return encode({"type": "draft_saved"})


def msg_student_doubts(doubts: list) -> str:
    return encode({"type": "student_doubts", "doubts": doubts})


def msg_moderation_queue(doubts: list) -> str:
    return encode({"type": "moderation_queue", "doubts": doubts})


def msg_all_doubts(approved: list, flagged: list) -> str:
    return encode({"type": "all_doubts", "approved": approved, "flagged": flagged})


def msg_clusters(data: dict, warning: str = None) -> str:
    res = {"type": "clusters", "clusters": data}
    if warning:
        res["warning"] = warning
    return encode(res)


def msg_cluster_updated(clusters: dict) -> str:
    return encode({"type": "cluster_updated", "clusters": clusters})


def msg_leaderboard(entries: list) -> str:
    return encode({"type": "leaderboard", "entries": entries})


def msg_points_finalized() -> str:
    return encode({"type": "points_finalized"})


def msg_resolution_queue(clusters: list) -> str:
    return encode({"type": "resolution_queue", "clusters": clusters})


def msg_doubt_resolved(cluster_id: str) -> str:
    return encode({"type": "doubt_resolved", "cluster_id": cluster_id})


def msg_schedule_info(schedule: dict) -> str:
    return encode({"type": "schedule_info", "schedule": schedule})


def msg_presence(users: list) -> str:
    return encode({"type": "presence", "users": users})


def msg_system(text: str, ts: float = None) -> str:
    return encode({"type": "system", "text": text, "ts": ts or now_ts()})


def msg_error(message: str) -> str:
    return encode({"type": "error", "message": message})
