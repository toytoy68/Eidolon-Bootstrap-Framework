/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : session.test.js
 * Description : Session connectée sur transport injecté : refus, pannes, réponses obsolètes, reset (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run from eidolon-core/: node --test "desktop/connected/tests/*.test.js"
// These are FIXTURE tests (scripted transport). server.test.js uses the real Python server.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../src/session.js");

const TOKEN = "a".repeat(43);
const STORE = "s-" + "1".repeat(32);
const OTHER_STORE = "s-" + "2".repeat(32);
const HEX = "f".repeat(64);
const id = (n) => "m-" + String(n).padStart(32, "0");

function mission(n, extra) {
  return Object.assign({ id: id(n), revision: 1, status: "NEW", phase: "RECALL", cancel_requested: false,
    progress: { completed: 0, total: 1 }, objective_kind: null, outcome_status: "CLARIFICATION", action_view: null }, extra || {});
}
function health(store) {
  return { protocol: C.PROTOCOL, mode: "read_only", store_id: store || STORE, authorizes_execution: false };
}
function page(ids, opts) {
  opts = opts || {};
  const store = opts.store || STORE;
  const generation = { sequence: 50, event_count: 40, mission_count: opts.total || ids.length, anchor_sha256: HEX };
  const items = ids.map((n) => ({ as_of_sequence: 10, mission: mission(n) }));
  const more = Boolean(opts.more);
  return { protocol: "eidolon-mission-list/1", snapshot_only: true, authorizes_execution: false, store_id: store,
    status: "PAGE", observed_at: "2026-10-06T17:00:00+00:00", generation, items, has_more: more,
    next_cursor: more ? { version: 1, store_id: store, generation, after_id: id(ids[ids.length - 1]) } : null };
}
function resetPage(reason) {
  const p = page([]);
  return Object.assign(p, { status: "RESET_REQUIRED", reason: reason || "STATE_CHANGED", items: [], has_more: false, next_cursor: null });
}
function cursor(n, seq, count, store) {
  return { version: 1, store_id: store || STORE, mission_id: id(n), sequence: seq, event_count: count, anchor_sha256: HEX };
}
function sync(n, status, opts) {
  opts = opts || {};
  const seq = opts.seq || 10;
  const env = { protocol: "eidolon-client-sync/1", store_id: opts.store || STORE, mission_id: id(n), status,
    snapshot: { as_of_sequence: opts.asOf || seq, event_count: opts.count || 3, observed_at: "2026-10-06T17:00:00+00:00",
      mission: mission(n, opts.mission) },
    events: opts.events || [], cursor: cursor(n, seq, opts.count || 3, opts.store), has_more: Boolean(opts.more),
    snapshot_only: true, authorizes_execution: false };
  if (status === "RESET_REQUIRED") env.reason = opts.reason || "ANCHOR_CHANGED";
  return env;
}
const err = (status, code) => ({ status, json: { protocol: C.PROTOCOL, error: code, authorizes_execution: false } });
const ok = (json) => ({ status: 200, json });

// Scripted transport: each route answers from a queue or a function; records every call.
function scripted(routes) {
  const calls = [];
  const transport = async (method, path, body, token) => {
    calls.push({ method, path, body: body === undefined ? undefined : JSON.parse(JSON.stringify(body)), token });
    const key = method + " " + path;
    const handler = routes[key];
    if (!handler) throw new Error("unexpected " + key);
    const answer = typeof handler === "function" ? handler(body, token) : handler.shift();
    if (answer instanceof Error) throw answer;
    return answer instanceof Promise ? answer : answer;
  };
  return { transport, calls };
}
const session = (t) => C.createSession({ transport: t.transport, now: () => "2026-10-06T17:00:01Z" });

test("token format is checked locally; nothing is sent for a malformed token", async () => {
  const t = scripted({});
  const s = session(t);
  assert.equal(await s.connect("court"), false);
  assert.equal(s.state().problem.code, "TOKEN_FORMAT");
  assert.equal(t.calls.length, 0);
});

test("connect reads health, lists, then a selection asks one snapshot; the token is only in the header argument", async () => {
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1, 2]))],
    ["GET /v1/missions/" + id(2)]: [ok(sync(2, "SNAPSHOT"))] });
  const s = session(t);
  assert.equal(await s.connect(TOKEN), true);
  const st = s.state();
  assert.equal(st.phase, "connected");
  assert.equal(st.list.items.length, 2);
  assert.equal(st.list.complete, true);
  await s.selectMission(id(2));
  assert.equal(s.state().list.selection.sync.view.mission.id, id(2));
  assert.deepEqual(t.calls.map((c) => c.method + " " + c.path), ["GET /v1/health", "POST /v1/missions", "GET /v1/missions/" + id(2)]);
  assert.ok(t.calls.every((c) => c.token === TOKEN));
  assert.ok(!JSON.stringify(s.state()).includes(TOKEN), "token never in the exposed state");
  assert.deepEqual(t.calls[1].body, { limit: 100 });
});

test("pagination sends next_cursor unchanged and stops at the end; never more than three pages", async () => {
  const first = page([1, 2], { more: true, total: 4 });
  const t = scripted({ "GET /v1/health": [ok(health())],
    "POST /v1/missions": [ok(first), ok(page([3, 4], { total: 4 }))] });
  const s = session(t);
  await s.connect(TOKEN);
  assert.equal(s.state().list.items.length, 4);
  assert.deepEqual(t.calls[2].body.cursor, first.next_cursor);
  // A server that never ends: has_more forever is cut by MAX_LIST_PAGES and the count check.
  let n = 0;
  const endless = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": () => { n += 2; return ok(page([n - 1, n], { more: true, total: 1000 })); } });
  const e = session(endless);
  await e.connect(TOKEN);
  assert.equal(endless.calls.filter((c) => c.path === "/v1/missions").length, 3);
  assert.equal(e.state().list.complete, false);
});

test("list RESET_REQUIRED keeps the old inventory marked stale; an explicit relist starts without cursor", async () => {
  const t = scripted({ "GET /v1/health": [ok(health())],
    "POST /v1/missions": [ok(page([1, 2], { more: true, total: 3 })), ok(resetPage()), ok(page([1, 2, 3]))] });
  const s = session(t);
  await s.connect(TOKEN);
  let st = s.state();
  assert.equal(st.list.stale.reason, "STATE_CHANGED");
  assert.equal(C.shownItems(st.list).length, 2);
  await s.relist();
  st = s.state();
  assert.equal(st.list.items.length, 3);
  assert.equal(st.list.stale, null);
  assert.deepEqual(t.calls[3].body, { limit: 100 });
});

test("401 forgets the token, stops, keeps the last data marked stale and drops answers still in flight", async () => {
  let release;
  const slow = new Promise((r) => { release = r; });
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1])), err(401, "UNAUTHORIZED")],
    ["GET /v1/missions/" + id(1)]: [slow] });
  const s = session(t);
  await s.connect(TOKEN);
  const late = s.selectMission(id(1));      // still waiting for its snapshot
  await s.relist();                         // meanwhile the server refuses the token
  let st = s.state();
  assert.equal(st.phase, "unauthorized");
  assert.equal(s.hasToken(), false);
  assert.equal(C.shownItems(st.list).length, 1, "last inventory still shown");
  release(ok(sync(1, "SNAPSHOT")));
  await late;
  st = s.state();
  assert.equal(st.list.selection.sync.view, null, "an answer from before the 401 is never applied");
  assert.equal(st.stats.staleConnection, 1);
  assert.equal(await s.refreshSelection(), false, "nothing is asked without token");
  assert.equal(t.calls.length, 4);
});

test("403 (Host/Origin) and 503 stop requests and keep the last state; 400 is a Core error, not a capture", async () => {
  const t = scripted({ "GET /v1/health": [err(403, "ORIGIN_REFUSED")] });
  const s = session(t);
  assert.equal(await s.connect(TOKEN), false);
  assert.equal(s.state().phase, "refused");
  assert.equal(s.state().problem.code, "ORIGIN_REFUSED");

  const u = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1])), err(503, "STATE_UNAVAILABLE")] });
  const s2 = session(u);
  await s2.connect(TOKEN);
  await s2.relist();
  assert.equal(s2.state().phase, "unavailable");
  assert.equal(C.shownItems(s2.state().list).length, 1);

  const b = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1]))],
    ["GET /v1/missions/" + id(1)]: [ok(sync(1, "SNAPSHOT"))],
    ["POST /v1/missions/" + id(1) + "/poll"]: [err(400, "INVALID_CURSOR")] });
  const s3 = session(b);
  await s3.connect(TOKEN);
  await s3.selectMission(id(1));
  await s3.refreshSelection();
  const sel = s3.state().list.selection.sync;
  assert.equal(sel.lastError, "INVALID_CURSOR");
  assert.equal(sel.view.mission.id, id(1), "the previous capture stays, nothing invented");
  assert.equal(s3.state().phase, "connected");
});

test("network failure: offline, data kept and dated; reconnect to the same store resumes", async () => {
  const t = scripted({ "GET /v1/health": [ok(health()), ok(health())],
    "POST /v1/missions": [ok(page([1])), new TypeError("Failed to fetch"), ok(page([1, 2]))] });
  const s = session(t);
  await s.connect(TOKEN);
  await s.relist();
  let st = s.state();
  assert.equal(st.phase, "offline");
  assert.equal(st.problem.code, "NETWORK_UNREACHABLE");
  assert.equal(C.shownItems(st.list).length, 1);
  assert.equal(st.list.connection, "offline");
  assert.equal(s.hasToken(), true, "a network failure does not forget the token");
  await s.connect(TOKEN);
  st = s.state();
  assert.equal(st.phase, "connected");
  assert.equal(st.list.items.length, 2);
  assert.equal(st.notice, null);
});

test("reconnection to another store wipes the previous display: no mixed identities", async () => {
  const t = scripted({ "GET /v1/health": [ok(health()), ok(health(OTHER_STORE))],
    "POST /v1/missions": [ok(page([1])), ok(page([7], { store: OTHER_STORE }))],
    ["GET /v1/missions/" + id(1)]: [ok(sync(1, "SNAPSHOT"))] });
  const s = session(t);
  await s.connect(TOKEN);
  await s.selectMission(id(1));
  await s.connect(TOKEN);
  const st = s.state();
  assert.equal(st.storeId, OTHER_STORE);
  assert.match(st.notice, /Autre base/);
  assert.equal(st.list.selection, null, "the old selection is gone");
  assert.deepEqual(st.list.items.map((i) => i.mission.id), [id(7)]);
  assert.equal(st.list.previous, null, "the old inventory is not kept as stale either");
});

test("a list answering for another store than health is refused and nothing is shown", async () => {
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1], { store: OTHER_STORE }))] });
  const s = session(t);
  await s.connect(TOKEN);
  const st = s.state();
  assert.equal(st.phase, "refused");
  assert.equal(st.problem.code, "STORE_IDENTITY_CHANGED");
  assert.equal(C.shownItems(st.list).length, 0);
});

test("an answer for a previous selection never replaces the current one", async () => {
  let release;
  const slow = new Promise((r) => { release = r; });
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1, 2]))],
    ["GET /v1/missions/" + id(1)]: [slow], ["GET /v1/missions/" + id(2)]: [ok(sync(2, "SNAPSHOT"))] });
  const s = session(t);
  await s.connect(TOKEN);
  const first = s.selectMission(id(1));
  await s.selectMission(id(2));
  release(ok(sync(1, "SNAPSHOT")));
  await first;
  const st = s.state();
  assert.equal(st.list.selection.missionId, id(2));
  assert.equal(st.list.selection.sync.view.mission.id, id(2));
  assert.equal(st.stats.staleSelection, 1);
});

test("disconnect forgets token and display; a late answer is dropped", async () => {
  let release;
  const slow = new Promise((r) => { release = r; });
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1]))], ["GET /v1/missions/" + id(1)]: [slow] });
  const s = session(t);
  await s.connect(TOKEN);
  const late = s.selectMission(id(1));
  s.disconnect();
  release(ok(sync(1, "SNAPSHOT")));
  await late;
  const st = s.state();
  assert.equal(st.phase, "disconnected");
  assert.equal(s.hasToken(), false);
  assert.equal(C.shownItems(st.list).length, 0);
  assert.equal(st.list.selection, null);
});

test("poll: DELTA drains has_more within five pages; RESET_REQUIRED waits for the explicit reload", async () => {
  const ev = (n) => ({ sequence: n, at: "2026-10-06T17:00:0" + (n % 10) + "Z", kind: "STEP" });
  const polls = [ok(sync(1, "DELTA", { seq: 11, count: 4, asOf: 12, events: [ev(11)], more: true })),
    ok(sync(1, "DELTA", { seq: 12, count: 5, asOf: 12, events: [ev(12)] })),
    ok(sync(1, "RESET_REQUIRED", { seq: 20, count: 9, reason: "ANCHOR_CHANGED" })),
    ok(sync(1, "DELTA", { seq: 20, count: 9, asOf: 20 }))];
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1]))],
    ["GET /v1/missions/" + id(1)]: [ok(sync(1, "SNAPSHOT"))], ["POST /v1/missions/" + id(1) + "/poll"]: polls });
  const s = session(t);
  await s.connect(TOKEN);
  await s.selectMission(id(1));
  await s.refreshSelection();
  let sel = s.state().list.selection.sync;
  assert.deepEqual(sel.refs.map((r) => r.sequence), [11, 12]);
  assert.equal(sel.cursor.sequence, 12);
  await s.refreshSelection();
  sel = s.state().list.selection.sync;
  assert.equal(sel.reset.reason, "ANCHOR_CHANGED");
  assert.equal(sel.view.asOf, 12, "view frozen until the explicit reload");
  assert.equal(await s.refreshSelection(), false, "no poll while a reset waits");
  await s.acceptReset();
  sel = s.state().list.selection.sync;
  assert.equal(sel.reset, null);
  assert.equal(sel.cursor.sequence, 20);
  const polled = t.calls.filter((c) => c.path.endsWith("/poll"));
  assert.equal(polled.length, 4);
  assert.deepEqual(polled[0].body.cursor, cursor(1, 10, 3));
});

test("an invalid or authority-claiming answer is rejected, never displayed", async () => {
  const bad = page([1]);
  bad.authorizes_execution = true;
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(bad)] });
  const s = session(t);
  await s.connect(TOKEN);
  const st = s.state();
  assert.equal(st.list.items.length, 0);
  assert.equal(st.list.stats.rejected[0].code, "AUTHORITY_CLAIMED");
  const h = scripted({ "GET /v1/health": [ok(Object.assign(health(), { mode: "read_write" }))] });
  const s2 = session(h);
  assert.equal(await s2.connect(TOKEN), false);
  assert.equal(s2.state().problem.code, "INVALID_HEALTH");
  const html = scripted({ "GET /v1/health": [{ status: 404, json: null }] });
  const s3 = session(html);
  assert.equal(await s3.connect(TOKEN), false);
  assert.equal(s3.state().problem.code, "INVALID_RESPONSE");
});

test("a malformed mission id is never turned into a request path", async () => {
  const t = scripted({ "GET /v1/health": [ok(health())], "POST /v1/missions": [ok(page([1]))] });
  const s = session(t);
  await s.connect(TOKEN);
  for (const bad of ["../health", "m-1/../../x", id(1) + "?x=1", ""]) assert.equal(await s.selectMission(bad), false);
  assert.equal(t.calls.length, 2);
});
