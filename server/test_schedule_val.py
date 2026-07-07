import asyncio
import json
import websockets
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connection_manager import ConnectionManager
from chat_server import handle_connection
import schedule as sched

TEST_PORT = 9994

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
    print(f"[TEST] Schedule validation test server started on port {TEST_PORT}")

    rand = random.randint(1000, 9999)
    teacher_user = f"t_sched_{rand}"

    try:
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Register & login teacher
            await ws.send(json.dumps({"type": "register", "username": teacher_user, "password": "Password123", "role": "teacher"}))
            resp1 = await recv_json_msg(ws)
            assert resp1["type"] == "auth_ok", f"Expected auth_ok, got {resp1}"
            await recv_json_msg(ws) # rooms_list
            await ws.send(json.dumps({"type": "create_room", "room_name": "Schedule Room"}))
            resp = await recv_json_msg(ws)
            room_code = resp["room_code"]

            # Test 1: Invalid day number (e.g. 6)
            bad_schedule = {
                "week_start": "2026-07-06",
                "subject": "Math",
                "days": [{"day": 6, "date": "2026-07-12", "start": "09:00", "end": "10:00"}]
            }
            await ws.send(json.dumps({"type": "set_schedule", "schedule": bad_schedule}))
            resp = await recv_json_msg(ws)
            print("[TEST] Bad day response:", resp)
            assert resp["type"] == "error"
            assert "Day number must be between 1 and 5" in resp["message"]
            print("[PASS] Test 1: Invalid day number correctly rejected")

            # Test 2: Invalid date format
            bad_schedule = {
                "week_start": "2026-07-06",
                "subject": "Math",
                "days": [{"day": 1, "date": "07-12-2026", "start": "09:00", "end": "10:00"}]
            }
            await ws.send(json.dumps({"type": "set_schedule", "schedule": bad_schedule}))
            resp = await recv_json_msg(ws)
            print("[TEST] Bad date response:", resp)
            assert resp["type"] == "error"
            assert "Invalid date format" in resp["message"]
            print("[PASS] Test 2: Invalid date format correctly rejected")

            # Test 3: Start time >= End time
            bad_schedule = {
                "week_start": "2026-07-06",
                "subject": "Math",
                "days": [{"day": 1, "date": "2026-07-12", "start": "11:00", "end": "10:00"}]
            }
            await ws.send(json.dumps({"type": "set_schedule", "schedule": bad_schedule}))
            resp = await recv_json_msg(ws)
            print("[TEST] Bad time response:", resp)
            assert resp["type"] == "error"
            assert "must be before end time" in resp["message"]
            print("[PASS] Test 3: Start time >= End time correctly rejected")

            # Test 4: Valid schedule
            good_schedule = {
                "week_start": "2026-07-06",
                "subject": "Math",
                "days": [{"day": 1, "date": "2026-07-06", "start": "09:00", "end": "10:00"}]
            }
            await ws.send(json.dumps({"type": "set_schedule", "schedule": good_schedule}))
            resp = await recv_json_msg(ws)
            print("[TEST] Good schedule response:", resp)
            assert resp["type"] == "schedule_info"
            print("[PASS] Test 4: Valid schedule successfully saved")

        print("[TEST] ALL SCHEDULE VALIDATION TESTS PASSED SUCCESSFULLY!")

    finally:
        server.close()
        await server.wait_closed()
        print("[TEST] Test server closed.")

if __name__ == "__main__":
    asyncio.run(run_test())
