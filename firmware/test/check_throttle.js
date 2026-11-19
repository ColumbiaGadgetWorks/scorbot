// Checks the outgoing-command throttle in web/index.html (Conn.send) against a
// fake WebSocket.   node firmware/test/check_throttle.js
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const m = html.match(/(const SEND_GAP_MS = [\s\S]*?\nconst Conn = \{[\s\S]*?\n\};)/);
if (!m) { console.log("FAIL: Conn block not found"); process.exit(1); }
let demo = null; const toast = () => {};
const sent = [];
const Conn = eval(m[1] + "\nConn");
Conn.ws = { readyState: 1, send: s => sent.push({ t: performance.now(), m: JSON.parse(s) }) };
Conn.key = () => "";
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
const check = (c, what) => { if (!c) { fails++; console.log("  FAIL", what); } };

(async () => {
  // 1. A burst of jog messages (every 5 ms for 300 ms) is thinned to about one per 50 ms.
  const t0 = performance.now();
  for (let i = 0; i < 60; i++) { Conn.send({ cmd: "jog", joint: 0, speed: 0.5 + i / 1000 }); await sleep(5); }
  await sleep(80);
  const jogs = sent.filter(s => s.m.cmd === "jog");
  check(jogs.length >= 5 && jogs.length <= 9, `burst of 60 sent ${jogs.length} (want ~7)`);
  for (let i = 1; i < jogs.length; i++) check(jogs[i].t - jogs[i - 1].t >= 45, `gap ${(jogs[i].t - jogs[i - 1].t).toFixed(1)} ms`);
  check(Math.abs(jogs[jogs.length - 1].m.speed - 0.559) < 1e-9, "the newest value is the one that arrives last");

  // 2. Releasing (speed 0) is sent at once, even right after a jog, and drops the queued jog.
  sent.length = 0;
  Conn.send({ cmd: "jog", joint: 1, speed: 0.4 });
  await sleep(10);
  Conn.send({ cmd: "jog", joint: 1, speed: 0.4 });  // queued (inside 50 ms)
  const tStop = performance.now();
  Conn.send({ cmd: "jog", joint: 1, speed: 0 });
  check(sent.length === 2 && sent[1].m.speed === 0 && sent[1].t - tStop < 5, "release sent immediately");
  await sleep(80);
  check(sent.length === 2, `queued jog fired after release (${sent.length} sends)`);

  // 3. stop cancels queued motion on every joint; other joints are throttled separately.
  sent.length = 0;
  Conn.send({ cmd: "jog", joint: 2, speed: 0.3 });
  Conn.send({ cmd: "jog", joint: 3, speed: 0.3 });
  check(sent.length === 2, "different joints are not throttled against each other");
  Conn.send({ cmd: "jog", joint: 2, speed: 0.3 });
  Conn.send({ cmd: "move", pos: [10, null, null, null, null, null], speed: 0.5 });
  Conn.send({ cmd: "move", pos: [20, null, null, null, null, null], speed: 0.5 });  // queued behind the first move
  Conn.send({ cmd: "stop" });
  await sleep(80);
  const after = sent.slice(sent.findIndex(s => s.m.cmd === "stop") + 1);
  check(after.length === 0, `motion sent after stop: ${JSON.stringify(after.map(s => s.m))}`);

  // 4. A queued send that a newer one replaces settles at once (ok, superseded),
  //    so callers never hang. (Sends that went out wait for the reply as before.)
  Conn.send({ cmd: "jog", joint: 4, speed: 0.2 });                // goes out
  const queued = Conn.send({ cmd: "jog", joint: 4, speed: 0.2 });  // queued...
  Conn.send({ cmd: "jog", joint: 4, speed: 0.3 });                // ...and replaced
  const r = await Promise.race([queued, sleep(20).then(() => "hung")]);
  check(r !== "hung" && r.ok && r.superseded, `superseded send settles: ${JSON.stringify(r)}`);

  // 5. Moves of different joints inside one gap are merged, not dropped.
  await sleep(80);
  sent.length = 0;
  Conn.send({ cmd: "move", pos: [5, null, null, null, null, null], speed: 0.5 });   // goes out
  Conn.send({ cmd: "move", pos: [null, 7, null, null, null, null], speed: 0.5 });   // queued
  Conn.send({ cmd: "move", pos: [null, null, 9, null, null, null], speed: 0.5 });   // merged into it
  await sleep(80);
  const mv = sent.filter(s => s.m.cmd === "move").map(s => s.m.pos);
  check(mv.length === 2 && JSON.stringify(mv[1]) === JSON.stringify([null, 7, 9, null, null, null]),
        `queued moves merged: ${JSON.stringify(mv)}`);

  console.log(fails ? `${fails} throttle checks failed` : "throttle checks OK");
  process.exit(fails ? 1 : 0);
})();
