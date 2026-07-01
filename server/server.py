"""
server.py
---------
Entrypoint for DoubtNet — wires all modules together and starts the WebSocket server.
"""

import asyncio
import websockets
import threading
import http.server
import functools
import os

from connection_manager import ConnectionManager
from chat_server import handle_connection
import schedule as sched
import protocol

HOST = "0.0.0.0"
PORT = 8765
HTTP_PORT = 8080

STATE_BROADCAST_INTERVAL = 30


async def state_broadcaster(manager: ConnectionManager):
    """Periodically broadcast current schedule state to all connected clients in their respective rooms."""
    import rooms
    while True:
        await asyncio.sleep(STATE_BROADCAST_INTERVAL)
        try:
            all_rooms = rooms._load()
            for room_code in all_rooms.keys():
                state = sched.get_current_state(room_code)
                encoded = protocol.msg_state_update(state)
                await manager.broadcast_to_room(room_code, encoded)
        except Exception as e:
            print(f"[!] State broadcast error: {e}")


def start_http_server():
    """Serve the client directory over HTTP for easy access."""
    client_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client")
    client_dir = os.path.normpath(client_dir)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=client_dir)
    httpd = http.server.HTTPServer(("0.0.0.0", HTTP_PORT), handler)
    print(f"[+] HTTP server serving client at http://10.136.99.209:{HTTP_PORT}")
    httpd.serve_forever()


async def main():
    manager = ConnectionManager()

    async def handler(websocket):
        await handle_connection(websocket, manager)

    print(f"[+] DoubtNet server starting on ws://10.136.99.209:{PORT}")
    print(f"[*] State broadcasts every {STATE_BROADCAST_INTERVAL}s")

    asyncio.create_task(state_broadcaster(manager))

    async with websockets.serve(handler, HOST, PORT):
        print("[*] Server is running. Waiting for connections...")
        await asyncio.Future()


if __name__ == "__main__":
    # Start HTTP static file server in background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    asyncio.run(main())
