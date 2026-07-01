"""Quick connectivity test for DoubtNet server."""
import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect("ws://localhost:8765") as ws:
            # Try logging in
            await ws.send(json.dumps({"type": "login", "username": "Student1", "password": "123456"}))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print(f"Response type: {resp.get('type')}")
            if resp.get("type") == "auth_ok":
                print(f"SUCCESS: Logged in as {resp.get('username')} ({resp.get('role')})")
            elif resp.get("type") == "auth_error":
                print(f"Auth response: {resp.get('message')}")
            else:
                print(f"Response: {resp}")
            print("\nWebSocket connection is WORKING!")
    except Exception as e:
        print(f"Connection error: {e}")

asyncio.run(test())
