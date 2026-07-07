"""
Self-contained integration test for Input Validation (H-3),
Rate Limiting (H-2), and Doubt Limits (H-4).
Starts a local WebSocket server, sets up a room in demo mode, and verifies:
- Doubt text too short (<10 chars) → error
- Doubt text too long (>500 chars) → error
- Invalid urgency value → error
- Valid doubt submission → success
- Rate limiting: rapid messages trigger rate_limited errors
- Doubt limit: 11th doubt is rejected
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

TEST_PORT = 9997


async def recv_json_msg(ws, timeout=5.0):
    """Read from websocket, skipping async broadcasts like presence and state_update."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") in ("presence", "state_update", "doubt_count"):
            continue
        return msg


async def setup_room(manager, port):
    """Register a teacher, create a room, enable demo mode. Returns room_code."""
    suffix = random.randint(10000, 99999)
    teacher_name = f"teacher_val_{suffix}"

    async with websockets.connect(f"ws://localhost:{port}") as ws:
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
            "room_name": "Validation Test Room"
        }))
        resp = await recv_json_msg(ws)
        assert resp.get("type") == "room_entered", f"Expected room_entered, got {resp}"
        room_code = resp.get("room_code")
        print(f"[SETUP] Teacher '{teacher_name}' created room: {room_code}")

        # Enable demo mode so doubt window is always open
        await ws.send(json.dumps({"type": "start_demo_mode"}))
        # Consume the state_update broadcast (filtered by recv_json_msg)
        try:
            await asyncio.wait_for(recv_json_msg(ws), timeout=1.0)
        except asyncio.TimeoutError:
            pass  # state_update was filtered, that's fine
        print("[SETUP] Demo mode enabled")

    return room_code, teacher_name


async def connect_student(port, room_code):
    """Register a student and join the room. Returns (ws, student_name)."""
    suffix = random.randint(10000, 99999)
    student_name = f"student_val_{suffix}"

    ws = await websockets.connect(f"ws://localhost:{port}")

    # Register student
    await ws.send(json.dumps({
        "type": "register",
        "username": student_name,
        "password": "StudentPass1",
        "role": "student"
    }))
    resp = await recv_json_msg(ws)
    assert resp.get("type") == "auth_ok", f"Student register failed: {resp}"
    await recv_json_msg(ws)  # rooms_list

    # Join room
    await ws.send(json.dumps({
        "type": "join_room",
        "room_code": room_code
    }))
    resp = await recv_json_msg(ws)
    assert resp.get("type") == "room_entered", f"Student join failed: {resp}"
    print(f"[SETUP] Student '{student_name}' joined room: {room_code}")

    return ws, student_name


async def run_test():
    manager = ConnectionManager()

    async def handler(websocket):
        await handle_connection(websocket, manager)

    server = await websockets.serve(handler, "localhost", TEST_PORT)
    print(f"[TEST] Test server started on port {TEST_PORT}")

    passed = 0
    failed = 0

    try:
        room_code, teacher_name = await setup_room(manager, TEST_PORT)

        # ── Test 1: Doubt text too short (<10 chars) ─────────────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            await ws.send(json.dumps({
                "type": "submit_doubt",
                "text": "short",
                "urgency": "clarification"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "error":
                print(f"[PASS] Test 1: Short text rejected — {resp.get('message')}")
                passed += 1
            else:
                print(f"[FAIL] Test 1: Expected error for short text, got {resp}")
                failed += 1
        finally:
            await ws.close()

        # ── Test 2: Doubt text too long (>500 chars) ─────────────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            long_text = "A" * 501
            await ws.send(json.dumps({
                "type": "submit_doubt",
                "text": long_text,
                "urgency": "clarification"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "error":
                print(f"[PASS] Test 2: Long text rejected — {resp.get('message')}")
                passed += 1
            else:
                print(f"[FAIL] Test 2: Expected error for long text, got {resp}")
                failed += 1
        finally:
            await ws.close()

        # ── Test 3: Invalid urgency value ────────────────────────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            await ws.send(json.dumps({
                "type": "submit_doubt",
                "text": "This is a valid length doubt text for testing",
                "urgency": "hacked"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "error":
                print(f"[PASS] Test 3: Invalid urgency rejected — {resp.get('message')}")
                passed += 1
            else:
                print(f"[FAIL] Test 3: Expected error for invalid urgency, got {resp}")
                failed += 1
        finally:
            await ws.close()

        # ── Test 4: Valid doubt submission ────────────────────────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            await ws.send(json.dumps({
                "type": "submit_doubt",
                "text": "This is a perfectly valid doubt with enough characters",
                "urgency": "clarification"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "doubt_submitted":
                print(f"[PASS] Test 4: Valid doubt accepted — id: {resp.get('doubt_id')}")
                passed += 1
            else:
                print(f"[FAIL] Test 4: Expected doubt_submitted, got {resp}")
                failed += 1
        finally:
            await ws.close()

        # ── Test 5: Rate limiting ────────────────────────────────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            rate_limited_count = 0
            errors_seen = []
            # Send 20 rapid messages
            for i in range(20):
                await ws.send(json.dumps({
                    "type": "submit_doubt",
                    "text": f"Rate limit test doubt number {i} with enough chars to pass validation",
                    "urgency": "clarification"
                }))

            # Collect all responses
            for i in range(20):
                try:
                    resp = await asyncio.wait_for(recv_json_msg(ws, timeout=3.0), timeout=3.0)
                    if resp.get("type") == "error" and "rate" in resp.get("message", "").lower():
                        rate_limited_count += 1
                        errors_seen.append(resp.get("message"))
                except asyncio.TimeoutError:
                    break
                except websockets.exceptions.ConnectionClosed:
                    # Server may disconnect after too many violations
                    rate_limited_count += 1
                    break

            if rate_limited_count > 0:
                print(f"[PASS] Test 5: Rate limiting triggered — {rate_limited_count} rate-limited responses")
                passed += 1
            else:
                print(f"[FAIL] Test 5: No rate limiting detected after 20 rapid messages")
                failed += 1
        except websockets.exceptions.ConnectionClosed:
            # Disconnected by rate limiter — that's a pass
            print(f"[PASS] Test 5: Rate limiter disconnected client")
            passed += 1
        finally:
            try:
                await ws.close()
            except Exception:
                pass

        # ── Test 6: Doubt limit (max 10 per student per day) ─────────
        ws, student = await connect_student(TEST_PORT, room_code)
        try:
            limit_hit = False
            for i in range(11):
                await ws.send(json.dumps({
                    "type": "submit_doubt",
                    "text": f"Doubt limit test number {i + 1} with sufficient length for validation",
                    "urgency": "feedback"
                }))
                resp = await recv_json_msg(ws)
                if resp.get("type") == "error" and "limit" in resp.get("message", "").lower():
                    print(f"[PASS] Test 6: Doubt limit hit at attempt {i + 1} — {resp.get('message')}")
                    limit_hit = True
                    passed += 1
                    break
                # Allow small delay to avoid rate limiting interference
                await asyncio.sleep(0.15)

            if not limit_hit:
                print(f"[FAIL] Test 6: No doubt limit error after 11 submissions")
                failed += 1
        finally:
            await ws.close()

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
