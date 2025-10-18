# app/wsmanager.py
import asyncio
from fastapi import WebSocket
from typing import Set
from app.pivpn import get_connected_clients, get_total_clients
from app.database import insert_traffic_sample
import time

POLL_INTERVAL = 5  # seconds

class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._task = None
        self._last_totals = {}  # map client -> (bytes_in, bytes_out)

    async def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self):
        while True:
            clients = get_connected_clients()
            total = get_total_clients()
            payload = {"total": total, "connected": len(clients), "list": clients, "ts": int(time.time())}
            print(payload)
            # compute deltas and insert into DB
            for c in clients:
                name = c["name"]
                # parse bytes strings like "12.3 MB" or "0"
                def to_bytes(s):
                    try:
                        # normalize: e.g., "12.3 KB" or "123"
                        s = s.strip()
                        if s == "-" or s == "":
                            return 0
                        parts = s.split()
                        if len(parts) == 1:
                            return int(parts[0])
                        val = float(parts[0])
                        unit = parts[1].upper()
                        if unit.startswith("KB"):
                            return int(val * 1024)
                        if unit.startswith("MB"):
                            return int(val * 1024 * 1024)
                        if unit.startswith("GB"):
                            return int(val * 1024 * 1024 * 1024)
                        return int(val)
                    except Exception:
                        return 0
                rx = to_bytes(c.get("bytes_received","0"))
                tx = to_bytes(c.get("bytes_sent","0"))
                prev = self._last_totals.get(name, (rx, tx))
                # delta = current - prev (if negative, reset)
                drx = max(0, rx - prev[0])
                dtx = max(0, tx - prev[1])
                # log sample
                insert_traffic_sample(name, drx, dtx)
                self._last_totals[name] = (rx, tx)

            # broadcast
            await self.broadcast(payload)
            await asyncio.sleep(POLL_INTERVAL)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, msg: dict):
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_json(msg)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

wsmanager = WSManager()
