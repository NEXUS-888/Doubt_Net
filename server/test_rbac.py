"""
Self-contained integration test for H-1 Role-Based Access Control (RBAC).
Starts a local WebSocket server, dynamically registers a student and teacher,
creates/joins a room, and verifies role restrictions.
"""

import asyncio
import json
import websockets
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connection_manager import ConnectionManager
from chat_server import handle_connection

TEST_PORT = 9999

async def recv_json_msg(ws):
    """Read from websocket, skipping async broadcasts like presence and state_update."""
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("type") in ("presence", "state_update", "doubt_count"):
            print(f"[TEST CLIENT] Ignored async broadcast: {msg.get('type')}")
            continue
        return msg

async def run_test():
    manager = ConnectionManager()

    async def handler(websocket):
        await handle_connection(websocket, manager)

    # Start local websocket server on TEST_PORT
    server = await websockets.serve(handler, "localhost", TEST_PORT)
    print(f"[TEST] Test server started on port {TEST_PORT}")

    try:
        room_code = None
        
        # 1. Register and login as a new teacher, then create a room
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            import random
            teacher_username = f"teacher_rbac_{random.randint(1000, 9999)}"
            print(f"[TEST] Registering teacher: {teacher_username}")
            
            await ws.send(json.dumps({
                "type": "register",
                "username": teacher_username,
                "password": "Password123",
                "role": "teacher"
            }))
            
            # Must read both auth_ok and rooms_list
            resp1 = await recv_json_msg(ws)
            assert resp1.get("type") == "auth_ok", f"Expected auth_ok, got {resp1}"
            resp2 = await recv_json_msg(ws)
            assert resp2.get("type") == "rooms_list", f"Expected rooms_list, got {resp2}"
            
            # Create a room
            await ws.send(json.dumps({
                "type": "create_room",
                "room_name": "RBAC Test Room"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "room_entered", f"Expected room_entered, got {resp}"
            room_code = resp.get("room_code")
            print(f"[TEST] Teacher created room with code: {room_code}")

            # Verify teacher can pin a doubt (should not throw Unauthorized)
            await ws.send(json.dumps({
                "type": "pin_doubt",
                "id": "doubt_123"
            }))
            # Verify no unauthorized error is returned
            try:
                resp = await asyncio.wait_for(recv_json_msg(ws), timeout=1.0)
                print("[TEST] Teacher pin_doubt response:", resp)
                assert resp.get("type") != "error" or "Unauthorized" not in resp.get("message", ""), "Teacher should be authorized to pin doubts"
            except asyncio.TimeoutError:
                print("[TEST] Teacher pin_doubt request sent successfully (no error received).")

        # 2. Register and login as a new student, then join the room
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            student_username = f"student_rbac_{random.randint(1000, 9999)}"
            print(f"[TEST] Registering student: {student_username}")
            
            await ws.send(json.dumps({
                "type": "register",
                "username": student_username,
                "password": "Password123",
                "role": "student"
            }))
            
            # Must read both auth_ok and rooms_list
            resp1 = await recv_json_msg(ws)
            assert resp1.get("type") == "auth_ok", f"Expected auth_ok, got {resp1}"
            resp2 = await recv_json_msg(ws)
            assert resp2.get("type") == "rooms_list", f"Expected rooms_list, got {resp2}"
            
            # Join the room
            await ws.send(json.dumps({
                "type": "join_room",
                "room_code": room_code
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "room_entered", f"Expected room_entered, got {resp}"
            print("[TEST] Student successfully joined the room.")

            # Attempt teacher action: set_schedule
            await ws.send(json.dumps({
                "type": "set_schedule",
                "schedule": {}
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "error", f"Expected error for student set_schedule, got {resp}"
            assert "Unauthorized" in resp.get("message", ""), f"Expected Unauthorized error message, got: {resp.get('message')}"
            print("[TEST] Student blocked from set_schedule: ", resp.get("message"))

            # Attempt teacher action: pin_doubt
            await ws.send(json.dumps({
                "type": "pin_doubt",
                "id": "doubt_123"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "error", f"Expected error for student pin_doubt, got {resp}"
            assert "Unauthorized" in resp.get("message", ""), f"Expected Unauthorized error message, got: {resp.get('message')}"
            print("[TEST] Student blocked from pin_doubt: ", resp.get("message"))

        # 3. Connect as teacher and attempt student-only action
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Login as the teacher we registered
            await ws.send(json.dumps({
                "type": "login",
                "username": teacher_username,
                "password": "Password123"
            }))
            
            # Must read both auth_ok and rooms_list
            resp1 = await recv_json_msg(ws)
            assert resp1.get("type") == "auth_ok", f"Expected auth_ok, got {resp1}"
            resp2 = await recv_json_msg(ws)
            assert resp2.get("type") == "rooms_list", f"Expected rooms_list, got {resp2}"
            
            # Select the room
            await ws.send(json.dumps({
                "type": "select_room",
                "room_code": room_code
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "room_entered", f"Expected room_entered, got {resp}"
            
            # Attempt student action: autosave_draft
            await ws.send(json.dumps({
                "type": "autosave_draft",
                "text": "Teacher draft"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "error", f"Expected error for teacher autosave_draft, got {resp}"
            assert "Unauthorized" in resp.get("message", ""), f"Expected Unauthorized error message, got: {resp.get('message')}"
            print("[TEST] Teacher blocked from autosave_draft: ", resp.get("message"))

        print("[TEST] ALL RBAC TESTS PASSED SUCCESSFULLY!")
        
    finally:
        server.close()
        await server.wait_closed()
        print("[TEST] Test server closed.")

if __name__ == "__main__":
    asyncio.run(run_test())
