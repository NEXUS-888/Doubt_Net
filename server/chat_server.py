"""
chat_server.py
--------------
WebSocket connection handler for DoubtNet.
Routes messages based on user role (student vs teacher) and scopes them per room.
"""

import asyncio
import json

import users
import rooms
import schedule as sched
import doubts
import cluster as cluster_module
import points
import protocol
from connection_manager import ConnectionManager


async def _authenticate(websocket) -> dict | None:
    """Register/login handshake. Returns {username, role, room_code} or None."""
    async for raw in websocket:
        try:
            data = protocol.decode(raw)
        except (json.JSONDecodeError, ValueError):
            await websocket.send(protocol.msg_auth_error("Malformed request."))
            continue

        msg_type = data.get("type")

        if msg_type == "register":
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", ""))
            role = str(data.get("role", "student"))
            room_code = data.get("room_code")
            room_name = data.get("room_name")

            if role == "student":
                ok, message = await asyncio.to_thread(users.register, username, password, "student", room_code)
                if ok:
                    room = await asyncio.to_thread(rooms.get_room, room_code)
                    state = await asyncio.to_thread(sched.get_current_state, room_code)
                    await websocket.send(protocol.msg_auth_ok(username, "student", state, room_code, room["name"]))
                    return {"username": username, "role": "student", "room_code": room_code}
                else:
                    await websocket.send(protocol.msg_auth_error(message))
            else:
                # Teacher registration
                if not room_name or not room_name.strip():
                    await websocket.send(protocol.msg_auth_error("Room name is required for teachers."))
                    continue
                ok, message = await asyncio.to_thread(users.register, username, password, "teacher")
                if ok:
                    # Create the room for the teacher
                    room = await asyncio.to_thread(rooms.create_room, username, room_name.strip())
                    await asyncio.to_thread(users.set_room_code, username, room["code"])
                    state = await asyncio.to_thread(sched.get_current_state, room["code"])
                    await websocket.send(protocol.msg_auth_ok(username, "teacher", state, room["code"], room["name"]))
                    return {"username": username, "role": "teacher", "room_code": room["code"]}
                else:
                    await websocket.send(protocol.msg_auth_error(message))

        elif msg_type == "login":
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", ""))
            ok, user_info = await asyncio.to_thread(users.verify_login, username, password)
            if ok:
                role = user_info["role"]
                room_code = user_info["room_code"]

                # Handle legacy user without a room
                if not room_code:
                    await websocket.send(protocol.msg_needs_room(role))
                    # Wait for room creation/joining message
                    async for next_raw in websocket:
                        try:
                            next_data = protocol.decode(next_raw)
                        except:
                            await websocket.send(protocol.msg_auth_error("Malformed request."))
                            break
                        
                        next_type = next_data.get("type")
                        if next_type == "create_room" and role == "teacher":
                            r_name = str(next_data.get("room_name", "")).strip()
                            if not r_name:
                                await websocket.send(protocol.msg_auth_error("Room name required."))
                                continue
                            room = await asyncio.to_thread(rooms.create_room, username, r_name)
                            await asyncio.to_thread(users.set_room_code, username, room["code"])
                            state = await asyncio.to_thread(sched.get_current_state, room["code"])
                            await websocket.send(protocol.msg_auth_ok(username, "teacher", state, room["code"], room["name"]))
                            return {"username": username, "role": "teacher", "room_code": room["code"]}
                        elif next_type == "join_room" and role == "student":
                            r_code = str(next_data.get("room_code", "")).strip()
                            join_ok, join_res = await asyncio.to_thread(rooms.join_room, username, r_code)
                            if join_ok:
                                await asyncio.to_thread(users.set_room_code, username, join_res["code"])
                                state = await asyncio.to_thread(sched.get_current_state, join_res["code"])
                                await websocket.send(protocol.msg_auth_ok(username, "student", state, join_res["code"], join_res["name"]))
                                return {"username": username, "role": "student", "room_code": join_res["code"]}
                            else:
                                await websocket.send(protocol.msg_auth_error(join_res))
                        else:
                            await websocket.send(protocol.msg_auth_error("Please create or join a room first."))
                    return None

                room = await asyncio.to_thread(rooms.get_room, room_code)
                state = await asyncio.to_thread(sched.get_current_state, room_code)
                await websocket.send(protocol.msg_auth_ok(username, role, state, room_code, room["name"]))
                return {"username": username, "role": role, "room_code": room_code}
            else:
                await websocket.send(protocol.msg_auth_error(user_info))

        else:
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
        await manager.kick_username(username)

    await manager.add(websocket, username, role, room_code)
    print(f"[+] {username} ({role}) authenticated from {addr} in room {room_code}")

    online_users = await manager.usernames_in_room(room_code)
    await manager.broadcast_to_room(room_code, protocol.msg_presence(online_users))

    sch = sched.get_schedule(room_code)
    ws = _week_start(sch)

    try:
        async for raw in websocket:
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
                    await _handle_student_message(websocket, manager, username, msg_type, data, ws, room_code)
                elif role == "teacher":
                    await _handle_teacher_message(websocket, manager, username, msg_type, data, ws, room_code)
                else:
                    await websocket.send(protocol.msg_error("Unknown role."))
            except Exception as e:
                print(f"[!] Error handling {msg_type} from {username} in room {room_code}: {e}")
                await websocket.send(protocol.msg_error(f"Server error: {str(e)[:100]}"))

    except Exception as e:
        print(f"[!] Connection error with {username} ({addr}) in room {room_code}: {e}")
    finally:
        await manager.remove(websocket)
        print(f"[-] {username} disconnected: {addr} from room {room_code}")
        online_users = await manager.usernames_in_room(room_code)
        await manager.broadcast_to_room(room_code, protocol.msg_presence(online_users))


async def _handle_student_message(websocket, manager, username, msg_type, data, ws, room_code):
    if msg_type == "get_state":
        state = sched.get_current_state(room_code)
        await websocket.send(protocol.encode(state))

    elif msg_type == "submit_doubt":
        text = str(data.get("text", "")).strip()
        urgency = str(data.get("urgency", "clarification"))
        state = sched.get_current_state(room_code)
        if state.get("phase") not in ("doubt_window", "grace_period"):
            await websocket.send(protocol.msg_error("Doubt window is not open."))
            return
        day = state.get("day", 1)
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
        await asyncio.to_thread(doubts.autosave_draft, username, text, ws, room_code)
        await websocket.send(protocol.msg_draft_saved())

    elif msg_type == "get_draft":
        draft = await asyncio.to_thread(doubts.get_draft, username, ws, room_code)
        await websocket.send(protocol.encode({"type": "draft", "text": draft}))

    elif msg_type == "pin_doubt":
        if role == "teacher":
            doubt_id = data.get("id")
            await asyncio.to_thread(sched.set_pinned_doubt, doubt_id, room_code)
            new_state = await asyncio.to_thread(sched.get_current_state, room_code)
            await manager.broadcast_to_room(room_code, protocol.msg_state(new_state))

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


async def _handle_teacher_message(websocket, manager, username, msg_type, data, ws, room_code):
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
        await websocket.send(protocol.msg_clusters(clusters))

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
