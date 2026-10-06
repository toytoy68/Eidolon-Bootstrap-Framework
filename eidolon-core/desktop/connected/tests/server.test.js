/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : server.test.js
 * Description : Client connecté contre le VRAI serveur http_api local (127.0.0.1) et Chromium (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run from eidolon-core/:
//   NODE_PATH=<dir containing playwright> node --test "desktop/connected/tests/*.test.js"
// Needs python3 with the Core sources (PYTHON overrides the interpreter). Builds a synthetic
// state with the Core CLI in a temporary directory, starts http_api on 127.0.0.1 with port 0,
// and never contacts anything else. CAPTURES=<dir> saves screenshots. Browser tests are
// skipped when playwright is unavailable; server tests are skipped without python3.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../src/session.js");
const { bundle } = require("../build.js");
const { WEB_ROOT, CAPTURES, chromium, chromiumUnavailable, hasPython, cli, makeState, startServer, stop,
  nodeTransport } = require("./helpers.js");

test("served assets are the committed ones and app.js is the current bundle", { skip: !hasPython && "python3 >= 3.11 unavailable" }, async () => {
  assert.equal(fs.readFileSync(path.join(WEB_ROOT, "app.js"), "utf8"), bundle(), "run node desktop/connected/build.js");
  const env = makeState();
  const server = await startServer(env, WEB_ROOT);
  try {
    for (const [p, file, type] of [["/", "index.html", "text/html"], ["/app.js", "app.js", "text/javascript"], ["/style.css", "style.css", "text/css"]]) {
      const res = await fetch(server.base + p);
      assert.equal(res.status, 200);
      assert.match(res.headers.get("content-type"), new RegExp(type));
      assert.match(res.headers.get("content-security-policy"), /script-src 'self'/);
      assert.equal(Buffer.compare(Buffer.from(await res.arrayBuffer()), fs.readFileSync(path.join(WEB_ROOT, file))), 0);
    }
  } finally { await stop(server); fs.rmSync(env.dir, { recursive: true, force: true }); }
});

test("real server: list, snapshot, a cancellation written by another process seen by poll and relist", { skip: !hasPython && "python3 >= 3.11 unavailable" }, async () => {
  const env = makeState();
  const server = await startServer(env, null);
  try {
    const s = C.createSession({ transport: nodeTransport(server.base) });
    assert.equal(await s.connect(env.token), true);
    let st = s.state();
    assert.equal(st.list.items.length, 4);
    assert.equal(st.list.complete, true);
    const statuses = st.list.items.map((i) => i.mission.status).sort();
    assert.deepEqual(statuses, ["BLOCKED", "NEW", "NEW", "SUCCEEDED"]);
    await s.selectMission(env.toCancel);
    st = s.state();
    assert.equal(st.list.selection.sync.view.mission.cancel_requested, false);
    // Another process (the Core CLI) records a cancellation request while we are connected.
    cli(env.state, ["cancel", env.toCancel]);
    await s.refreshSelection();
    st = s.state();
    const sync = st.list.selection.sync;
    assert.ok(sync.refs.length >= 1, "the poll returned the new event reference");
    assert.equal(sync.view.mission.status, "CANCELLED");
    assert.equal(sync.view.mission.cancel_requested, true);
    await s.relist();
    st = s.state();
    assert.equal(st.list.items.find((i) => i.mission.id === env.toCancel).mission.status, "CANCELLED");
    assert.ok(!JSON.stringify(st).includes(env.token));
  } finally { await stop(server); fs.rmSync(env.dir, { recursive: true, force: true }); }
});

test("real server: wrong token is 401, a server stopped is offline with data kept, a restarted server resumes", { skip: !hasPython && "python3 >= 3.11 unavailable" }, async () => {
  const env = makeState();
  let server = await startServer(env, null);
  try {
    const bad = C.createSession({ transport: nodeTransport(server.base) });
    assert.equal(await bad.connect("b".repeat(43)), false);
    assert.equal(bad.state().phase, "unauthorized");
    assert.equal(bad.state().problem.code, "UNAUTHORIZED");

    let base = server.base;
    const s = C.createSession({ transport: (m, p, b, t) => nodeTransport(base)(m, p, b, t) });
    await s.connect(env.token);
    await s.selectMission(env.fresh);
    await stop(server);
    await s.refreshSelection();
    let st = s.state();
    assert.equal(st.phase, "offline");
    assert.equal(st.list.selection.sync.view.mission.id, env.fresh, "last capture kept");
    assert.equal(C.shownItems(st.list).length, 4);
    server = await startServer(env, null);
    base = server.base;
    assert.equal(await s.connect(env.token), true);
    st = s.state();
    assert.equal(st.phase, "connected");
    assert.equal(st.notice, null, "same store: nothing wiped");
    assert.equal(st.list.items.length, 4);
  } finally { await stop(server); fs.rmSync(env.dir, { recursive: true, force: true }); }
});

test("real server: another state behind the same address wipes the display", { skip: !hasPython && "python3 >= 3.11 unavailable" }, async () => {
  const a = makeState(), b = makeState();
  let server = await startServer(a, null);
  try {
    let base = server.base;
    const s = C.createSession({ transport: (m, p, body, t) => nodeTransport(base)(m, p, body, t) });
    await s.connect(a.token);
    await s.selectMission(a.fresh);
    const first = s.state().storeId;
    await stop(server);
    fs.copyFileSync(a.tokenFile, b.tokenFile);
    server = await startServer(b, null);
    base = server.base;
    await s.connect(a.token);
    const st = s.state();
    assert.notEqual(st.storeId, first);
    assert.match(st.notice, /Autre base/);
    assert.equal(st.list.selection, null);
    assert.ok(st.list.items.every((i) => i.mission.id !== a.fresh));
  } finally {
    await stop(server);
    fs.rmSync(a.dir, { recursive: true, force: true }); fs.rmSync(b.dir, { recursive: true, force: true });
  }
});

test("Chromium on the real server: token, list, details, no storage, no foreign request, mobile layout", { skip: (!hasPython && "python3 unavailable") || chromiumUnavailable }, async () => {
  const env = makeState();
  const server = await startServer(env, WEB_ROOT);
  let browser;
  try {
    browser = await chromium.launch();
    const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const page = await context.newPage();
    const requests = [], errors = [];
    page.on("request", (r) => requests.push(r.url()));
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(server.base + "/");
    assert.equal(await page.textContent("#connection-status"), "Non connecté.");
    await page.fill("#token", env.token);
    await page.click("#connect");
    await page.waitForSelector(".mission-button");
    assert.equal(await page.inputValue("#token"), "", "the input is emptied");
    assert.equal(await page.locator(".mission-button").count(), 4);
    assert.match(await page.textContent("#connection-status"), /Connecté en lecture seule/);
    assert.match(await page.textContent("#list-status"), /Capture entièrement lue \(4\)/);
    await page.click(".mission-button:has-text('À décider')");
    await page.waitForSelector(".fields");
    const details = await page.textContent("#details-body");
    assert.match(details, /BLOCKED/);
    assert.match(details, /Décision/);
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g031-connected-desktop.png"), fullPage: true });

    // Nothing persisted, token absent from DOM; no button that could command Core.
    const leaks = await page.evaluate((t) => ({
      local: localStorage.length, session: sessionStorage.length, cookie: document.cookie,
      dom: document.documentElement.outerHTML.includes(t),
      commands: [...document.querySelectorAll("button")].map((b) => b.textContent).filter((x) => /approuv|lancer|annuler|exécut/i.test(x))
    }), env.token);
    assert.deepEqual(leaks, { local: 0, session: 0, cookie: "", dom: false, commands: [] });

    // A cancellation written by the Core CLI is shown after an explicit refresh.
    await page.click(".mission-button:has-text('" + env.toCancel.slice(0, 10) + "')");
    await page.waitForFunction((id) => document.querySelector("#details-body").textContent.includes(id), env.toCancel);
    cli(env.state, ["cancel", env.toCancel]);
    await page.click("#refresh");
    await page.waitForFunction(() => document.querySelector("#details-body").textContent.includes("CANCELLED"));
    assert.match(await page.textContent("#details-body"), /Événements reçus/);

    // Mobile width: one column, no horizontal scroll.
    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 0, "no horizontal scroll at 390 px");
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g031-connected-mobile.png"), fullPage: true });

    // Server stopped: the page says so and keeps the last state.
    await stop(server);
    await page.click("#refresh");
    await page.waitForFunction(() => /injoignable/.test(document.querySelector("#connection-status").textContent));
    assert.match(await page.textContent("#details-body"), /Capture périmée/);
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g031-connected-offline.png"), fullPage: true });

    await page.click("#disconnect");
    assert.equal(await page.locator(".mission-button").count(), 0);
    assert.deepEqual(errors.filter((e) => !/Failed to fetch|ERR_CONNECTION_REFUSED/.test(e)), []);
    assert.ok(requests.every((u) => u.startsWith(server.base + "/")), "same origin only: " + requests.join(" "));
    await context.close();
  } finally {
    try { if (browser) await browser.close(); }
    finally {
      try { await stop(server); }
      finally { fs.rmSync(env.dir, { recursive: true, force: true }); }
    }
  }
});

test("Chromium: a page opened through another Host is refused by the server, and the client says so", { skip: (!hasPython && "python3 unavailable") || chromiumUnavailable }, async () => {
  const env = makeState();
  const server = await startServer(env, WEB_ROOT);
  let browser;
  try {
    browser = await chromium.launch({ args: ["--host-resolver-rules=MAP eidolon.test 127.0.0.1"] });
    const page = await browser.newPage();
    const res = await page.goto("http://eidolon.test:" + server.port + "/");
    assert.equal(res.status(), 403, "assets are refused for an unknown Host too");
  } finally {
    try { if (browser) await browser.close(); }
    finally {
      try { await stop(server); }
      finally { fs.rmSync(env.dir, { recursive: true, force: true }); }
    }
  }
});
