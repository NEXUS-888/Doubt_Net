"""
users.py
--------
Handles user accounts: registration, login, roles.
Passwords are hashed with bcrypt. Room codes link users to rooms.
"""

import json
import os
import threading
import bcrypt

USERS_FILE = os.path.join(os.path.dirname(__file__), "data", "users.json")

_lock = threading.Lock()


def _ensure_store():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_store()
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    tmp_path = USERS_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, USERS_FILE)


def _migrate_user_record(username: str, record: dict):
    """Add missing fields to legacy user accounts."""
    if "role" not in record:
        record["role"] = "student"
    if "real_name" not in record:
        record["real_name"] = None
    if "show_real_name" not in record:
        record["show_real_name"] = False
    if "room_code" not in record:
        record["room_code"] = None
    return record


def username_exists(username: str) -> bool:
    with _lock:
        users = _load()
        return username.lower() in {u.lower() for u in users.keys()}


def register(username: str, password: str, role: str = "student", room_code: str = None) -> tuple:
    """
    Register a new user.
    - Teachers: room_code is None (a room is created for them after registration)
    - Students: room_code is required (must exist)
    Returns (success, message).
    """
    username = username.strip()
    if not (3 <= len(username) <= 20):
        return False, "Username must be 3-20 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username may only contain letters, numbers, _ and -."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    # Validate room code for students
    if role == "student":
        if not room_code:
            return False, "Room code is required for students."
        import rooms
        room = rooms.get_room(room_code)
        if not room:
            return False, "Invalid room code."

    with _lock:
        users = _load()
        if username.lower() in {u.lower() for u in users.keys()}:
            return False, "Username is already taken."

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        users[username] = {
            "password_hash": hashed.decode("utf-8"),
            "role": role,
            "real_name": None,
            "show_real_name": False,
            "room_code": room_code.upper() if room_code else None,
        }
        _save(users)

    # Join the room for students
    if role == "student" and room_code:
        import rooms
        rooms.join_room(username, room_code)

    return True, "Account created."


def verify_login(username: str, password: str) -> tuple:
    """Returns (success, user_info_or_error)."""
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return False, "No account with that username."

        record = _migrate_user_record(username, record)
        stored_hash = record["password_hash"].encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return True, {
                "role": record["role"],
                "room_code": record.get("room_code"),
            }
        return False, "Incorrect password."


def set_room_code(username: str, room_code: str):
    """Set the room code for a user."""
    with _lock:
        users = _load()
        record = users.get(username)
        if record:
            record["room_code"] = room_code
            _save(users)


def get_role(username: str) -> str:
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return "student"
        record = _migrate_user_record(username, record)
        return record["role"]


def get_room_code(username: str) -> str | None:
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return None
        return record.get("room_code")


def get_real_name(username: str):
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return None
        record = _migrate_user_record(username, record)
        return record.get("real_name")


def set_real_name(username: str, real_name: str):
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return
        record = _migrate_user_record(username, record)
        record["real_name"] = real_name
        _save(users)


def set_show_real_name(username: str, show: bool):
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return
        record = _migrate_user_record(username, record)
        record["show_real_name"] = show
        _save(users)


def get_show_real_name(username: str) -> bool:
    with _lock:
        users = _load()
        record = users.get(username)
        if record is None:
            return False
        record = _migrate_user_record(username, record)
        return record.get("show_real_name", False)


def list_students() -> list:
    with _lock:
        users = _load()
        result = []
        for uname, record in users.items():
            record = _migrate_user_record(uname, record)
            if record.get("role") == "student":
                result.append(uname)
        return result
