"""
schedule.py
-----------
Manages the weekly class schedule and determines the current phase. Scoped per room.
"""

import json
import os
import threading
from datetime import datetime, date, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python < 3.9 fallback
    ZoneInfo = None

_lock = threading.Lock()
_DEMO_MODES = {}


def _ensure_store(room_code: str):
    import rooms
    d_dir = rooms.room_data_dir(room_code)
    path = os.path.join(d_dir, "schedule.json")
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)


def _load(room_code: str) -> dict:
    _ensure_store(room_code)
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "schedule.json")
    with open(path, "r") as f:
        return json.load(f)


def _save(data: dict, room_code: str):
    import rooms
    path = os.path.join(rooms.room_data_dir(room_code), "schedule.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def set_allow_all_doubts(enabled: bool, room_code: str):
    import time
    with _lock:
        schedule = _load(room_code)
        schedule["allow_all_doubts"] = enabled
        if enabled:
            # Auto-expire after 4 hours (14400 seconds)
            schedule["allow_all_doubts_expires"] = time.time() + 14400
        else:
            schedule["allow_all_doubts_expires"] = 0
        _save(schedule, room_code)


def set_demo_mode(enabled: bool, room_code: str):
    global _DEMO_MODES
    _DEMO_MODES[room_code] = enabled


def get_demo_mode(room_code: str) -> bool:
    return _DEMO_MODES.get(room_code, False)


def set_schedule(schedule_data: dict, room_code: str) -> tuple:
    """Store a new schedule. Returns (success, message)."""
    mode = schedule_data.get("mode", "class")
    if mode == "webinar":
        if "subject" not in schedule_data:
            return False, "Missing required field: subject"
        with _lock:
            existing = _load(room_code)
            webinar_schedule = dict(existing)
            webinar_schedule.update(schedule_data)
            webinar_schedule["mode"] = "webinar"
            webinar_schedule["subject"] = schedule_data.get("subject", existing.get("subject", "Webinar Session"))
            webinar_schedule["webinar_active"] = bool(schedule_data.get("webinar_active", False))
            webinar_schedule["week_start"] = existing.get("week_start") or webinar_schedule.get("week_start") or f"webinar_{int(datetime.now().timestamp())}"
            _save(webinar_schedule, room_code)
        return True, "Webinar session configuration saved."

    required = ["week_start", "subject", "days"]
    for key in required:
        if key not in schedule_data:
            return False, f"Missing required field: {key}"
    if not isinstance(schedule_data["days"], list) or len(schedule_data["days"]) < 1:
        return False, "Schedule must have at least one day."

    import re
    for day in schedule_data["days"]:
        for field in ["day", "date", "start", "end"]:
            if field not in day:
                return False, f"Day entry missing field: {field}"
        # Validate day range (1 to 5)
        if not (1 <= day.get("day", 0) <= 5):
            return False, "Day number must be between 1 and 5."
        # Validate YYYY-MM-DD
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(day.get("date", ""))):
            return False, "Invalid date format. Use YYYY-MM-DD."
        # Validate HH:MM
        if not re.match(r'^\d{2}:\d{2}$', str(day.get("start", ""))):
            return False, "Invalid start time format. Use HH:MM."
        if not re.match(r'^\d{2}:\d{2}$', str(day.get("end", ""))):
            return False, "Invalid end time format. Use HH:MM."
        if day["start"] >= day["end"]:
            return False, f"Start time ({day['start']}) must be before end time ({day['end']})."

    with _lock:
        schedule_data["mode"] = "class"
        schedule_data["doubt_window_minutes"] = schedule_data.get("doubt_window_minutes", 5)
        schedule_data["grace_period_seconds"] = schedule_data.get("grace_period_seconds", 90)
        _save(schedule_data, room_code)
    return True, "Schedule saved."


def get_schedule(room_code: str) -> dict:
    with _lock:
        data = _load(room_code)
        if not data:
            return {}
        return data


def _parse_time(date_str: str, time_str: str) -> datetime:
    dt_str = f"{date_str} {time_str}"
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")


def set_pinned_doubt(doubt_id: Optional[str], room_code: str):
    with _lock:
        schedule = _load(room_code)
        schedule["pinned_doubt_id"] = doubt_id
        _save(schedule, room_code)


def get_current_state(room_code: str) -> dict:
    state = _get_current_state_raw(room_code)
    with _lock:
        schedule = _load(room_code)
    pinned_id = schedule.get("pinned_doubt_id") if schedule else None
    pinned_doubt = None
    if pinned_id:
        import doubts
        p_doubt = doubts.get_doubt_by_id(pinned_id, room_code)
        if p_doubt:
            pinned_doubt = {"id": pinned_id, "text": p_doubt["text"]}
    state["pinned_doubt"] = pinned_doubt
    return state


def _get_current_state_raw(room_code: str) -> dict:
    if get_demo_mode(room_code):
        return {
            "phase": "doubt_window",
            "day": 2,
            "seconds_remaining": 120,
            "subject": "Demo Subject",
        }

    with _lock:
        schedule = _load(room_code)

    if not schedule:
        return {"phase": "no_class_today"}

    # Check if manual doubts mode is toggled on
    if schedule.get("allow_all_doubts", False):
        import time
        expires = schedule.get("allow_all_doubts_expires", 0)
        if expires and time.time() > expires:
            with _lock:
                schedule = _load(room_code)
                schedule["allow_all_doubts"] = False
                schedule["allow_all_doubts_expires"] = 0
                _save(schedule, room_code)
        else:
            return {
                "phase": "doubt_window",
                "day": 1,
                "seconds_remaining": -1,
                "subject": schedule.get("subject", "Manual Doubt Session"),
                "allow_all_doubts": True
            }

    # Handle Webinar Mode
    if schedule.get("mode") == "webinar":
        subject = schedule.get("subject", "Webinar Session")
        active = schedule.get("webinar_active", False)
        if active:
            return {
                "phase": "doubt_window",
                "day": 1,
                "seconds_remaining": -1,
                "subject": subject,
                "mode": "webinar",
                "webinar_active": True
            }
        else:
            return {
                "phase": "no_class_today",
                "day": 1,
                "seconds_remaining": 0,
                "subject": subject,
                "mode": "webinar",
                "webinar_active": False
            }

    # Use room timezone if configured, otherwise server-local time
    tz = None
    room_tz = schedule.get("timezone")
    if room_tz and ZoneInfo is not None:
        try:
            tz = ZoneInfo(room_tz)
        except (KeyError, Exception):
            pass  # Invalid timezone — fall back to server-local
    now = datetime.now(tz=tz)
    today_str = now.strftime("%Y-%m-%d")

    # Find today's class
    today_entry = None
    for day_entry in schedule.get("days", []):
        if day_entry.get("date") == today_str:
            today_entry = day_entry
            break

    if today_entry is None:
        return {"phase": "no_class_today"}

    day_num = today_entry.get("day", 1)
    start_time = _parse_time(today_str, today_entry["start"])
    end_time = _parse_time(today_str, today_entry["end"])
    doubt_minutes = schedule.get("doubt_window_minutes", 5)
    grace_seconds = schedule.get("grace_period_seconds", 90)
    subject = schedule.get("subject", "Unknown")

    if now < start_time:
        return {"phase": "before_class", "subject": subject}

    if day_num == 5:
        if start_time <= now < end_time:
            return {"phase": "resolution_session", "day": 5, "subject": subject}
        else:
            return {"phase": "after_class", "subject": subject}

    if start_time <= now < end_time:
        seconds_remaining = int((end_time - now).total_seconds())
        doubt_window_start = end_time - timedelta(minutes=doubt_minutes)
        if now >= doubt_window_start:
            return {
                "phase": "doubt_window",
                "day": day_num,
                "seconds_remaining": seconds_remaining,
                "subject": subject,
            }
        return {
            "phase": "class_active",
            "day": day_num,
            "minutes_remaining": round(seconds_remaining / 60),
            "subject": subject,
        }

    # After class — grace period
    grace_end = end_time + timedelta(seconds=grace_seconds)
    if now <= grace_end:
        seconds_remaining = int((grace_end - now).total_seconds())
        return {
            "phase": "grace_period",
            "day": day_num,
            "seconds_remaining": seconds_remaining,
            "subject": subject,
        }

    return {"phase": "after_class", "subject": subject}
