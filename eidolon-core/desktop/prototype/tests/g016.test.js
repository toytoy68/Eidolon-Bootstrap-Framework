/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : g016.test.js
 * Description : Régressions G012-01/02/03 du consommateur client-sync/1 (C-TASK-G016)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
// G016_SYNC_STATE=<path to another sync-state.js> replays these tests against an older version
// (used once to show they fail on cc9a64b; see docs/validation/2026-10-06/claude-g016/).
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const S = require(process.env.G016_SYNC_STATE ? path.resolve(process.env.G016_SYNC_STATE) : "../sync-state.js");
const F = require("../fixtures/client-sync-fixtures.js");
const O = F.original, D = (name) => F.derived[name].envelope;
const OBSERVED = F.observed.core_unsupported;

function ask(state, at) { const r = S.nextRequest(state) || { kind: "poll", epoch: state.epoch, cursorSequence: null }; return Object.assign({}, r, { receivedAt: at || "t" }); }
function deliver(state, env, request) { return S.receive(state, env, request || ask(state)); }
const copy = (v) => JSON.parse(JSON.stringify(v));

test("G012-01: the observed Core capture with objective_kind=null is accepted and shown without an invented objective", () => {
  assert.equal(OBSERVED.sha256.length, 64);
  assert.equal(OBSERVED.envelope.snapshot.mission.objective_kind, null, "real Core value, kept verbatim");
  assert.equal(S.validateEnvelope(OBSERVED.envelope), null);
  const s = deliver(S.createState(), OBSERVED.envelope);
  assert.equal(s.view.mission.objective_kind, null);
  assert.equal(s.view.mission.status, "BLOCKED");
  assert.equal(s.cursor.sequence, 2);
  assert.match(S.missionLabel(s.view.mission), /^Bloquée/);
});

test("G012-01: other validations are not relaxed (objective_kind must be a bounded string or null)", () => {
  for (const bad of [5, true, {}, "x".repeat(81)]) {
    const env = copy(OBSERVED.envelope);
    env.snapshot.mission.objective_kind = bad;
    assert.equal(S.validateEnvelope(env), "INVALID_MISSION", JSON.stringify(bad).slice(0, 20));
  }
});

test("G012-02: Codex's sequence — a late DELTA after RESET_REQUIRED no longer moves the view (1 → 11)", () => {
  let s = deliver(S.createState(), O.initial);
  const sameEpoch = ask(s);
  s = deliver(s, O.reset_example);
  const late = S.receive(s, O.pages[0], sameEpoch);
  assert.equal(late.view.asOf, 1);
  assert.equal(late.cursor.sequence, 1);
  assert.ok(late.reset, "reset still pending");
});

test("G012-02: while a reset is pending, late SNAPSHOT and DELTA are frozen out; nothing is requested", () => {
  let s = deliver(deliver(S.createState(), O.initial), O.pages[0]);
  const req = ask(s);
  s = deliver(s, O.reset_example);
  const view = s.view.asOf, cursor = s.cursor.sequence, refs = s.refs.length;
  const fresher = copy(O.pages[4]); fresher.status = "SNAPSHOT"; fresher.events = []; fresher.snapshot.as_of_sequence = 99;
  for (const env of [O.pages[1], O.pages[4], fresher]) s = S.receive(s, env, req);
  assert.deepEqual([s.view.asOf, s.cursor.sequence, s.refs.length], [view, cursor, refs]);
  assert.equal(S.nextRequest(s), null, "zero emission while waiting for the user");
});

test("G012-02: a second reset replaces the pending one; acceptance applies the latest, older-epoch answers stay ignored", () => {
  let s = deliver(S.createState(), O.initial);
  const oldRequest = ask(s);
  s = deliver(s, O.reset_example);
  s = deliver(s, D("reset_store_changed"));
  assert.equal(s.reset.reason, "STORE_CHANGED");
  assert.equal(s.view.asOf, 1, "still the old view");
  s = S.acceptReset(s);
  assert.equal(s.storeId, D("reset_store_changed").store_id);
  assert.equal(s.epoch, 1);
  const before = JSON.stringify([s.view, s.cursor]);
  const late = S.receive(s, O.pages[2], oldRequest);
  assert.equal(JSON.stringify([late.view, late.cursor]), before);
  const again = deliver(s, O.reset_example); // a new reset in the new epoch is pending again, not applied
  assert.equal(again.reset.reason, "ANCHOR_CHANGED");
  assert.equal(again.view.asOf, s.view.asOf);
});

test("G012-03: REVIEW_REQUIRED stays primary with a cancellation request; nothing promises CANCELLED", () => {
  const s = deliver(S.createState(), D("review_with_cancel"), { kind: "snapshot", epoch: 0, receivedAt: "t" });
  const m = s.view.mission;
  assert.equal(m.status, "REVIEW_REQUIRED");
  assert.equal(m.cancel_requested, true);
  assert.equal(S.missionLabel(m), "Revue requise — effet à vérifier");
  assert.equal(m.action_view.effect.code, "UNKNOWN", "unknown effect kept");
  const note = S.cancelNote(m);
  assert.ok(note && /Annulation demandée/.test(note));
  assert.doesNotMatch(note + S.missionLabel(m), /CANCELLED|sera annul|attendre/i);
});

test("G012-03: a cancellation on a running mission is labelled without promising the outcome", () => {
  const s = deliver(S.createState(), Object.assign(copy(D("cancel_requested_same_revision")), { status: "SNAPSHOT", events: [] }),
    { kind: "snapshot", epoch: 0, receivedAt: "t" });
  assert.equal(S.missionLabel(s.view.mission), "Annulation demandée — issue non confirmée");
  assert.doesNotMatch(S.cancelNote(s.view.mission), /CANCELLED/);
});
