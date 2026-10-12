import json
from collections import defaultdict
from fastapi import WebSocket

_connections: dict[str, set[WebSocket]] = defaultdict(set)

async def connect(request_id: str, websocket: WebSocket):
    await websocket.accept()
    _connections[request_id].add(websocket)

def disconnect(request_id: str, websocket: WebSocket):
    _connections[request_id].discard(websocket)
    if not _connections[request_id]:
        _connections.pop(request_id, None)

async def broadcast(request_id: str, message: dict):
    dead = []
    for ws in list(_connections.get(request_id, set())):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.append(ws)
    for ws in dead:
        disconnect(request_id, ws)
