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
import sys
import ssl
import argparse

from connection_manager import ConnectionManager
from chat_server import handle_connection
import schedule as sched
import protocol

# CLI args parsed at bottom; these are defaults
HOST = "0.0.0.0"
PORT = 8765
HTTP_PORT = 8080
SSL_CERT = None
SSL_KEY = None

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


class _NoListingHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler that disables directory listing (returns 404)."""

    def list_directory(self, path):
        self.send_error(404, "Not Found")
        return None

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Suppress noisy per-request logs
        pass


def start_http_server(bind_ip):
    """Serve the client directory over HTTP for easy access."""
    client_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client")
    client_dir = os.path.normpath(client_dir)
    
    display_ip = bind_ip if bind_ip != '0.0.0.0' else '10.136.99.209'
    config_path = os.path.join(client_dir, "js", "config.js")
    with open(config_path, "w") as f:
        f.write(f'window.SERVER_IP = "{display_ip}";\n')

    handler = functools.partial(_NoListingHandler, directory=client_dir)
    httpd = http.server.HTTPServer((bind_ip, HTTP_PORT), handler)
    print(f"[+] HTTP server serving client at http://{display_ip}:{HTTP_PORT}")
    httpd.serve_forever()


async def main():
    manager = ConnectionManager()

    async def handler(websocket):
        await handle_connection(websocket, manager)

    print(f"[+] DoubtNet server starting on ws://{HOST if HOST != '0.0.0.0' else '10.136.99.209'}:{PORT}")
    print(f"[*] State broadcasts every {STATE_BROADCAST_INTERVAL}s")

    asyncio.create_task(state_broadcaster(manager))

    ssl_context = None
    if SSL_CERT and SSL_KEY:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(SSL_CERT, SSL_KEY)
        print(f"[+] TLS enabled — serving wss://")

    async with websockets.serve(
        handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=None,
        ssl=ssl_context,
    ):
        proto = "wss" if ssl_context else "ws"
        print(f"[*] Server is running on {proto}://{HOST}:{PORT}. Waiting for connections...")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DoubtNet Server")
    parser.add_argument("host", nargs="?", default="0.0.0.0", help="Bind IP address")
    parser.add_argument("--ssl-cert", default=None, help="Path to SSL certificate file for wss://")
    parser.add_argument("--ssl-key", default=None, help="Path to SSL private key file for wss://")
    args = parser.parse_args()

    HOST = args.host
    SSL_CERT = args.ssl_cert
    SSL_KEY = args.ssl_key

    # Start HTTP static file server in background thread
    http_thread = threading.Thread(target=start_http_server, args=(HOST,), daemon=True)
    http_thread.start()

    asyncio.run(main())
