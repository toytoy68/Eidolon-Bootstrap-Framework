/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : list.test.js
 * Description : Tests du consommateur mission-list/1 du prototype (C-TASK-G018)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const L = require("../mission-list-state.js");
const S = require("../sync-state.js");
const F = require("../fixtures/mission-list-fixtures.js");

const O = F.observed.trace;
const D = (name, i) => JSON.parse(JSON.stringify(i === undefined ? F.derived[name].value : F.derived[name].value[i]));
const copy = (v) => JSON.parse(JSON.stringify(v));
const req = (state, extra) => Object.assign(L.nextPageRequest(state) || { kind: "list", epoch: state.epoch, cursor: state.nextCursor }, { receivedAt: "t" }, extra || {});
const feed = (state, page, extra) => L.receivePage(state, page, req(state, extra));
const ids = (state) => L.shownItems(state).map((it) => it.mission.id);

test("observed trace is kept verbatim with its SHA-256", () => {
  const file = path.resolve(__dirname, "../../..", O.source);
  const raw = fs.readFileSync(file);
  assert.equal(crypto.createHash("sha256").update(raw).digest("hex"), O.sha256);
  const trace = JSON.parse(raw);
  assert.deepEqual(O.fresh_pages, trace.fresh_pages);
  assert.deepEqual(O.changed_between_pages, trace.changed_between_pages);
  for (const [name, d] of Object.entries(F.derived)) assert.ok(d.derived && d.why.length > 20, name + " is labelled");
});

test("complete pagination of one generation: no loss, no duplicate, cursor sent back unchanged", () => {
  let s = L.createState();
  const asked = [];
  for (const p of O.fresh_pages) {
    const r = L.nextPageRequest(s);
    asked.push(r.cursor);
    s = L.receivePage(s, p, Object.assign(r, { receivedAt: "t" }));
  }
  assert.deepEqual(asked, [null, O.fresh_pages[0].next_cursor, O.fresh_pages[1].next_cursor]);
  assert.deepEqual(ids(s), O.fresh_pages.map((p) => p.items[0].mission.id));
  assert.equal(new Set(ids(s)).size, 3);
  assert.equal(s.complete, true);
  assert.equal(L.nextPageRequest(s), null, "nothing more to ask once has_more=false");
  assert.match(L.summary(s).status, /entièrement lue \(3\)/);
});

test("a repeated or late page changes nothing", () => {
  let s = feed(L.createState(), O.fresh_pages[0]);
  const page2Request = req(s);
  s = L.receivePage(s, O.fresh_pages[1], page2Request);
  const before = JSON.stringify(s.items);
  s = L.receivePage(s, O.fresh_pages[1], page2Request);          // same answer again
  s = L.receivePage(s, O.fresh_pages[0], Object.assign(req(s), { cursor: null })); // first page again, late
  assert.equal(JSON.stringify(s.items), before);
  assert.equal(s.stats.repeatedPages, 2);
});

test("RESET_REQUIRED between pages: old inventory kept as stale, nothing asked, no merge, explicit relist", () => {
  let s = feed(L.createState(), O.initial_page);
  const oldRequest = req(s);
  s = L.receivePage(s, O.changed_between_pages, oldRequest);
  assert.deepEqual(s.stale, { reason: "STATE_CHANGED", receivedAt: "t" });
  assert.equal(L.nextPageRequest(s), null);
  assert.equal(L.summary(s).stale, true);
  const frozen = L.receivePage(s, O.fresh_pages[1], oldRequest);   // late page of any generation
  assert.equal(JSON.stringify(frozen.items), JSON.stringify(s.items));
  assert.equal(frozen.stats.frozenAnswers, 1);
  s = L.relist(frozen);
  assert.equal(s.items.length, 0);
  assert.equal(s.previous.items.length, 1, "old inventory still shown, marked stale");
  assert.equal(L.receivePage(s, O.fresh_pages[1], oldRequest).stats.staleAnswers, 1, "older epoch ignored");
  for (const p of O.fresh_pages) s = feed(s, p);
  assert.equal(s.complete, true);
  assert.equal(s.previous, null);
  assert.ok(s.items.every((it) => it.asOf >= 2), "only generation-4 projections");
  assert.equal(s.items[0].mission.cancel_requested, true, "the cancel request that caused the reset is visible");
});

test("a page of another generation is refused even if structurally valid", () => {
  let s = feed(L.createState(), O.fresh_pages[0]);
  s = feed(s, D("mixed_generation"));
  assert.deepEqual(s.stats.rejected.map((r) => r.code), ["GENERATION_MIXED"]);
  assert.equal(s.items.length, 1);
});

test("disconnection: a page received offline is ignored; the same page is asked again with the same cursor", () => {
  let s = feed(L.createState(), O.fresh_pages[0]);
  const r = req(s);
  s = L.setConnection(s, "offline");
  assert.equal(L.nextPageRequest(s), null);
  s = L.receivePage(s, O.fresh_pages[1], r);
  assert.equal(s.items.length, 1);
  s = L.setConnection(s, "online");
  assert.deepEqual(L.nextPageRequest(s).cursor, r.cursor);
  s = feed(feed(s, O.fresh_pages[1]), O.fresh_pages[2]);
  assert.equal(s.complete, true);
});

test("visible total bound: 250 announced, 200 shown, never claimed complete", () => {
  let s = L.createState();
  for (let i = 0; i < 3; i++) s = feed(s, D("big_inventory", i));
  assert.equal(s.items.length, L.MAX_ITEMS);
  assert.equal(s.truncated, true);
  assert.equal(s.complete, false);
  assert.equal(L.nextPageRequest(s), null);
  assert.match(L.summary(s).status, /tronquée : 200 affichées sur 250 annoncées/);
});

test("validation: authority, unsafe integers, ordering, cursors, reset shape", () => {
  assert.equal(L.validatePage(D("authority_claimed")), "AUTHORITY_CLAIMED");
  assert.equal(L.validatePage(D("unsafe_integer")), "UNSAFE_OR_INVALID_INTEGER");
  const unordered = copy(D("varied_page")); unordered.items.reverse();
  assert.equal(L.validatePage(unordered), "ITEMS_NOT_ORDERED");
  const badCursor = copy(O.fresh_pages[0]); badCursor.next_cursor.after_id = O.fresh_pages[1].items[0].mission.id;
  assert.equal(L.validatePage(badCursor), "INVALID_LIST_CURSOR");
  const floatGen = copy(O.fresh_pages[0]); floatGen.generation.sequence = 4.5;
  assert.equal(L.validatePage(floatGen), "UNSAFE_OR_INVALID_INTEGER");
  const resetWithItems = copy(O.changed_between_pages); resetWithItems.items = copy(O.fresh_pages[0].items);
  assert.equal(L.validatePage(resetWithItems), "INVALID_RESET");
  const syncEnv = copy(F.derived.selection_snapshots.value[O.fresh_pages[0].items[0].mission.id]);
  assert.equal(L.validatePage(syncEnv), "UNSUPPORTED_PROTOCOL", "a client-sync envelope is not a list page");
  assert.equal(L.validatePage(D("empty_store")), null);
});

test("empty store, null objective, review with cancellation: statuses are not confused", () => {
  const empty = feed(L.createState(), D("empty_store"));
  assert.equal(empty.complete, true);
  assert.equal(L.summary(empty).status, "Aucune mission dans cette capture");
  const v = feed(L.createState(), D("varied_page"));
  const byStatus = Object.fromEntries(v.items.map((it) => [it.mission.status + (it.mission.cancel_requested ? "+cancel" : ""), it.mission]));
  assert.equal(S.missionLabel(byStatus["REVIEW_REQUIRED+cancel"]), "Revue requise — effet à vérifier");
  assert.equal(S.missionLabel(byStatus["RUNNING+cancel"]), "Annulation demandée — issue non confirmée");
  assert.equal(S.missionLabel(byStatus.BLOCKED), "Bloquée — précision demandée");
  assert.equal(byStatus.BLOCKED.objective_kind, null);
  for (const m of v.items.map((it) => it.mission)) assert.doesNotMatch(S.missionLabel(m) + (S.cancelNote(m) || ""), /CANCELLED|autoris/i);
});

test("selection asks only a client-sync snapshot of that id; the list cursor is never an event cursor", () => {
  let s = L.createState();
  for (const p of O.fresh_pages) s = feed(s, p);
  const id = O.fresh_pages[1].items[0].mission.id;
  s = L.select(s, id);
  const r = L.selectionRequest(s);
  assert.deepEqual([r.kind, r.missionId, r.syncKind, r.cursor], ["mission-snapshot", id, "snapshot", null]);
  assert.equal(JSON.stringify(r).includes("after_id"), false);
  // Feeding the list cursor to client-sync as if it were an event cursor is rejected by sync-state.
  const forged = copy(F.derived.selection_snapshots.value[id]); forged.cursor = copy(O.fresh_pages[0].next_cursor);
  assert.equal(S.validateEnvelope(forged), "INVALID_CURSOR");
  s = L.receiveSelection(s, copy(F.derived.selection_snapshots.value[id]), Object.assign({}, r, { receivedAt: "t" }));
  assert.equal(s.selection.sync.view.mission.id, id);
  assert.equal(L.select(s, "m-" + "0".repeat(32)).stats.rejected.at(-1).code, "NOT_IN_INVENTORY");
});

test("an answer for an older selection never replaces the mission shown", () => {
  let s = L.createState();
  for (const p of O.fresh_pages) s = feed(s, p);
  const [a, b] = O.fresh_pages.map((p) => p.items[0].mission.id);
  s = L.select(s, a); const ra = L.selectionRequest(s);
  s = L.select(s, b); const rb = L.selectionRequest(s);
  s = L.receiveSelection(s, copy(F.derived.selection_snapshots.value[a]), Object.assign({}, ra, { receivedAt: "t1" }));
  assert.equal(s.stats.staleSelections, 1);
  assert.equal(s.selection.missionId, b);
  assert.equal(s.selection.sync.view, null);
  s = L.receiveSelection(s, copy(F.derived.selection_snapshots.value[b]), Object.assign({}, rb, { receivedAt: "t2" }));
  assert.equal(s.selection.sync.view.mission.id, b);
  s = L.receiveSelection(s, copy(F.derived.selection_snapshots.value[a]), Object.assign({}, rb, { receivedAt: "t3" }));
  assert.equal(s.stats.rejected.at(-1).code, "SELECTION_MISMATCH");
  s = L.receiveSelection(s, D("selection_other_store"), Object.assign({}, rb, { receivedAt: "t4" }));
  assert.equal(s.stats.rejected.at(-1).code, "SELECTION_MISMATCH");
});

test("selection from another store than the list is refused", () => {
  let s = L.createState();
  for (const p of O.fresh_pages) s = feed(s, p);
  const other = D("selection_other_store");
  s = L.select(s, other.mission_id);
  s = L.receiveSelection(s, other, Object.assign({}, L.selectionRequest(s), { receivedAt: "t" }));
  assert.equal(s.stats.rejected.at(-1).code, "SELECTION_STORE_MISMATCH");
  assert.equal(s.selection.sync.view, null);
});

test("nothing in the consumer can emit a command", () => {
  const src = fs.readFileSync(path.join(__dirname, "../mission-list-state.js"), "utf8");
  assert.doesNotMatch(src, /fetch\(|XMLHttpRequest|WebSocket|localStorage|setTimeout|setInterval/);
  for (const name of Object.keys(L)) assert.doesNotMatch(name, /approve|decide|run|cancel|submit/i);
});
