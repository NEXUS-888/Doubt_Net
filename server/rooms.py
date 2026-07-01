"""
rooms.py
--------
Room management for DoubtNet. Teachers create rooms with unique join codes,
students enter the code to join a teacher's room.
"""

import json
import os
import random
import string
import threading
import time

ROOMS_FILE = os.path.join(os.path.dirname(__file__), "data", "rooms.json")
_lock = threading.RLock()


def _ensure_store():
    os.makedirs(os.path.dirname(ROOMS_FILE), exist_ok=True)
    if not os.path.exists(ROOMS_FILE):
        with open(ROOMS_FILE, "w") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_store()
    with open(ROOMS_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(ROOMS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _generate_code() -> str:
    """Generate a unique 6-character alphanumeric room code."""
    rooms = _load()
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in rooms:
            return code


def create_room(teacher_username: str, room_name: str) -> dict:
    """Create a new room for a teacher. Returns the room dict."""
    with _lock:
        code = _generate_code()
        room = {
            "code": code,
            "name": room_name,
            "teacher": teacher_username,
            "created_at": time.time(),
            "students": []
        }
        rooms = _load()
        rooms[code] = room
        _save(rooms)

        # Create room data directory
        room_dir = os.path.join(os.path.dirname(__file__), "data", "rooms", code)
        os.makedirs(room_dir, exist_ok=True)

        return room


def join_room(student_username: str, room_code: str) -> tuple:
    """Add a student to a room. Returns (success, message_or_room)."""
    room_code = room_code.strip().upper()
    with _lock:
        rooms = _load()
        if room_code not in rooms:
            return False, "Invalid room code."
        room = rooms[room_code]
        if student_username in room["students"]:
            return True, room  # Already in room
        room["students"].append(student_username)
        _save(rooms)
        return True, room


def leave_room(student_username: str, room_code: str) -> bool:
    """Remove a student from a room."""
    with _lock:
        rooms = _load()
        if room_code not in rooms:
            return False
        room = rooms[room_code]
        if student_username in room["students"]:
            room["students"].remove(student_username)
            _save(rooms)
            return True
        return False


def get_room(room_code: str) -> dict | None:
    """Get room info by code."""
    with _lock:
        rooms = _load()
        return rooms.get(room_code.upper())


def get_room_for_user(username: str, role: str) -> dict | None:
    """Find which room a user belongs to."""
    with _lock:
        rooms = _load()
        for code, room in rooms.items():
            if role == "teacher" and room["teacher"] == username:
                return room
            if role == "student" and username in room.get("students", []):
                return room
        return None


def get_room_members(room_code: str) -> list:
    """Get all members of a room."""
    with _lock:
        rooms = _load()
        room = rooms.get(room_code)
        if not room:
            return []
        members = [{"username": room["teacher"], "role": "teacher"}]
        for s in room.get("students", []):
            members.append({"username": s, "role": "student"})
        return members


def room_data_dir(room_code: str) -> str:
    """Get the data directory for a specific room."""
    d = os.path.join(os.path.dirname(__file__), "data", "rooms", room_code)
    os.makedirs(d, exist_ok=True)
    return d
