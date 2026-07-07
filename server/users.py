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
from typing import Optional

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

    # Migrate single room_code -> room_codes list
    if "room_codes" not in record:
        old_code = record.pop("room_code", None)
        record["room_codes"] = [old_code] if old_code else []
    # Clean up leftover room_code key if it still exists
    record.pop("room_code", None)

    return record


def _find_user_record(users: dict, username: str) -> tuple:
    """Helper to find a user record case-insensitively. Returns (exact_key, record) or (None, None)."""
    if username in users:
        return username, users[username]
    target_lower = username.lower()
    for k, v in users.items():
        if k.lower() == target_lower:
            return k, v
    return None, None


def username_exists(username: str) -> bool:
    with _lock:
        users = _load()
        key, _ = _find_user_record(users, username)
        return key is not None


def register(username: str, password: str, role: str = "student") -> tuple:
    """
    Register a new user. Room assignment is handled separately via the
    room picker after registration.
    Returns (success, message).
    """
    username = username.strip()
    if not (3 <= len(username) <= 20):
        return False, "Username must be 3-20 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username may only contain letters, numbers, _ and -."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not (any(c.isdigit() for c in password) and any(c.isalpha() for c in password)):
        return False, "Password must contain both letters and numbers."

    with _lock:
        users = _load()
        key, _ = _find_user_record(users, username)
        if key is not None:
            return False, "Username is already taken."

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        users[username.lower()] = {
            "password_hash": hashed.decode("utf-8"),
            "role": role,
            "real_name": None,
            "show_real_name": False,
            "room_codes": [],
        }
        _save(users)

    return True, "Account created."


def verify_login(username: str, password: str) -> tuple:
    """Returns (success, user_info_or_error)."""
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return False, "No account with that username."

        record = _migrate_user_record(key, record)
        stored_hash = record["password_hash"].encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return True, {
                "role": record["role"],
                "room_codes": record.get("room_codes", []),
            }
        return False, "Incorrect password."


def add_room_code(username: str, room_code: str):
    """Add a room code to the user's list (no duplicates)."""
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record:
            record = _migrate_user_record(key, record)
            if room_code not in record["room_codes"]:
                record["room_codes"].append(room_code)
            _save(users)


def remove_room_code(username: str, room_code: str):
    """Remove a room code from the user's list."""
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record:
            record = _migrate_user_record(key, record)
            if room_code in record["room_codes"]:
                record["room_codes"].remove(room_code)
            _save(users)


def get_room_codes(username: str) -> list:
    """Get all room codes for a user."""
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return []
        record = _migrate_user_record(key, record)
        return record.get("room_codes", [])


def set_room_code(username: str, room_code: str):
    """Legacy compat: adds the room code to the user's list."""
    add_room_code(username, room_code)


def get_room_code(username: str) -> Optional[str]:
    """Legacy compat: returns the first room code or None."""
    codes = get_room_codes(username)
    return codes[0] if codes else None


def get_role(username: str) -> str:
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return "student"
        record = _migrate_user_record(key, record)
        return record["role"]


def get_real_name(username: str):
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return None
        record = _migrate_user_record(key, record)
        return record.get("real_name")


def set_real_name(username: str, real_name: str):
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return
        record = _migrate_user_record(key, record)
        record["real_name"] = real_name
        _save(users)


def set_show_real_name(username: str, show: bool):
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return
        record = _migrate_user_record(key, record)
        record["show_real_name"] = show
        _save(users)


def get_show_real_name(username: str) -> bool:
    with _lock:
        users = _load()
        key, record = _find_user_record(users, username)
        if record is None:
            return False
        record = _migrate_user_record(key, record)
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
