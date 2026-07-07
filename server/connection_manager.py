"""
connection_manager.py
---------------------
Tracks connected clients with role and room information. Supports
role-aware and room-aware broadcasting and direct messaging.
"""

import asyncio
from typing import Optional


class ConnectionManager:
    def __init__(self):
        # websocket -> {"username": str, "role": str, "room_code": Optional[str]}
        self._clients: dict = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket, username: str, role: str = "student", room_code: str = None):
        async with self._lock:
            self._clients[websocket] = {"username": username, "role": role, "room_code": room_code}

    async def remove(self, websocket):
        async with self._lock:
            self._clients.pop(websocket, None)

    async def get_username(self, websocket) -> Optional[str]:
        async with self._lock:
            info = self._clients.get(websocket)
            return info["username"] if info else None

    async def get_role(self, websocket) -> Optional[str]:
        async with self._lock:
            info = self._clients.get(websocket)
            return info["role"] if info else None

    async def usernames(self) -> list:
        async with self._lock:
            return [v["username"] for v in self._clients.values()]

    async def usernames_in_room(self, room_code: str) -> list:
        """Get all online usernames in a specific room."""
        async with self._lock:
            return [v["username"] for v in self._clients.values() if v.get("room_code") == room_code]

    async def is_username_online(self, username: str) -> bool:
        async with self._lock:
            return username in [v["username"] for v in self._clients.values()]

    async def kick_username(self, username: str):
        """Forcefully disconnect a user by username (for stale connections)."""
        async with self._lock:
            target_ws = None
            for ws, info in self._clients.items():
                if info["username"] == username:
                    target_ws = ws
                    break
        if target_ws:
            try:
                await target_ws.close()
            except Exception:
                pass
            await self.remove(target_ws)

    async def _send_safe(self, ws, message: str):
        """Helper to send message to a client and return the websocket on error."""
        try:
            await ws.send(message)
            return None
        except Exception:
            return ws

    async def broadcast(self, message: str, exclude=None):
        """Broadcast to ALL connected clients concurrently."""
        async with self._lock:
            targets = [ws for ws in self._clients.keys() if ws is not exclude]
        if not targets:
            return

        results = await asyncio.gather(*(self._send_safe(ws, message) for ws in targets), return_exceptions=True)
        dead = [ws for ws in results if isinstance(ws, websocket.__class__ if hasattr(websocket, "__class__") else object) or ws is not None]
        # In case exception objects or websockets are returned, filter for actual websockets
        dead_ws = [ws for ws in dead if ws in targets]
        for ws in dead_ws:
            await self.remove(ws)

    async def broadcast_to_room(self, room_code: str, message: str, exclude=None):
        """Broadcast to all clients in a specific room concurrently."""
        async with self._lock:
            targets = [
                ws for ws, info in self._clients.items()
                if info.get("room_code") == room_code and ws is not exclude
            ]
        if not targets:
            return

        results = await asyncio.gather(*(self._send_safe(ws, message) for ws in targets), return_exceptions=True)
        dead_ws = [ws for ws in results if ws in targets]
        for ws in dead_ws:
            await self.remove(ws)

    async def broadcast_to_role(self, message: str, role: str, exclude=None):
        """Send message to all connected clients of a given role concurrently."""
        async with self._lock:
            targets = [
                ws for ws, info in self._clients.items()
                if info["role"] == role and ws is not exclude
            ]
        if not targets:
            return

        results = await asyncio.gather(*(self._send_safe(ws, message) for ws in targets), return_exceptions=True)
        dead_ws = [ws for ws in results if ws in targets]
        for ws in dead_ws:
            await self.remove(ws)

    async def broadcast_to_role_in_room(self, room_code: str, role: str, message: str, exclude=None):
        """Send message to all clients of a given role in a specific room concurrently."""
        async with self._lock:
            targets = [
                ws for ws, info in self._clients.items()
                if info["role"] == role and info.get("room_code") == room_code and ws is not exclude
            ]
        if not targets:
            return

        results = await asyncio.gather(*(self._send_safe(ws, message) for ws in targets), return_exceptions=True)
        dead_ws = [ws for ws in results if ws in targets]
        for ws in dead_ws:
            await self.remove(ws)

    async def send_to_user(self, username: str, message: str):
        """Send a message directly to a specific user by username."""
        async with self._lock:
            target_ws = None
            for ws, info in self._clients.items():
                if info["username"] == username:
                    target_ws = ws
                    break

        if target_ws:
            try:
                await target_ws.send(message)
            except Exception:
                await self.remove(target_ws)

    async def send_to(self, websocket, message: str):
        try:
            await websocket.send(message)
        except Exception:
            await self.remove(websocket)
