import asyncio
import json
import websockets
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connection_manager import ConnectionManager
from chat_server import handle_connection

TEST_PORT = 9995

async def recv_json_msg(ws):
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("type") in ("presence", "state_update", "doubt_count"):
            continue
        return msg

async def run_test():
    manager = ConnectionManager()
    server = await websockets.serve(lambda ws: handle_connection(ws, manager), "localhost", TEST_PORT)
    print(f"[TEST] Profanity test server started on port {TEST_PORT}")

    rand = random.randint(1000, 9999)
    teacher_user = f"t_prof_{rand}"
    student_user = f"s_prof_{rand}"

    try:
        # Register teacher, create room, enable demo
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({"type": "register", "username": teacher_user, "password": "Password123", "role": "teacher"}))
            resp1 = await recv_json_msg(ws)
            assert resp1["type"] == "auth_ok", f"Expected auth_ok, got {resp1}"
            await recv_json_msg(ws) # rooms_list
            await ws.send(json.dumps({"type": "create_room", "room_name": "Profanity Room"}))
            resp = await recv_json_msg(ws)
            room_code = resp["room_code"]
            await ws.send(json.dumps({"type": "start_demo_mode"}))

        # Connect student
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            await ws.send(json.dumps({"type": "register", "username": student_user, "password": "Password123", "role": "student"}))
            resp2 = await recv_json_msg(ws)
            assert resp2["type"] == "auth_ok", f"Expected auth_ok, got {resp2}"
            await recv_json_msg(ws) # rooms_list
            await ws.send(json.dumps({"type": "join_room", "room_code": room_code}))
            await recv_json_msg(ws)

            # Test 1: Submit doubt with 'assessment' (should be approved)
            await ws.send(json.dumps({"type": "submit_doubt", "text": "Will this topic be in the assessment?", "urgency": "clarification"}))
            resp = await recv_json_msg(ws)
            print("[TEST] Submission 1 ('assessment'):", resp)
            assert resp["type"] == "doubt_submitted"
            assert resp["status"] == "approved"
            print("[PASS] Test 1: 'assessment' was correctly approved (no false positive for 'ass')")

            # Test 2: Submit obfuscated profanity 'f-u-c-k' (should be flagged)
            await ws.send(json.dumps({"type": "submit_doubt", "text": "This is a f-u-c-k test", "urgency": "clarification"}))
            resp = await recv_json_msg(ws)
            print("[TEST] Submission 2 ('f-u-c-k'):", resp)
            assert resp["type"] == "doubt_submitted"
            assert resp["status"] == "flagged"
            print("[PASS] Test 2: 'f-u-c-k' was correctly flagged")

        print("[TEST] ALL PROFANITY TESTS PASSED SUCCESSFULLY!")

    finally:
        server.close()
        await server.wait_closed()
        print("[TEST] Test server closed.")

if __name__ == "__main__":
    asyncio.run(run_test())
