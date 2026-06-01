"""
websocket_hub.py — Distribuye mensajes JSON a todos los browsers conectados
"""
import asyncio, json, logging
from fastapi import WebSocket

log = logging.getLogger("ws_hub")

class WebSocketHub:
    def __init__(self):
        self._clients: list[WebSocket] = []

    def add(self, ws: WebSocket):
        self._clients.append(ws)
        log.info(f"Cliente WS conectado. Total: {len(self._clients)}")

    def remove(self, ws: WebSocket):
        self._clients.discard(ws) if hasattr(self._clients,'discard') else None
        try: self._clients.remove(ws)
        except ValueError: pass

    async def broadcast(self, msg: dict):
        text = json.dumps(msg)
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)
