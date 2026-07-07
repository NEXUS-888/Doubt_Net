"""
chat_server.py
--------------
WebSocket connection handler for DoubtNet.
Routes messages based on user role (student vs teacher) and scopes them per room.
"""

import asyncio
import json
import time
from typing import Optional

import users
import rooms
import schedule as sched
import doubts
import cluster as cluster_module
import points
import protocol
from connection_manager import ConnectionManager
import functools

async def _to_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    func_call = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


# --------------- Rate Limiter (H-2) ---------------

MAX_MESSAGES_PER_SECOND = 15
MAX_RATE_VIOLATIONS = 50
MAX_DOUBTS_PER_STUDENT_PER_DAY = 10
VALID_URGENCIES = {"clarification", "feedback", "blocking"}
MAX_DOUBT_TEXT_LENGTH = 500
MIN_DOUBT_TEXT_LENGTH = 10
MAX_DRAFT_TEXT_LENGTH = 2000


class _RateLimiter:
    """Sliding-window rate limiter per connection."""

    def __init__(self, max_per_second: int = MAX_MESSAGES_PER_SECOND):
        self._timestamps: list[float] = []
        self._max_per_second = max_per_second
        self._violations = 0

    def check(self) -> bool:
        """Returns True if the message is allowed, False if rate-limited."""
        now = time.monotonic()
        # Keep only timestamps within the last second
        self._timestamps = [t for t in self._timestamps if now - t < 1.0]
        if len(self._timestamps) >= self._max_per_second:
            self._violations += 1
            return False
        self._timestamps.append(now)
        return True

    @property
    def should_disconnect(self) -> bool:
        return self._violations > MAX_RATE_VIOLATIONS


async def _send_rooms_list(websocket, username: str, role: str):
    """Helper: fetch user's rooms and send the rooms_list message."""
    room_codes = await _to_thread(users.get_room_codes, username)
    room_list = await _to_thread(rooms.get_rooms_by_codes, room_codes)
    await websocket.send(protocol.msg_rooms_list(username, role, room_list))


async def _authenticate(websocket) -> Optional[dict]:
    """Register/login handshake + room picker. Returns {username, role, room_code} or None."""
    username = None
    role = None
    authenticated = False

    async for raw in websocket:
        try:
            data = protocol.decode(raw)
        except (json.JSONDecodeError, ValueError):
            await websocket.send(protocol.msg_auth_error("Malformed request."))
            continue

        msg_type = data.get("type")

        # ---- Phase 1: Register or Login ----
        if msg_type == "register" and not authenticated:
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", ""))
            role = str(data.get("role", "student"))

            ok, message = await _to_thread(users.register, username, password, role)
            if ok:
                authenticated = True
                print(f"[AUTH] {username} registered as {role}")
                await websocket.send(protocol.msg_auth_ok(username, role, {}))
                await _send_rooms_list(websocket, username, role)
            else:
                print(f"[AUTH] Registration failed for {username}: {message}")
                await websocket.send(protocol.msg_auth_error(message))

        elif msg_type == "login" and not authenticated:
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", ""))
            ok, user_info = await _to_thread(users.verify_login, username, password)
            if ok:
                role = user_info["role"]
                authenticated = True
                print(f"[AUTH] {username} logged in as {role}")
                await websocket.send(protocol.msg_auth_ok(username, role, {}))
                await _send_rooms_list(websocket, username, role)
            else:
                print(f"[AUTH] Login failed for {username}: {user_info}")
                await websocket.send(protocol.msg_auth_error(user_info))

        # ---- Phase 2: Room Picker actions (after authenticated) ----
        elif msg_type == "select_room" and authenticated:
            room_code = str(data.get("room_code", "")).strip().upper()
            print(f"[ROOM] {username} selecting room {room_code}")
            # Verify user belongs to this room
            user_codes = await _to_thread(users.get_room_codes, username)
            print(f"[ROOM] {username} has rooms: {user_codes}")
            if room_code not in [c.upper() for c in user_codes]:
                print(f"[ROOM] {username} NOT member of {room_code}")
                await websocket.send(protocol.msg_auth_error("You are not a member of that room."))
                continue
            room = await _to_thread(rooms.get_room, room_code)
            if not room:
                print(f"[ROOM] Room {room_code} not found")
                await websocket.send(protocol.msg_auth_error("Room not found."))
                continue
            state = await _to_thread(sched.get_current_state, room_code)
            print(f"[ROOM] {username} entering room {room_code} ({room['name']})")
            await websocket.send(protocol.msg_room_entered(username, role, state, room_code, room["name"]))
            return {"username": username, "role": role, "room_code": room_code}

        elif msg_type == "create_room" and authenticated and role == "teacher":
            room_name = str(data.get("room_name", "")).strip()
            room_code = data.get("room_code")
            if not room_name or len(room_name) < 3 or len(room_name) > 50:
                await websocket.send(protocol.msg_auth_error("Room name must be 3-50 characters."))
                continue
            import re
            if not re.match(r'^[a-zA-Z0-9\s\-_]+$', room_name):
                await websocket.send(protocol.msg_auth_error("Room name contains invalid characters."))
                continue
            room = await _to_thread(rooms.create_room, username, room_name, room_code)
            await _to_thread(users.add_room_code, username, room["code"])
            # Auto-enter the created room
            state = await _to_thread(sched.get_current_state, room["code"])
            await websocket.send(protocol.msg_room_entered(username, role, state, room["code"], room["name"]))
            return {"username": username, "role": role, "room_code": room["code"]}

        elif msg_type == "join_room" and authenticated and role == "student":
            room_code = str(data.get("room_code", "")).strip().upper()
            print(f"[ROOM] Student {username} joining room {room_code}")
            if not room_code:
                await websocket.send(protocol.msg_auth_error("Room code is required."))
                continue
            join_ok, join_res = await _to_thread(rooms.join_room, username, room_code)
            print(f"[ROOM] join_room result: ok={join_ok}, res={join_res}")
            if join_ok:
                await _to_thread(users.add_room_code, username, join_res["code"])
                # Auto-enter the joined room
                state = await _to_thread(sched.get_current_state, join_res["code"])
                print(f"[ROOM] Student {username} entering room {join_res['code']} ({join_res['name']})")
                await websocket.send(protocol.msg_room_entered(username, role, state, join_res["code"], join_res["name"]))
                return {"username": username, "role": role, "room_code": join_res["code"]}
            else:
                print(f"[ROOM] Join failed for {username}: {join_res}")
                await websocket.send(protocol.msg_auth_error(join_res))

        elif not authenticated:
            await websocket.send(protocol.msg_auth_error("Register or log in first."))

    return None


def _week_start(schedule: dict) -> str:
    return schedule.get("week_start", "")


async def handle_connection(websocket, manager: ConnectionManager):
    addr = websocket.remote_address
    print(f"[+] Connection opened: {addr}")

    auth = await _authenticate(websocket)
    if auth is None:
        print(f"[!] Connection {addr} closed before authenticating.")
        return

    username = auth["username"]
    role = auth["role"]
    room_code = auth["room_code"]

    if await manager.is_username_online(username):
        print(f"[!] {username} already online — kicking old connection")
        await manager.kick_username(username)

    await manager.add(websocket, username, role, room_code)
    print(f"[+] {username} ({role}) authenticated from {addr} in room {room_code}")

    online_users = await manager.usernames_in_room(room_code)
    await manager.broadcast_to_room(room_code, protocol.msg_presence(online_users))

    sch = sched.get_schedule(room_code)
    ws = _week_start(sch)
    rate_limiter = _RateLimiter()

    try:
        async for raw in websocket:
            # --- Rate limiting (H-2) ---
            if not rate_limiter.check():
                try:
                    await websocket.send(protocol.msg_error("Rate limit exceeded. Slow down."))
                except Exception:
                    pass
                if rate_limiter.should_disconnect:
                    print(f"[!] Rate limit abuse by {username} — disconnecting")
                    await websocket.close(1008, "Rate limit abuse")
                    return
                continue

            try:
                data = protocol.decode(raw)
            except (json.JSONDecodeError, ValueError):
                await websocket.send(protocol.msg_error("Malformed message."))
                continue

            msg_type = data.get("type")
            sch = sched.get_schedule(room_code)
            ws = _week_start(sch)

            try:
                if role == "student":
                    await _handle_student_message(websocket, manager, username, msg_type, data, ws, room_code, role)
                elif role == "teacher":
                    await _handle_teacher_message(websocket, manager, username, msg_type, data, ws, room_code, role)
                else:
                    await websocket.send(protocol.msg_error("Unknown role."))
            except Exception as e:
                print(f"[!] Error handling {msg_type} from {username} in room {room_code}: {e}")
                await websocket.send(protocol.msg_error(f"Server error: {str(e)[:100]}"))

    except Exception as e:
        print(f"[!] Connection error with {username} ({addr}) in room {room_code}: {type(e).__name__}: {e}")
    finally:
        await manager.remove(websocket)
        close_code = getattr(websocket, "close_code", None)
        close_reason = getattr(websocket, "close_reason", None)
        print(f"[-] {username} disconnected: {addr} from room {room_code} (code={close_code}, reason={close_reason})")
        online_users = await manager.usernames_in_room(room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_presence(online_users))


async def _handle_student_message(websocket, manager, username, msg_type, data, ws, room_code, role):
    # Enforce role boundaries for student-only messages
    student_only_messages = {"submit_doubt", "autosave_draft", "get_draft", "get_my_doubts", "get_my_points"}
    if msg_type in student_only_messages and role != "student":
        await websocket.send(protocol.msg_error("Unauthorized: Student role required."))
        return

    # Enforce role boundaries for teacher-only messages sent by students
    teacher_messages = {
        "get_schedule", "set_schedule", "get_doubts", "moderate_doubt", 
        "auto_cluster", "get_clusters", "merge_clusters", "split_cluster", 
        "undo_cluster", "finalize_clusters", "get_resolution_queue", 
        "resolve_doubt", "start_demo_mode", "stop_demo_mode", 
        "toggle_allow_all_doubts", "pin_doubt"
    }
    if msg_type in teacher_messages and role != "teacher":
        await websocket.send(protocol.msg_error("Unauthorized: Teacher role required."))
        return

    if msg_type == "get_state":
        state = sched.get_current_state(room_code)
        await websocket.send(protocol.encode(state))

    elif msg_type == "submit_doubt":
        text = str(data.get("text", "")).strip()
        urgency = str(data.get("urgency", "clarification"))

        # --- Input validation (H-3) ---
        if len(text) < MIN_DOUBT_TEXT_LENGTH:
            await websocket.send(protocol.msg_error(f"Doubt must be at least {MIN_DOUBT_TEXT_LENGTH} characters."))
            return
        if len(text) > MAX_DOUBT_TEXT_LENGTH:
            await websocket.send(protocol.msg_error(f"Doubt must be at most {MAX_DOUBT_TEXT_LENGTH} characters."))
            return
        if urgency not in VALID_URGENCIES:
            await websocket.send(protocol.msg_error(f"Invalid urgency. Must be one of: {', '.join(sorted(VALID_URGENCIES))}."))
            return

        state = sched.get_current_state(room_code)
        if state.get("phase") not in ("doubt_window", "grace_period"):
            await websocket.send(protocol.msg_error("Doubt window is not open."))
            return
        day = state.get("day", 1)

        # --- Per-student doubt limit (H-4) ---
        existing_count = doubts.count_student_doubts_for_day(username, day, ws, room_code)
        if existing_count >= MAX_DOUBTS_PER_STUDENT_PER_DAY:
            await websocket.send(protocol.msg_error(f"Doubt limit reached ({MAX_DOUBTS_PER_STUDENT_PER_DAY} per day). Try again tomorrow."))
            return

        result = doubts.submit_doubt(username, text, urgency, day, ws, room_code)
        await websocket.send(protocol.msg_doubt_submitted(result["doubt_id"], result["status"]))
        if not result.get("flagged"):
            count = doubts.get_doubt_count(ws, room_code)
            await manager.broadcast_to_room(room_code, protocol.msg_doubt_count(count))
            approved = doubts.get_approved_doubts(ws, room_code)
            flagged = doubts.get_pending_moderation(ws, room_code)
            await manager.broadcast_to_role_in_room(room_code, "teacher", protocol.msg_all_doubts(approved, flagged))

    elif msg_type == "autosave_draft":
        text = str(data.get("text", ""))
        # Cap draft size (H-3 defense-in-depth)
        if len(text) > MAX_DRAFT_TEXT_LENGTH:
            text = text[:MAX_DRAFT_TEXT_LENGTH]
        await _to_thread(doubts.autosave_draft, username, text, ws, room_code)
        await websocket.send(protocol.msg_draft_saved())

    elif msg_type == "get_draft":
        draft = await _to_thread(doubts.get_draft, username, ws, room_code)
        await websocket.send(protocol.encode({"type": "draft", "text": draft}))

    elif msg_type == "get_my_doubts":
        my_doubts = doubts.get_student_doubts(username, ws, room_code)
        public = [
            {"id": d["id"], "text": d["text"], "urgency": d["urgency"],
             "day": d["day"], "status": d["status"]}
            for d in my_doubts
        ]
        await websocket.send(protocol.msg_student_doubts(public))

    elif msg_type == "get_leaderboard":
        entries = points.get_leaderboard(ws, room_code)
        await websocket.send(protocol.msg_leaderboard(entries))

    elif msg_type == "set_real_name":
        real_name = str(data.get("real_name", ""))
        users.set_real_name(username, real_name)
        await websocket.send(protocol.encode({"type": "real_name_set"}))

    elif msg_type == "toggle_name_visibility":
        show = bool(data.get("show_real", False))
        users.set_show_real_name(username, show)
        await websocket.send(protocol.encode({"type": "visibility_toggled"}))

    elif msg_type == "get_my_points":
        student_points = points.get_student_points(username, room_code)
        await websocket.send(protocol.encode({"type": "student_points", "data": student_points}))

    else:
        await websocket.send(protocol.msg_error(f"Unknown message type: {msg_type}"))


async def _handle_teacher_message(websocket, manager, username, msg_type, data, ws, room_code, role):
    # Enforce role boundaries for teacher-only messages
    if role != "teacher":
        await websocket.send(protocol.msg_error("Unauthorized: Teacher role required."))
        return

    # Enforce role boundaries for student-only messages sent by teachers
    student_only_messages = {"submit_doubt", "autosave_draft", "get_draft", "get_my_doubts", "get_my_points"}
    if msg_type in student_only_messages and role != "student":
        await websocket.send(protocol.msg_error("Unauthorized: Student role required."))
        return

    if msg_type == "get_state":
        state = sched.get_current_state(room_code)
        await websocket.send(protocol.encode(state))

    elif msg_type == "get_schedule":
        sch = sched.get_schedule(room_code)
        await websocket.send(protocol.msg_schedule_info(sch))

    elif msg_type == "set_schedule":
        schedule_data = data.get("schedule", {})
        ok, message = sched.set_schedule(schedule_data, room_code)
        if ok:
            await websocket.send(protocol.msg_schedule_info(schedule_data))
            state = sched.get_current_state(room_code)
            await manager.broadcast_to_room(room_code, protocol.msg_state_update(state))
        else:
            await websocket.send(protocol.msg_error(message))

    elif msg_type == "get_doubts":
        approved = doubts.get_approved_doubts(ws, room_code)
        flagged = doubts.get_pending_moderation(ws, room_code)
        await websocket.send(protocol.msg_all_doubts(approved, flagged))

    elif msg_type == "moderate_doubt":
        doubt_id = str(data.get("doubt_id", ""))
        action = str(data.get("action", ""))  # "approve" or "reject"
        if action == "approve":
            doubts.update_doubt_status(doubt_id, "approved", ws, room_code)
            count = doubts.get_doubt_count(ws, room_code)
            await manager.broadcast_to_room(room_code, protocol.msg_doubt_count(count))
        elif action == "reject":
            doubts.update_doubt_status(doubt_id, "rejected", ws, room_code)
        await websocket.send(protocol.encode({"type": "moderation_done", "doubt_id": doubt_id}))
        # Broadcast updated lists to all teachers in the room
        approved = doubts.get_approved_doubts(ws, room_code)
        flagged = doubts.get_pending_moderation(ws, room_code)
        await manager.broadcast_to_role_in_room(room_code, "teacher", protocol.msg_all_doubts(approved, flagged))

    elif msg_type == "auto_cluster":
        approved = doubts.get_approved_doubts(ws, room_code)
        clusters = cluster_module.auto_cluster(approved)
        for cid, cdata in clusters.items():
            for did in cdata["doubt_ids"]:
                doubts.set_cluster_id(did, cid, ws, room_code)
        doubts.store_clusters(ws, clusters, room_code)
        warning = None
        if not cluster_module.HAS_SKLEARN:
            warning = "scikit-learn is not installed on the server. Falling back to basic 1-to-1 clustering."
        await websocket.send(protocol.msg_clusters(clusters, warning=warning))

    elif msg_type == "get_clusters":
        clusters = doubts.get_clusters(ws, room_code)
        await websocket.send(protocol.msg_clusters(clusters))

    elif msg_type == "merge_clusters":
        clusters = doubts.get_clusters(ws, room_code)
        cluster_a = str(data.get("cluster_a", ""))
        cluster_b = str(data.get("cluster_b", ""))
        clusters = cluster_module.merge_clusters(clusters, cluster_a, cluster_b)
        _sync_clusters_with_doubts(clusters, ws, room_code)
        await websocket.send(protocol.msg_cluster_updated(clusters))

    elif msg_type == "split_cluster":
        clusters = doubts.get_clusters(ws, room_code)
        cluster_id = str(data.get("cluster_id", ""))
        doubt_ids = list(data.get("doubt_ids", []))
        clusters = cluster_module.split_cluster(clusters, cluster_id, doubt_ids)
        _sync_clusters_with_doubts(clusters, ws, room_code)
        await websocket.send(protocol.msg_cluster_updated(clusters))

    elif msg_type == "undo_cluster":
        clusters = doubts.get_clusters(ws, room_code)
        clusters = cluster_module.undo_last_action(clusters)
        _sync_clusters_with_doubts(clusters, ws, room_code)
        await websocket.send(protocol.msg_cluster_updated(clusters))

    elif msg_type == "finalize_clusters":
        clusters = doubts.get_clusters(ws, room_code)
        cluster_module.finalize_clusters(clusters)
        all_doubts = doubts.get_doubts_for_week(ws, room_code)
        approved = [d for d in all_doubts if d.get("status") == "approved"]
        points.compute_points(clusters, approved, ws, room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_points_finalized())

    elif msg_type == "get_leaderboard":
        entries = points.get_leaderboard(ws, room_code)
        await websocket.send(protocol.msg_leaderboard(entries))

    elif msg_type == "get_resolution_queue":
        approved = doubts.get_approved_doubts(ws, room_code)
        clusters = doubts.get_clusters(ws, room_code)
        resolved = doubts.get_resolved_clusters(ws, room_code)
        unresolved_clusters = {cid: cdata for cid, cdata in clusters.items() if cid not in resolved}
        queue = _build_resolution_queue(unresolved_clusters)
        await websocket.send(protocol.msg_resolution_queue(queue))

    elif msg_type == "resolve_doubt":
        cluster_id = str(data.get("cluster_id", ""))
        doubts.mark_cluster_resolved(cluster_id, ws, room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_doubt_resolved(cluster_id))
        await websocket.send(protocol.encode({"type": "resolve_confirmed", "cluster_id": cluster_id}))

    elif msg_type == "start_demo_mode":
        sched.set_demo_mode(True, room_code)
        state = sched.get_current_state(room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_state_update(state))

    elif msg_type == "stop_demo_mode":
        sched.set_demo_mode(False, room_code)
        state = sched.get_current_state(room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_state_update(state))

    elif msg_type == "toggle_allow_all_doubts":
        enabled = bool(data.get("enabled", False))
        sched.set_allow_all_doubts(enabled, room_code)
        state = sched.get_current_state(room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_state_update(state))

    elif msg_type == "pin_doubt":
        doubt_id = data.get("id")
        await _to_thread(sched.set_pinned_doubt, doubt_id, room_code)
        new_state = await _to_thread(sched.get_current_state, room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_state_update(new_state))

    else:
        await websocket.send(protocol.msg_error(f"Unknown message type: {msg_type}"))


def _sync_clusters_with_doubts(clusters: dict, ws: str, room_code: str):
    """Update cluster_id in each doubt entry to match cluster state."""
    doubts.store_clusters(ws, clusters, room_code)
    all_doubts = doubts.get_doubts_for_week(ws, room_code)
    for cid, cdata in clusters.items():
        for did in cdata["doubt_ids"]:
            doubts.set_cluster_id(did, cid, ws, room_code)


def _build_resolution_queue(clusters: dict) -> list:
    """Sort clusters by priority for day 5 resolution."""
    ranked = []
    for cid, cdata in clusters.items():
        freq = cdata.get("size", 1)
        urgency = cdata.get("avg_urgency_score", 0)
        priority = freq * urgency
        ranked.append({
            "cluster_id": cid,
            "representative_text": cdata.get("representative_text", ""),
            "frequency": freq,
            "avg_urgency_score": urgency,
            "priority_score": round(priority, 2),
            "doubt_ids": cdata.get("doubt_ids", []),
        })
    ranked.sort(key=lambda x: -x["priority_score"])
    return ranked
