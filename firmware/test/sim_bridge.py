#!/usr/bin/env python3
"""Serve the real web UI against the simulated arm (no ESP32 needed).

    make -C firmware/test sim_server CJSON=/path/to/cJSON
    pip install aiohttp
    python3 firmware/test/sim_bridge.py       # then open http://localhost:8080

Runs sim_server (the firmware's robot core + JSON API on a physics sim) and
exposes the same endpoints as the ESP32: /, /ws, /api/state, /api/cmd,
/api/config, /api/wifi, /api/reboot, /api/ota (stub).
Like the ESP32, /ws carries binary wire::Live frames plus {"t":"info"} text.
"""
import asyncio
import itertools
import json
import os
import sys

from aiohttp import web, WSMsgType

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class Bridge:
    def __init__(self):
        self.proc = None
        self.state = None   # full JSON, for /api/state
        self.info = None    # latest {"t":"info"} JSON, sent to each new /ws client
        self.sockets = set()
        self.waiters = {}
        self.ids = itertools.count(100000)

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            os.path.join(HERE, "sim_server"), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            limit=1 << 20)
        asyncio.create_task(self.reader())

    async def reader(self):
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                print("sim_server exited", file=sys.stderr)
                return
            kind, _, payload = line.decode().partition(" ")
            if kind == "S":
                self.state = payload.strip()
            elif kind in ("L", "I"):  # same /ws traffic as the ESP32: binary live frame, info text
                if kind == "I":
                    self.info = payload.strip()
                data = bytes.fromhex(payload.strip()) if kind == "L" else self.info
                for ws in list(self.sockets):
                    try:
                        await (ws.send_bytes(data) if kind == "L" else ws.send_str(data))
                    except Exception:
                        self.sockets.discard(ws)
            elif kind == "R":
                msg = json.loads(payload)
                fut = self.waiters.pop(msg.get("id"), None)
                if fut and not fut.done():
                    fut.set_result(msg)

    async def call(self, msg):
        mid = next(self.ids)
        fut = asyncio.get_running_loop().create_future()
        self.waiters[mid] = fut
        self.proc.stdin.write((json.dumps(dict(msg, id=mid)) + "\n").encode())
        await self.proc.stdin.drain()
        return await asyncio.wait_for(fut, 3)


bridge = Bridge()


async def index(_):
    return web.FileResponse(INDEX)


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    if bridge.info:
        await ws.send_str(bridge.info)
    bridge.sockets.add(ws)
    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        m = json.loads(msg.data)
        client_id = m.pop("id", None)
        m.pop("key", None)
        reply = await bridge.call(m)
        reply["id"] = client_id
        reply["t"] = "reply"
        await ws.send_str(json.dumps(reply))
    bridge.sockets.discard(ws)
    return ws


async def api_state(_):
    return web.Response(text=bridge.state or "{}", content_type="application/json")


async def api_cmd(request):
    reply = await bridge.call(await request.json())
    reply.pop("id", None)
    return web.json_response(reply)


async def api_config(request):
    if request.method == "POST":
        r = await bridge.call({"cmd": "__set_config", "config": await request.json()})
    else:
        r = await bridge.call({"cmd": "__get_config"})
    return web.json_response(r["config"])


async def api_wifi(request):
    if request.method == "POST":
        return web.json_response({"ok": True, "note": "simulator: not saved"})
    return web.json_response({"ssid": "", "hostname": "scorbot", "has_password": False, "has_api_key": False})


async def api_ota(request):  # firmware updates: nothing to update in the simulator
    status = {"version": "simulator", "variant": "sim", "driver": "simulated", "slot": "ota_0", "ota_layout": True,
              "busy": False, "progress": -1, "state": "idle", "latest": "", "message": ""}
    if request.method == "POST":
        status["message"] = "simulator: no firmware updates"
    return web.json_response(status)


async def not_found(_):  # like the ESP32's captive-portal handler
    raise web.HTTPFound("/")


async def api_sim(request):  # test hook (E-stop etc.)
    return web.json_response(await bridge.call(dict(await request.json(), cmd="__sim")))


async def main(port):
    await bridge.start()
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/ws", ws_handler), web.get("/api/state", api_state),
                    web.post("/api/cmd", api_cmd), web.get("/api/config", api_config),
                    web.post("/api/config", api_config), web.get("/api/wifi", api_wifi),
                    web.post("/api/wifi", api_wifi), web.post("/api/reboot", api_wifi),
                    web.post("/api/sim", api_sim), web.get("/api/ota", api_ota),
                    web.post("/api/ota/check", api_ota), web.post("/api/ota/install", api_ota),
                    web.post("/api/ota/upload", api_ota), web.get("/favicon.ico", not_found)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    print(f"simulator UI on http://127.0.0.1:{port}", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8080))
