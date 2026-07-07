"""
Self-contained integration test for Authentication.
Starts a local WebSocket server, registers users, and verifies:
- Successful registration + login
- Login with wrong password fails
- Duplicate registration fails
- Short username (<3 chars) fails
- Short password (<6 chars) fails
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

TEST_PORT = 9998


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

    server = await websockets.serve(handler, "localhost", TEST_PORT)
    print(f"[TEST] Test server started on port {TEST_PORT}")

    passed = 0
    failed = 0

    try:
        suffix = random.randint(10000, 99999)
        test_username = f"auth_user_{suffix}"
        test_password = "SecurePass123"

        # ── Test 1: Successful Registration ──────────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "register",
                "username": test_username,
                "password": test_password,
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_ok" and resp.get("username") == test_username:
                print(f"[PASS] Test 1: Registration succeeded for '{test_username}'")
                passed += 1
            else:
                print(f"[FAIL] Test 1: Expected auth_ok, got {resp}")
                failed += 1

            # Consume the rooms_list that follows auth_ok
            resp2 = await recv_json_msg(ws)
            assert resp2.get("type") == "rooms_list", f"Expected rooms_list, got {resp2}"

        # ── Test 2: Login with correct password ──────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "login",
                "username": test_username,
                "password": test_password
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_ok" and resp.get("username") == test_username:
                print(f"[PASS] Test 2: Login succeeded with correct password")
                passed += 1
            else:
                print(f"[FAIL] Test 2: Expected auth_ok, got {resp}")
                failed += 1

            # Consume rooms_list
            resp2 = await recv_json_msg(ws)
            assert resp2.get("type") == "rooms_list", f"Expected rooms_list, got {resp2}"

        # ── Test 3: Login with wrong password ────────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "login",
                "username": test_username,
                "password": "WrongPassword999"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_error" and "Incorrect" in resp.get("message", ""):
                print(f"[PASS] Test 3: Login correctly rejected with wrong password")
                passed += 1
            else:
                print(f"[FAIL] Test 3: Expected auth_error with 'Incorrect', got {resp}")
                failed += 1

        # ── Test 4: Duplicate registration ───────────────────────────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "register",
                "username": test_username,
                "password": "AnotherPass456",
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_error" and "already taken" in resp.get("message", "").lower():
                print(f"[PASS] Test 4: Duplicate registration correctly rejected")
                passed += 1
            else:
                print(f"[FAIL] Test 4: Expected auth_error with 'already taken', got {resp}")
                failed += 1

        # ── Test 5: Registration with short username (<3 chars) ──────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "register",
                "username": "ab",
                "password": "ValidPass123",
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_error" and "3" in resp.get("message", ""):
                print(f"[PASS] Test 5: Short username correctly rejected")
                passed += 1
            else:
                print(f"[FAIL] Test 5: Expected auth_error about username length, got {resp}")
                failed += 1

        # ── Test 6: Registration with short password (<6 chars) ──────
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "register",
                "username": f"valid_user_{suffix}",
                "password": "12345",
                "role": "student"
            }))
            resp = await recv_json_msg(ws)
            if resp.get("type") == "auth_error" and "6" in resp.get("message", ""):
                print(f"[PASS] Test 6: Short password correctly rejected")
                passed += 1
            else:
                print(f"[FAIL] Test 6: Expected auth_error about password length, got {resp}")
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
