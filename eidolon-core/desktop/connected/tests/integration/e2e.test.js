/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : e2e.test.js
 * Description : Banc de bout en bout client–API réel : pagination, reset, absence de réémission, nettoyage (C-TASK-G038)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:
//   NODE_PATH=<dir containing playwright> node --test "desktop/connected/tests/**/*.test.js"
// Extends tests/server.test.js and tests/receipts.test.js (G031, G036) without repeating their
// scenarios (wrong token, stop/restart, new Store, receipts). Real python http_api on 127.0.0.1:0,
// synthetic states in temporary folders; waits on conditions, never on long fixed delays.
// "skipped" means NOT executed (no python3 >= 3.11, or no Chromium), never passed.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../../src/session.js");
const { WEB_ROOT, CAPTURES, chromium, chromiumUnavailable, noPython, cli, makeState, bulkCreate, startServer, stop,
  nodeTransport, cleanup } = require("../helpers.js");

// Transport that records every request and can run a hook between two requests.
function recording(base, hooks) {
  const calls = [];
  const inner = nodeTransport(base);
  return { calls, transport: async (method, p, body, token) => {
    const n = calls.length;
    if (hooks && hooks[n]) hooks[n]();
    calls.push({ method, path: p, body: body === undefined ? undefined : JSON.parse(JSON.stringify(body)) });
    return inner(method, p, body, token);
  } };
}

const READ_ROUTES = /^(GET \/v1\/health|POST \/v1\/missions|GET \/v1\/missions\/m-[0-9a-f]{32}|POST \/v1\/missions\/m-[0-9a-f]{32}\/poll|POST \/v1\/command-receipt)$/;

test("pagination over the real API: 150 extra missions read in two pages, exact cursor echoed, complete", { skip: noPython }, async () => {
  const env = makeState();
  let server;
  try {
    bulkCreate(env.state, 150);
    server = await startServer(env, null);
    const rec = recording(server.base);
    const s = C.createSession({ transport: rec.transport });
    await s.connect(env.token);
    const st = s.state();
    const lists = rec.calls.filter((c) => c.path === "/v1/missions");
    assert.equal(lists.length, 2);
    assert.deepEqual(lists[0].body, { limit: 100 });
    assert.equal(lists[1].body.cursor.after_id, st.list.items[99].mission.id, "cursor sent back unchanged");
    assert.equal(st.list.items.length, 154);
    assert.equal(st.list.complete, true);
    const ids = st.list.items.map((i) => i.mission.id);
    assert.deepEqual(ids, [...ids].sort(), "ordered");
    assert.equal(new Set(ids).size, ids.length, "no duplicate");
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("more than 200 missions: the client stops at 200, says truncated, and never loops", { skip: noPython }, async () => {
  const env = makeState();
  let server;
  try {
    bulkCreate(env.state, 250);
    server = await startServer(env, null);
    const rec = recording(server.base);
    const s = C.createSession({ transport: rec.transport });
    await s.connect(env.token);
    const st = s.state();
    assert.equal(st.list.items.length, 200);
    assert.equal(st.list.truncated, true);
    assert.equal(st.list.complete, false);
    assert.match(C.listSummary(st.list).status, /Liste tronquée : 200 affichées sur 254 annoncées/);
    assert.equal(rec.calls.filter((c) => c.path === "/v1/missions").length, 2);
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("a mission created by another process between two pages: RESET_REQUIRED, old inventory stale, explicit relist complete", { skip: noPython }, async () => {
  const env = makeState();
  let server;
  try {
    bulkCreate(env.state, 120);
    server = await startServer(env, null);
    // Hook before request #2 (the second list page): the Core CLI writes in between.
    const rec = recording(server.base, { 2: () => cli(env.state, ["create", "écrite entre deux pages"]) });
    const s = C.createSession({ transport: rec.transport });
    await s.connect(env.token);
    let st = s.state();
    assert.equal(st.list.stale.reason, "STATE_CHANGED");
    assert.equal(C.shownItems(st.list).length, 100, "first page kept, marked stale, nothing mixed");
    await s.relist();
    st = s.state();
    assert.equal(st.list.complete, true);
    assert.equal(st.list.items.length, 125);
    assert.equal(rec.calls.filter((c) => c.path === "/v1/missions").length, 4);
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("a cancellation by the Core CLI is observed once, over repeated polls, and the client only ever reads", { skip: noPython }, async () => {
  const env = makeState();
  let server;
  try {
    server = await startServer(env, null);
    const rec = recording(server.base);
    const s = C.createSession({ transport: rec.transport });
    await s.connect(env.token);
    await s.selectMission(env.toCancel);
    const before = cli(env.state, ["show", env.toCancel, "--events"]).events.length;
    cli(env.state, ["cancel", env.toCancel]);
    for (let i = 0; i < 4; i++) await s.refreshSelection();
    const sync = s.state().list.selection.sync;
    assert.deepEqual(sync.refs.map((r) => r.kind), ["CANCEL_REQUESTED", "CANCELLED"], "each event once");
    const after = cli(env.state, ["show", env.toCancel, "--events"]).events.length;
    assert.equal(after - before, 2, "only the two events written by the CLI; nothing re-emitted by the client");
    assert.ok(rec.calls.every((c) => READ_ROUTES.test(c.method + " " + c.path)), "read routes only");
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("cleanup on failure paths: refused start, a throwing scenario, a browser that cannot start", { skip: noPython }, async () => {
  // 1. Server refused at start (state missing): the promise rejects and the child is gone.
  const env = makeState();
  const missing = Object.assign({}, env, { state: path.join(env.dir, "absent") });
  await assert.rejects(startServer(missing, null), /server exited/);
  // 2. A scenario that throws mid-way still stops its server and removes its folder.
  let server;
  await assert.rejects((async () => {
    try {
      server = await startServer(env, null);
      throw new Error("échec simulé du scénario");
    } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
  })(), /échec simulé/);
  assert.notEqual(server.child.exitCode === null && server.child.signalCode === null, true, "server process ended");
  assert.equal(fs.existsSync(env.dir), false, "folder removed");
  // 3. A browser that cannot start: launch rejects, cleanup still stops the server.
  if (chromium) {
    const env2 = makeState();
    let server2, browser;
    await assert.rejects((async () => {
      try {
        server2 = await startServer(env2, null);
        browser = await chromium.launch({ executablePath: path.join(env2.dir, "no-such-browser") });
      } finally { await cleanup({ browser, servers: [server2], dirs: [env2.dir] }); }
    })());
    assert.ok(server2.child.exitCode !== null || server2.child.signalCode !== null, "server stopped after browser failure");
    assert.equal(fs.existsSync(env2.dir), false);
  }
});

test("Chromium on the real server: 150 missions listed and keyboard-selectable, then server stopped", { skip: noPython || chromiumUnavailable }, async () => {
  const env = makeState();
  let server, browser;
  try {
    bulkCreate(env.state, 150);
    server = await startServer(env, WEB_ROOT);
    browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    await page.goto(server.base + "/");
    await page.fill("#token", env.token);
    await page.click("#connect");
    await page.waitForFunction(() => /Capture entièrement lue \(154\)/.test(document.querySelector("#list-status").textContent));
    assert.equal(await page.locator(".mission-button").count(), 154);
    await page.locator(".mission-button").nth(120).focus();
    await page.keyboard.press("Enter");
    await page.waitForSelector(".fields");
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g038-150-missions.png") });
    await stop(server);
    await page.click("#refresh");
    await page.waitForFunction(() => /injoignable/.test(document.querySelector("#connection-status").textContent));
    assert.equal(await page.locator(".mission-button").count(), 154, "last inventory kept");
  } finally { await cleanup({ browser, servers: [server], dirs: [env.dir] }); }
});
