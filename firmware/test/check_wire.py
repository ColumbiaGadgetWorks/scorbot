#!/usr/bin/env python3
"""Check the binary /ws live frame (wire::Live, main/api.h) against the JSON state.

    make -C firmware/test sim_server CJSON=/path/to/cJSON
    python3 firmware/test/check_wire.py

Runs sim_server, enables and jogs the arm, then decodes each binary frame two
ways and compares every field with the JSON state from the same tick:
  1. with Python's struct module (checks the C++ layout), and
  2. with decodeLive() taken from web/index.html, run under Node (checks the page).
"""
import json
import math
import os
import re
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE_FMT = "<HBBBbBBBBBbf6f6f6f6f6i6i6iI64s32s"  # keep in step with wire::Live
MODES = ["disabled", "idle", "moving", "jog", "homing", "calibrating", "test", "fault", "estop"]
fails = 0


def check(cond, what):
    global fails
    if not cond:
        fails += 1
        print("  FAIL", what)


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def bits(v, n):
    return [bool(v >> i & 1) for i in range(n)]


def decode_py(raw):
    f = struct.unpack(LIVE_FMT, raw)
    it = iter(f)
    magic, ver, mode, flags, busy, homed, cal, sw, sw_on, sw_off, rssi, vm = (next(it) for _ in range(12))
    arr = lambda: [next(it) for _ in range(6)]
    pos, tgt, duty, cur, counts, emin, emax = (arr() for _ in range(7))
    uptime, fault, phase = next(it), next(it), next(it)
    cstr = lambda b: b.split(b"\0", 1)[0].decode()
    return dict(magic=magic, version=ver, mode=MODES[mode], enabled=bool(flags & 1), vm_ok=bool(flags & 2),
                drv_fault=bool(flags & 4), busy=busy, homed=bits(homed, 6), calibrated=bits(cal, 6),
                sw=bits(sw, 5), sw_on=bits(sw_on, 5), sw_off=bits(sw_off, 5), rssi=rssi,
                vm=None if math.isnan(vm) else vm, pos=pos, tgt=tgt, duty=duty,
                cur=[None if math.isnan(c) else c for c in cur], counts=counts, emin=emin, emax=emax,
                uptime=uptime, fault=cstr(fault), phase=cstr(phase))


def compare(d, s, who):
    for k in ("mode", "enabled", "vm_ok", "drv_fault", "busy", "homed", "calibrated", "sw", "sw_on", "sw_off",
              "counts", "emin", "emax", "fault", "phase"):
        check(d[k] == s[k], f"{who}: {k} {d[k]!r} != {s[k]!r}")
    check(close(d["vm"], s["vm"], 0.01), f"{who}: vm")
    for k, tol in (("pos", 0.01), ("tgt", 0.01), ("duty", 0.001), ("cur", 0.001)):
        check(all(close(a, b, tol) for a, b in zip(d[k], s[k])), f"{who}: {k} {d[k]} != {s[k]}")
    check(d["hw_rssi"] == s["hw"]["rssi"] and d["hw_uptime"] == s["hw"]["uptime"], f"{who}: rssi/uptime")


def js_decoder():
    html = open(os.path.join(HERE, "..", "web", "index.html")).read()
    m = re.search(r"(const MODES = .*?)\nlet staleWarned", html, re.S)
    assert m, "decodeLive() block not found in index.html"
    return m.group(1)


def main():
    proc = subprocess.Popen([os.path.join(HERE, "sim_server")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)
    send = lambda m: (proc.stdin.write(json.dumps(m) + "\n"), proc.stdin.flush())
    send({"cmd": "enable", "id": 1})
    pairs, state, t0 = [], None, time.time()
    while len(pairs) < 40 and time.time() - t0 < 10:
        kind, _, payload = proc.stdout.readline().partition(" ")
        if kind == "S":
            state = json.loads(payload)
            if len(pairs) % 5 == 0:
                send({"cmd": "jog", "joint": len(pairs) // 5 % 6, "speed": 0.5, "id": 2})
        elif kind == "L" and state is not None:
            pairs.append((bytes.fromhex(payload.strip()), state))
    proc.kill()
    check(len(pairs) >= 40, f"only {len(pairs)} frames")
    check(any(s["mode"] == "jog" for _, s in pairs), "arm never jogged: weak test")

    size = struct.calcsize(LIVE_FMT)
    for raw, s in pairs:
        check(len(raw) == size == 284, f"frame is {len(raw)} bytes, struct {size}")
        d = decode_py(raw)
        check(d["magic"] == 0x5342 and d["version"] == 1, "magic/version")
        d["hw_rssi"], d["hw_uptime"] = d["rssi"], d["uptime"]
        compare(d, s, "python")

    # The page's own decoder, on the same frames.
    script = js_decoder() + """
const frames = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = frames.map(h => { const b = Buffer.from(h, 'hex'); const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.length);
  const s = decodeLive(ab); const a = x => Array.from(x, v => Number.isNaN(v) ? null : v);
  return Object.assign({}, s, {pos:a(s.pos), tgt:a(s.tgt), duty:a(s.duty), cur:a(s.cur), counts:a(s.counts),
    emin:a(s.emin), emax:a(s.emax), hw_rssi:s.hw.rssi, hw_uptime:s.hw.uptime}); });
process.stdout.write(JSON.stringify(out));
"""
    js = subprocess.run(["node", "-e", "global.TextDecoder=require('util').TextDecoder;" + script],
                        input=json.dumps([r.hex() for r, _ in pairs]), capture_output=True, text=True)
    check(js.returncode == 0, "node: " + js.stderr.strip()[-300:])
    if js.returncode == 0:
        for d, (_, s) in zip(json.loads(js.stdout), pairs):
            compare(d, s, "page")
    check(decode_js_rejects_bad(), "page decoder should reject a wrong version")

    print(f"{len(pairs)} frames checked (python + page decoder): {'OK' if not fails else f'{fails} failures'}")
    return 1 if fails else 0


def decode_js_rejects_bad():
    bad = bytearray(284)
    struct.pack_into("<HB", bad, 0, 0x5342, 99)
    r = subprocess.run(["node", "-e", js_decoder() + "\nconst b=Buffer.from(process.argv[1],'hex');"
                        "process.stdout.write(String(decodeLive(b.buffer.slice(b.byteOffset,b.byteOffset+b.length))))",
                        bad.hex()], capture_output=True, text=True)
    return r.stdout == "null"


if __name__ == "__main__":
    sys.exit(main())
