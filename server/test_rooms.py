"""
Self-contained integration test for Room Management.
Starts a local WebSocket server and verifies:
- Teacher can create a room
- Student can join with valid code
- Student cannot join with invalid code
- Student cannot create a room (teacher-only)
- Teacher can select an existing room
"""

import asyncio
import json
import random
import websockets
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connection_manager import ConnectionManager
from chat_server import handle_connection

TEST_PORT = 9996


async def recv_json_msg(ws, timeout=5.0):
    """Read from websocket, skipping async broadcasts like presence and state_update."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") in ("presence", "state_update", "doubt_count"):
            print(f"[TEST CLIENT] Ignored async broadcast: {msg.get('type')}")
            continue
        return msg


async def run_test():
    manager = ConnectionManager()

    async def handler(websocket):
        await handle_connection(websocket, manager)

    server = await websockets.serve(handler, "localhost", TEST_PORT)
    print(f"[TEST] Test server started on port {TEST_PORT}")

    passed = 0
    failed = 0

    try:
        suffix = random.randint(10000, 99999)
        teacher_name = f"teacher_room_{suffix}"
        student1_name = f"student1_room_{suffix}"
        student2_name = f"student2_room_{suffix}"
        room_code = None

        # ── Test 1: Teacher creates a room ───────────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Register teacher
            await ws.send(json.dumps({
                "type": "register",
                "username": teacher_name,
                "password": "TeacherPass1",
                "role": "teacher"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "auth_ok", f"Teacher register failed: {resp}"
            await recv_json_msg(ws)  # rooms_list

            # Create room
            await ws.send(json.dumps({
                "type": "create_room",
                "room_name": "Room Test Class"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "room_entered" and resp.get("room_code"):
                room_code = resp.get("room_code")
                print(f"[PASS] Test 1: Teacher created room '{resp.get('room_name')}' — code: {room_code}")
                passed += 1
            else:
                print(f"[FAIL] Test 1: Expected room_entered with room_code, got {resp}")
                failed += 1

        # ── Test 2: Student joins with valid code ────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Register student 1
            await ws.send(json.dumps({
                "type": "register",
                "username": student1_name,
                "password": "StudentPass1",
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "auth_ok", f"Student1 register failed: {resp}"
            await recv_json_msg(ws)  # rooms_list

            # Join room with valid code
            await ws.send(json.dumps({
                "type": "join_room",
                "room_code": room_code
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "room_entered" and resp.get("room_code") == room_code:
                print(f"[PASS] Test 2: Student joined room with valid code: {room_code}")
                passed += 1
            else:
                print(f"[FAIL] Test 2: Expected room_entered for valid code, got {resp}")
                failed += 1

        # ── Test 3: Student joins with invalid code ──────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Register student 2
            await ws.send(json.dumps({
                "type": "register",
                "username": student2_name,
                "password": "StudentPass2",
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "auth_ok", f"Student2 register failed: {resp}"
            await recv_json_msg(ws)  # rooms_list

            # Join room with invalid code
            await ws.send(json.dumps({
                "type": "join_room",
                "room_code": "ZZZZZZ"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_error" and "invalid" in resp.get("message", "").lower():
                print(f"[PASS] Test 3: Invalid room code correctly rejected — {resp.get('message')}")
                passed += 1
            else:
                print(f"[FAIL] Test 3: Expected auth_error for invalid code, got {resp}")
                failed += 1

        # ── Test 4: Student cannot create a room ─────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Login as student 1
            await ws.send(json.dumps({
                "type": "login",
                "username": student1_name,
                "password": "StudentPass1"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "auth_ok", f"Student1 login failed: {resp}"
            await recv_json_msg(ws)  # rooms_list

            # Attempt to create a room (should be ignored — create_room requires role==teacher)
            await ws.send(json.dumps({
                "type": "create_room",
                "room_name": "Student Room Attempt"
            }))

            # The server's _authenticate function only handles create_room when
            # role == "teacher", so for a student it falls through to the
            # generic "not authenticated" or is simply not handled.
            # We check that the student does NOT get a room_entered response.
            try:
                resp = await asyncio.wait_for(recv_json_msg(ws, timeout=2.0), timeout=2.0)
                if resp.get("type") == "room_entered":
                    print(f"[FAIL] Test 4: Student was able to create a room!")
                    failed += 1
                else:
                    # Got an error or auth_error — that's correct
                    print(f"[PASS] Test 4: Student blocked from creating room — {resp.get('type')}: {resp.get('message', '')}")
                    passed += 1
            except asyncio.TimeoutError:
                # No response means the message was silently ignored — that's fine
                print(f"[PASS] Test 4: Student create_room silently ignored (no room_entered)")
                passed += 1

        # ── Test 5: Teacher can select an existing room ──────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Login as teacher
            await ws.send(json.dumps({
                "type": "login",
                "username": teacher_name,
                "password": "TeacherPass1"
            }))
            resp = await recv_json_msg(ws)
            assert resp.get("type") == "auth_ok", f"Teacher login failed: {resp}"
            rooms_resp = await recv_json_msg(ws)
            assert rooms_resp.get("type") == "rooms_list", f"Expected rooms_list, got {rooms_resp}"

            # Verify the room appears in the rooms_list
            room_list = rooms_resp.get("rooms", [])
            found = any(r.get("code") == room_code for r in room_list)
            if not found:
                print(f"[FAIL] Test 5: Room {room_code} not found in teacher's rooms_list: {room_list}")
                failed += 1
            else:
                # Select the room
                await ws.send(json.dumps({
                    "type": "select_room",
                    "room_code": room_code
                }))
                resp = await recv_json_msg(ws)
                if resp.get("type") == "room_entered" and resp.get("room_code") == room_code:
                    print(f"[PASS] Test 5: Teacher selected existing room: {room_code}")
                    passed += 1
                else:
                    print(f"[FAIL] Test 5: Expected room_entered, got {resp}")
                    failed += 1

        # ── Summary ──────────────────────────────────────────────────
        total = passed + failed
        print(f"\n{'='*50}")
        print(f"[TEST] Results: {passed}/{total} passed, {failed}/{total} failed")
        if failed == 0:
            print(f"[TEST] ALL {total} TESTS PASSED SUCCESSFULLY!")
        else:
            print(f"[TEST] {failed} TEST(S) FAILED!")
        print(f"{'='*50}")

    finally:
        server.close()
        await server.wait_closed()
        print("[TEST] Test server closed.")


if __name__ == "__main__":
    asyncio.run(run_test())
