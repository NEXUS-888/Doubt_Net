"""Test auth + doubt flow for DoubtNet."""
import asyncio
import websockets
import json


async def test():
    async with websockets.connect("ws://128.0.88.70:8765") as ws:
        # Login with test_student2 (created earlier)
        await ws.send(json.dumps({"type": "login", "username": "test_student2",
                                  "password": "test123"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        t = resp.get("type")
        if t == "auth_ok":
            print(f"AUTH OK - role: {resp.get('role')}, phase: {resp.get('state', {}).get('phase')}")
        elif t == "auth_error":
            # Try registering
            print(f"Login failed: {resp.get('message')}")
            await ws.send(json.dumps({"type": "register", "username": "test_student3",
                                      "password": "test123", "role": "student", "invite_code": ""}))
            resp2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print(f"Register: {resp2.get('type')} - {resp2.get('role', resp2.get('message', ''))}")
        else:
            print(f"Unexpected: {resp}")

asyncio.run(test())
