/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : g021.test.js
 * Description : Régressions G021 : total annoncé, nombre reçu et has_more (inventaire)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
// G021_LIST_STATE=<path to another mission-list-state.js> replays these tests against an older
// version (used once to show they fail on bfa75d2; see docs/validation/2026-10-06/claude-g021/).
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const L = require(process.env.G021_LIST_STATE ? path.resolve(process.env.G021_LIST_STATE) : "../mission-list-state.js");
const F = require("../fixtures/mission-list-fixtures.js");

const O = F.observed.trace;
const copy = (v) => JSON.parse(JSON.stringify(v));
const D = (name, i) => copy(i === undefined ? F.derived[name].value : F.derived[name].value[i]);
const req = (s) => Object.assign(L.nextPageRequest(s) || { kind: "list", epoch: s.epoch, cursor: s.nextCursor }, { receivedAt: "t" });
const feed = (s, page) => L.receivePage(s, page, req(s));
const codes = (s) => s.stats.rejected.map((r) => r.code);
const terminal = (page) => { const p = copy(page); p.has_more = false; p.next_cursor = null; return p; };
function withTotal(page, total) {
  const p = copy(page);
  p.generation.mission_count = total;
  if (p.next_cursor) p.next_cursor.generation.mission_count = total;
  return p;
}

test("Codex's probe: a first page ending early (1 of 3) is refused, never complete", () => {
  const s = feed(L.createState(), terminal(O.fresh_pages[0]));
  assert.equal(s.complete, false);
  assert.equal(s.items.length, 0, "nothing taken from an inconsistent page");
  assert.deepEqual(codes(s), ["LIST_ENDED_EARLY"]);
  assert.equal(L.nextPageRequest(s), null, "listing stopped; explicit relisting needed");
  assert.doesNotMatch(L.summary(s).status, /entièrement/);
});

test("a later page ending early (2 of 3) keeps what was received, refused, not complete", () => {
  let s = feed(L.createState(), O.fresh_pages[0]);
  s = feed(s, D("ended_early"));
  assert.deepEqual([s.items.length, s.complete], [1, false]);
  assert.deepEqual(codes(s), ["LIST_ENDED_EARLY"]);
  assert.match(L.summary(s).status, /incomplète.*1 reçues sur 3 annoncées/);
});

test("announced total zero with an item, and an overflow across pages, are refused", () => {
  const zero = feed(L.createState(), withTotal(D("varied_page"), 0));
  assert.deepEqual(codes(zero), ["COUNT_EXCEEDED"]);
  assert.equal(zero.items.length, 0);
  let s = feed(L.createState(), withTotal(D("big_inventory", 0), 150));
  assert.equal(s.items.length, 100);
  s = feed(s, withTotal(D("big_inventory", 1), 150));
  assert.deepEqual(codes(s), ["COUNT_EXCEEDED"]);
  assert.deepEqual([s.items.length, s.complete, s.truncated], [100, false, false]);
});

test("has_more=true although every announced mission was received is refused", () => {
  const s = feed(L.createState(), D("has_more_inconsistent"));
  assert.deepEqual(codes(s), ["HAS_MORE_INCONSISTENT"]);
  assert.equal(s.complete, false);
});

test("valid traces are unchanged: observed 3 pages complete, empty store, 250 → 200 shown and truncated", () => {
  let s = L.createState();
  for (const p of O.fresh_pages) s = feed(s, p);
  assert.deepEqual([s.items.length, s.complete, codes(s).length], [3, true, 0]);
  const empty = feed(L.createState(), D("empty_store"));
  assert.deepEqual([empty.complete, codes(empty).length], [true, 0]);
  let big = L.createState();
  for (let i = 0; i < 3; i++) big = feed(big, D("big_inventory", i));
  assert.deepEqual([big.items.length, big.truncated, big.complete, codes(big).length], [200, true, false, 0]);
  assert.match(L.summary(big).status, /200 affichées sur 250 annoncées/);
});

test("after a refusal: late pages are frozen, explicit relisting reads the generation completely", () => {
  let s = feed(L.createState(), O.fresh_pages[0]);
  const page2 = req(s);
  s = L.receivePage(s, D("ended_early"), page2);
  s = L.receivePage(s, O.fresh_pages[1], page2); // the correct page 2, arriving late
  assert.equal(s.items.length, 1, "no page taken while the listing is halted");
  s = L.relist(s);
  for (const p of O.fresh_pages) s = feed(s, p);
  assert.deepEqual([s.items.length, s.complete], [3, true]);
  assert.equal(L.summary(s).status, "Capture entièrement lue (3)");
});
