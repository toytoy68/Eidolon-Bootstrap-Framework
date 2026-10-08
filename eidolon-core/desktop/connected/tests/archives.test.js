/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : archives.test.js
 * Description : Catalogue paginé des archives dans le client connecté, contrat C-030 (C-TASK-G066)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run from eidolon-core/: NODE_PATH=<dir containing playwright> node --test "desktop/connected/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const A = require("../src/archives.js");
const C = require("../src/session.js");
const { WEB_ROOT, chromium, chromiumUnavailable, noPython, makeArchiveFixture, startServer, nodeTransport,
  cleanup } = require("./helpers.js");

const STORE = "s-" + "a".repeat(32);
const SHA = (c) => c.repeat(64);

function item(index, extra) {
  return Object.assign({ file: "research-archive-" + String(index).padStart(6, "0") + ".json", index, sha256: SHA("b"),
    created_at_ms: 1760000000000 + index, count: 2, queries_with_text: 1, legacy_runs_without_text: 1, linked_missions: 1 }, extra);
}

// A page of the C-030 contract for `total` archives, starting after `after`.
function page(total, after, n, extra) {
  const items = [];
  for (let i = after + 1; i <= Math.min(total, after + n); i++) items.push(item(i));
  const end = after + items.length;
  return Object.assign({ protocol: A.PROTOCOL, status: "PAGE", store_id: STORE, catalog_sha256: SHA("c"), chain_head: SHA("d"),
    archive_count: total, run_count: total * 2, observed_at: "2026-10-08T07:00:00Z", items, has_more: end < total,
    next_cursor: end < total ? { version: 1, store_id: STORE, catalog_sha256: SHA("c"), after_index: end } : null },
  A.FLAGS, extra);
}

function reset(reason) {
  return Object.assign(page(3, 0, 0), { status: "RESET_REQUIRED", reason, items: [], has_more: false, next_cursor: null });
}

function load(st, kind, answer, limit) {
  const r = A.request(st, kind, limit || 2);
  assert.ok(r.req, "request allowed");
  return A.receive(r.state, r.req, answer, STORE, "2026-10-08T07:00:01Z");
}

test("G066 pages of one generation are appended in order; the list is complete only at the end", () => {
  let st = load(A.create(), "first", page(3, 0, 2));
  assert.equal(st.status, "loaded");
  assert.deepEqual(A.summary(st), { shown: 2, total: 3, runs: 6, complete: false, current: true });
  st = load(st, "more", page(3, 2, 2));
  assert.deepEqual(st.items.map((x) => x.index), [1, 2, 3]);
  assert.deepEqual(A.summary(st), { shown: 3, total: 3, runs: 6, complete: true, current: true });
  assert.equal(A.request(st, "more").req, null, "nothing after the last page");
  const empty = load(A.create(), "first", page(0, 0, 2));
  assert.deepEqual(A.summary(empty), { shown: 0, total: 0, runs: 0, complete: true, current: true });
});

test("G066 refused pages never change what is shown and are never mixed", () => {
  const first = load(A.create(), "first", page(3, 0, 2));
  const cases = {
    AUTHORITY_CLAIMED: page(3, 2, 2, { authenticity_verified: true }),
    INVALID_ARCHIVE_PAGE: page(3, 2, 2, { query: "texte" }),
    STORE_MISMATCH: page(3, 2, 2, { store_id: "s-" + "f".repeat(32) }),
    CATALOG_MISMATCH: page(3, 2, 2, { catalog_sha256: SHA("e") }),
    UNSUPPORTED_PROTOCOL: page(3, 2, 2, { protocol: "other/1" }),
    UNKNOWN_STATUS: page(3, 2, 2, { status: "LATER" })
  };
  for (const [code, answer] of Object.entries(cases)) {
    const st = load(first, "more", answer);
    assert.equal(st.code, code, code);
    assert.deepEqual(st.items, first.items, code + ": shown list kept");
    assert.equal(st.stale, true, code + ": marked stale");
    assert.equal(A.request(st, "more").req, null, code + ": no continuation from a frozen list");
  }
  const gap = page(3, 2, 2);
  gap.items[0] = item(4);
  assert.equal(load(first, "more", gap).code, "PAGE_GAP");
  const extraField = page(3, 2, 2);
  extraField.items[0] = item(3, { guard_id: "g-x" });
  assert.equal(load(first, "more", extraField).code, "INVALID_ARCHIVE_PAGE", "no extra metadata accepted");
  const badSum = page(3, 2, 2);
  badSum.items[0] = item(3, { queries_with_text: 2 });
  assert.equal(load(first, "more", badSum).code, "INVALID_ARCHIVE_PAGE");
  const tooMany = page(10, 0, 3);
  assert.equal(load(A.create(), "first", tooMany, 2).code, "INVALID_ARCHIVE_PAGE", "more items than asked");
  const badCursor = page(3, 0, 2);
  badCursor.next_cursor.after_index = 1;
  assert.equal(load(A.create(), "first", badCursor).code, "INVALID_ARCHIVE_PAGE");
  const unsafe = page(3, 0, 2, { run_count: 2 ** 53 });
  assert.equal(load(A.create(), "first", unsafe).code, "INVALID_ARCHIVE_PAGE");
});

test("G066 RESET_REQUIRED freezes the previous list until an explicit reload of a new generation", () => {
  const first = load(A.create(), "first", page(3, 0, 2));
  for (const reason of ["CATALOG_CHANGED", "STORE_CHANGED"]) {
    const st = load(first, "more", reset(reason));
    assert.equal(st.status, "reset");
    assert.equal(st.code, reason);
    assert.deepEqual(st.items, first.items);
    assert.equal(st.stale, true);
    assert.equal(A.request(st, "more").req, null);
    const again = load(st, "first", page(5, 0, 2));
    assert.deepEqual([again.stale, again.items.length, again.catalog.archiveCount], [false, 2, 5], "replaced, not concatenated");
  }
  assert.equal(load(first, "more", Object.assign(reset("OTHER"))).code, "INVALID_ARCHIVE_PAGE");
});

test("G066 an answer to an older request is ignored after a reload", () => {
  const first = load(A.create(), "first", page(3, 0, 2));
  const more = A.request(first, "more", 2);
  const reload = A.request(more.state, "first", 2);
  const late = A.receive(reload.state, more.req, page(3, 2, 2), STORE, "t");
  assert.equal(late.stats.staleAnswers, 1);
  assert.equal(late.status, "loading");
  const fresh = A.receive(late, reload.req, page(3, 0, 2), STORE, "t");
  assert.deepEqual(fresh.items.map((x) => x.index), [1, 2]);
  const lateError = A.receiveError(fresh, more.req, "ARCHIVES_BUSY", "t");
  assert.equal(lateError.stale, false, "an old error does not freeze the new list");
});

// Fake transport: health then scripted archive answers.
function scripted(answers) {
  const calls = [];
  const transport = async (method, p, body) => {
    calls.push({ method, p, body });
    if (p === "/v1/health") return { status: 200, json: { protocol: C.PROTOCOL, mode: "read_only", authorizes_execution: false, store_id: STORE } };
    if (p === "/v1/missions") return { status: 200, json: { protocol: "eidolon-mission-list/1", status: "PAGE" } };
    const next = answers.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  return { transport, calls };
}
const err = (status, code) => ({ status, json: { protocol: C.PROTOCOL, error: code, authorizes_execution: false } });

test("G066 archive refusals stay in their panel; connection failures freeze the list", async () => {
  for (const [status, code] of [[404, "ARCHIVES_NOT_CONFIGURED"], [503, "ARCHIVES_UNAVAILABLE"], [503, "ARCHIVES_BUSY"],
    [400, "INVALID_ARCHIVE_CURSOR"]]) {
    const t = scripted([{ status: 200, json: page(3, 0, 2) }, err(status, code)]);
    const s = C.createSession({ transport: t.transport, archiveLimit: 2 });
    await s.connect("x".repeat(40));
    assert.equal(await s.loadArchives(), true);
    assert.equal(await s.moreArchives(), false);
    const st = s.state();
    assert.equal(st.phase, "connected", code + ": the connection is not declared down");
    assert.deepEqual([st.archives.code, st.archives.stale, st.archives.items.length], [code, true, 2], code);
  }
  const down = scripted([{ status: 200, json: page(3, 0, 2) }, err(503, "STATE_UNAVAILABLE")]);
  let s = C.createSession({ transport: down.transport, archiveLimit: 2 });
  await s.connect("x".repeat(40));
  await s.loadArchives();
  await s.moreArchives();
  assert.deepEqual([s.state().phase, s.state().archives.stale], ["unavailable", true]);
  assert.equal(await s.loadArchives(), false, "no read while the Store is unavailable");

  const lost = scripted([{ status: 200, json: page(3, 0, 2) }, err(401, "UNAUTHORIZED")]);
  s = C.createSession({ transport: lost.transport, archiveLimit: 2 });
  await s.connect("x".repeat(40));
  await s.loadArchives();
  await s.moreArchives();
  assert.deepEqual([s.state().phase, s.state().archives.stale, s.state().archives.items.length], ["unauthorized", true, 2]);
  await s.connect("y".repeat(40));
  assert.deepEqual(s.state().archives, A.create(), "a new session never shows the previous session's pages");
  assert.ok(!lost.calls.some((c) => c.p === "/v1/research-archives" && c.method !== "POST"));
});

test("G066 nothing is read without an explicit request, and a late answer after disconnect is dropped", async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const calls = [];
  const transport = async (method, p) => {
    calls.push(p);
    if (p === "/v1/health") return { status: 200, json: { protocol: C.PROTOCOL, mode: "read_only", authorizes_execution: false, store_id: STORE } };
    if (p === "/v1/missions") return { status: 200, json: null };
    await gate;
    return { status: 200, json: page(3, 0, 3) };
  };
  const s = C.createSession({ transport });
  await s.connect("x".repeat(40));
  assert.ok(!calls.includes("/v1/research-archives"), "connect does not read the catalog");
  const pending = s.loadArchives();
  s.disconnect();
  release();
  assert.equal(await pending, false);
  assert.deepEqual(s.state().archives, A.create());
});

function privateStrings(env) {
  const out = [env.archives, env.dir];
  for (const row of env.manifest.scenarios) out.push(row.mission_id);
  for (const name of fs.readdirSync(env.archives).filter((n) => n.endsWith(".json"))) {
    const meta = JSON.parse(fs.readFileSync(path.join(env.archives, name), "utf8"));
    out.push(meta.guard_id);
    for (const run of meta.runs) if (run.cleaned_query) out.push(JSON.parse(run.cleaned_query).text);
  }
  return out.filter(Boolean);
}

test("G066 real Core C-030 pages: two pages, change between pages, unavailable folder", { skip: noPython }, async () => {
  const env = makeArchiveFixture();
  let server;
  try {
    server = await startServer(env, null);
    const s = C.createSession({ transport: nodeTransport(server.base), archiveLimit: 2 });
    assert.equal(await s.connect(env.token), true);
    assert.equal(await s.loadArchives(), true);
    let st = s.state();
    assert.deepEqual(C.archiveSummary(st.archives), { shown: 2, total: 3, runs: 3, complete: false, current: true });
    assert.equal(await s.moreArchives(), true);
    st = s.state();
    assert.deepEqual(st.archives.items.map((x) => x.file),
      ["research-archive-000001.json", "research-archive-000002.json", "research-archive-000003.json"]);
    assert.equal(C.archiveSummary(st.archives).complete, true);
    // Mission ids are legitimately in the mission list; the archive state must hold none of them.
    const all = JSON.stringify(st.archives);
    for (const secret of privateStrings(env)) assert.ok(!all.includes(secret), "private value reached the archive state: " + secret.slice(0, 12));

    // The catalog changes between two pages: RESET_REQUIRED, previous list frozen, never mixed.
    assert.equal(await s.loadArchives(), true);
    const moved = path.join(env.dir, "moved.json");
    fs.renameSync(path.join(env.archives, "research-archive-000003.json"), moved);
    assert.equal(await s.moreArchives(), false);
    st = s.state();
    assert.deepEqual([st.archives.status, st.archives.code, st.archives.items.length, st.phase],
      ["reset", "CATALOG_CHANGED", 2, "connected"]);
    assert.equal(await s.loadArchives(), true);
    assert.deepEqual(C.archiveSummary(s.state().archives), { shown: 2, total: 2, runs: 2, complete: true, current: true });

    // A folder that is no longer private: 503 ARCHIVES_UNAVAILABLE, connection kept, list frozen.
    fs.chmodSync(env.archives, 0o755);
    assert.equal(await s.loadArchives(), false);
    st = s.state();
    assert.deepEqual([st.archives.code, st.archives.stale, st.phase], ["ARCHIVES_UNAVAILABLE", true, "connected"]);
    fs.chmodSync(env.archives, 0o700);
    fs.renameSync(moved, path.join(env.archives, "research-archive-000003.json"));
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("G066 real Core without --research-archives: ARCHIVES_NOT_CONFIGURED, missions still readable", { skip: noPython }, async () => {
  const env = makeArchiveFixture();
  let server;
  try {
    server = await startServer(Object.assign({}, env, { archives: null }), null);
    const s = C.createSession({ transport: nodeTransport(server.base) });
    assert.equal(await s.connect(env.token), true);
    assert.equal(await s.loadArchives(), false);
    const st = s.state();
    assert.deepEqual([st.archives.code, st.phase, st.list.items.length > 0], ["ARCHIVES_NOT_CONFIGURED", "connected", true]);
  } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
});

test("G066 Chromium: keyboard load, table of metadata only, small screen without page scroll", { skip: noPython || chromiumUnavailable }, async () => {
  const env = makeArchiveFixture();
  let server, browser;
  try {
    server = await startServer(env, WEB_ROOT);
    browser = await chromium.launch();
    const errors = [];
    for (const width of [1280, 360]) {
      const page = await browser.newPage({ viewport: { width, height: 800 } });
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(server.base + "/");
      assert.equal(await page.isDisabled("#archives-load"), true, "disabled before connection");
      await page.fill("#token", env.token);
      await page.click("#connect");
      await page.waitForSelector(".mission-button");
      assert.equal(await page.$("#archives-body table"), null, "not loaded automatically");
      await page.focus("#archives-load");
      await page.keyboard.press("Enter");
      await page.waitForSelector(".archives-table tbody tr");
      assert.equal(await page.$$eval(".archives-table tbody tr", (r) => r.length), 3);
      assert.equal(await page.textContent("#archives-load"), "Actualiser les archives");
      assert.equal(await page.isDisabled("#archives-more"), true, "all archives shown");
      const status = await page.textContent("#archives-status");
      assert.match(status, /3 archive\(s\) affichée\(s\) sur 3/);
      const section = await page.textContent("#archives");
      assert.match(section, /authenticité et prise en compte dans le journal actif non établies/);
      const panel = await page.$eval("#archives", (n) => n.outerHTML);
      for (const secret of privateStrings(env)) assert.ok(!panel.includes(secret), "private value in the archive panel");
      assert.equal(await page.$$eval("#archives a, #archives [download]", (n) => n.length), 0, "no link or download");
      const labels = await page.$$eval("#archives button", (b) => b.map((x) => x.textContent));
      assert.deepEqual(labels.filter((x) => /supprim|restaur|télécharg|export|relanc/i.test(x)), []);
      // Cells keep one line (no letter-by-letter column); a narrow screen scrolls the table region only.
      const cells = await page.$$eval(".archives-table th, .archives-table td", (n) => n.map((x) => x.getBoundingClientRect().height));
      assert.ok(Math.max(...cells) < 60, width + "px: a cell is " + Math.max(...cells) + "px high");
      const region = await page.$eval(".table-wrap", (n) => ({ tab: n.tabIndex, role: n.getAttribute("role"),
        scrolls: n.scrollWidth > n.clientWidth }));
      assert.deepEqual([region.tab, region.role], [0, "region"]);
      if (width === 360) assert.equal(region.scrolls, true, "360px: the table region scrolls horizontally");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 0, width + "px: the page scrolls horizontally by " + overflow + "px");
      await page.close();
    }
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [env.dir] }); }
});
