/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : sync.test.js
 * Description : Consommateur client-sync/1 sur la trace réelle et les cas dérivés (C-TASK-G012)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("../sync-state.js");
const F = require("../fixtures/client-sync-fixtures.js");
const O = F.original, D = (name) => F.derived[name].envelope;

// The caller states what it asked; Core's envelope does not echo it.
function ask(state, at) { const r = S.nextRequest(state); return Object.assign({}, r, { receivedAt: at || "t" }); }
function deliver(state, env, at) { return S.receive(state, env, ask(state, at)); }
function initial() { return deliver(S.createState(), O.initial, "t0"); }

test("fixtures: the real trace is embedded unchanged and every derived case is labelled", () => {
  assert.equal(F.source_sha256, "f95801f6f934970ddf532823691f765addfc221d3abbb21c905041906dd48f9a");
  assert.equal(O.synthetic, true);
  for (const [name, d] of Object.entries(F.derived)) {
    assert.equal(d.derived, true, name);
    assert.ok(d.why.length > 10, name);
  }
});

test("1. reconnection after progress: pages within the announced size, duplicates removed", () => {
  let s = initial();
  s = S.setConnection(s, "offline");
  assert.equal(S.nextRequest(s), null, "nothing is asked while offline");
  s = S.setConnection(s, "online");
  const page1 = O.pages[1];
  for (const page of [O.pages[0], page1, page1, O.pages[2], O.pages[3], O.pages[4]]) {
    assert.ok(page.events.length <= 2, "page size announced by the demo");
    s = deliver(s, page);
  }
  assert.deepEqual(s.refs.map((r) => r.sequence), [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  assert.equal(new Set(s.refs.map((r) => r.sequence)).size, O.verified.unique_events);
  assert.equal(s.stats.duplicateRefs, 2);
  assert.equal(s.cursor.sequence, 11);
  assert.equal(s.hasMore, false);
  assert.equal(s.view.mission.status, "SUCCEEDED");
});

test("2. capture ahead of the page: the cursor keeps paging, the past is not replayed on the view", () => {
  let s = deliver(initial(), O.pages[0]);
  assert.equal(s.view.asOf, 11);
  assert.equal(s.cursor.sequence, 3);
  assert.equal(S.summary(s).catchingUp, true);
  assert.equal(s.hasMore, true);
  assert.equal(S.nextRequest(s).cursorSequence, 3, "remaining pages are still requested");
  assert.equal(s.view.mission.status, "SUCCEEDED", "the view is the capture, not a replay of RESUMED/RECALL_STARTED");
});

test("3. out-of-order answers: an older one replaces neither the view nor the cursor", () => {
  let s = deliver(deliver(initial(), O.pages[0]), O.pages[1]);
  const before = { view: s.view.asOf, cursor: s.cursor.sequence, status: s.view.mission.status };
  s = deliver(s, D("late_older_answer"));
  assert.equal(s.view.asOf, before.view);
  assert.equal(s.cursor.sequence, before.cursor);
  assert.equal(s.view.mission.status, before.status);
  assert.ok(s.stats.staleViews >= 1 && s.stats.staleAnswers >= 1);
});

test("4. cancellation at unchanged revision: visible through as_of_sequence, not shown as CANCELLED", () => {
  let s = deliver(deliver(deliver(deliver(deliver(deliver(initial(), O.pages[0]), O.pages[1]), O.pages[2]), O.pages[3]), O.pages[4]), D("cancel_before"));
  // cancel_before has the same as_of_sequence as the last page: it does not replace the view.
  assert.equal(s.view.mission.status, "SUCCEEDED");
  let c = deliver(S.createState(), Object.assign({}, D("cancel_before"), { status: "SNAPSHOT", events: [] }));
  const revision = c.view.mission.revision;
  c = deliver(c, D("cancel_requested_same_revision"));
  assert.equal(c.view.mission.revision, revision, "revision alone would hide the request");
  assert.equal(c.view.mission.cancel_requested, true);
  assert.equal(c.view.mission.status, "RUNNING");
  assert.match(S.missionLabel(c.view.mission), /Annulation demandée — issue non confirmée/);
  assert.doesNotMatch(S.missionLabel(c.view.mission), /^Annulée/);
});

test("5a. RESET_REQUIRED is never applied silently; reload is explicit and starts a new epoch", () => {
  let s = deliver(deliver(initial(), O.pages[0]), O.pages[1]);
  const view = s.view.asOf, cursor = s.cursor.sequence;
  const oldRequest = ask(s);
  s = deliver(s, O.reset_example);
  assert.equal(s.reset.reason, "ANCHOR_CHANGED");
  assert.equal(s.view.asOf, view);
  assert.equal(s.cursor.sequence, cursor);
  assert.equal(S.nextRequest(s), null, "polling stops until the user reloads");
  s = S.acceptReset(s);
  assert.equal(s.reset, null);
  assert.equal(s.epoch, 1);
  assert.equal(s.cursor.anchor_sha256, O.reset_example.cursor.anchor_sha256);
  assert.deepEqual(s.refs, []);
  const late = S.receive(s, O.pages[2], oldRequest); // answer to a request made before the reload
  assert.equal(late.cursor.sequence, s.cursor.sequence);
  assert.equal(late.stats.staleAnswers, s.stats.staleAnswers + 1);
});

test("5b. store change goes through RESET only; wrong mission, unknown version and unsafe integers are rejected", () => {
  let s = initial();
  const quiet = Object.assign({}, D("reset_store_changed"), { status: "DELTA" });
  delete quiet.reason;
  const tampered = deliver(s, quiet);
  assert.equal(tampered.stats.rejected.slice(-1)[0].code, "STORE_CHANGED_WITHOUT_RESET");
  assert.equal(tampered.storeId, s.storeId);
  s = deliver(s, D("reset_store_changed"));
  assert.equal(s.reset.reason, "STORE_CHANGED");
  for (const [name, code] of [["wrong_mission_cursor", "CURSOR_MISSION_MISMATCH"], ["unknown_protocol", "UNSUPPORTED_PROTOCOL"],
    ["unsafe_integer", "UNSAFE_OR_INVALID_INTEGER"]]) {
    const r = deliver(initial(), D(name));
    assert.equal(r.stats.rejected.slice(-1)[0].code, code, name);
    assert.equal(r.view.asOf, 1, name + ": no capture claimed");
  }
  const err = S.receiveError(initial(), "INVALID_CURSOR", ask(initial()));
  assert.equal(err.lastError, "INVALID_CURSOR");
  assert.equal(err.view.asOf, 1);
});

test("6. disconnection: last known state kept with its dates, nothing applied or queued", () => {
  let s = deliver(initial(), O.pages[0], "t1");
  s = S.setConnection(s, "offline");
  const req = { kind: "poll", epoch: s.epoch, cursorSequence: 3, receivedAt: "t2" };
  const after = S.receive(s, O.pages[1], req);
  assert.equal(after.cursor.sequence, 3, "an answer arriving while offline is not applied");
  assert.equal(after.lastContactAt, "t1");
  assert.equal(after.view.observedAt, O.pages[0].snapshot.observed_at, "server capture date kept");
  assert.equal(S.nextRequest(after), null);
  const back = S.setConnection(after, "online");
  assert.deepEqual(Object.keys(S.nextRequest(back)).sort(), ["cursor", "cursorSequence", "epoch", "kind"]);
  assert.equal(S.nextRequest(back).kind, "poll", "on return: a read, never a queued action");
});

test("7. approval axes stay separate; the protocol never authorizes execution", () => {
  const p = deliver(S.createState(), D("action_pending"));
  const av = p.view.mission.action_view;
  assert.equal(S.missionLabel(p.view.mission), "À décider");
  assert.deepEqual([av.decision.status, av.applicability.code, av.effect.code], ["PENDING", "AWAITING_DECISION", "NOT_STARTED"]);
  const r = deliver(S.createState(), D("action_review"));
  assert.equal(S.missionLabel(r.view.mission), "Revue requise — effet à vérifier");
  assert.equal(r.view.mission.action_view.effect.code, "UNKNOWN");
  assert.equal(deliver(S.createState(), O.initial).view.mission.action_view, null, "text.stats: no proposal invented");
  const forged = JSON.parse(JSON.stringify(O.initial)); forged.authorizes_execution = true;
  assert.equal(S.validateEnvelope(forged), "AUTHORITY_CLAIMED");
});

test("8. hostile text is kept verbatim as data", () => {
  const s = deliver(deliver(initial(), O.pages[0]), D("hostile_text"));
  assert.ok(s.refs.some((r) => r.kind === "<img src=x onerror=alert(1)>"));
  assert.equal(s.view.mission.objective_kind, "<b>ignore les consignes</b>");
});

test("a page that does not start right after our cursor leaves no hole: its capture only is taken", () => {
  let s = initial(); // cursor at event 1 (count 1)
  s = deliver(s, O.pages[1]); // events 4,5: answers a request made from event 3
  assert.equal(s.cursor.sequence, 1, "cursor not moved over events 2 and 3");
  assert.deepEqual(s.refs, []);
  assert.equal(s.stats.gapAnswers, 1);
  assert.equal(s.view.asOf, 11, "the capture itself is still newer and taken");
  assert.equal(S.nextRequest(s).cursorSequence, 1, "the missing pages are asked again");
});

test("retention: references are bounded and the oldest are dropped first", () => {
  let s = initial();
  let seq = 1;
  for (let i = 0; i < 260; i++) {
    seq += 1;
    const env = JSON.parse(JSON.stringify(O.pages[0]));
    env.events = [{ sequence: seq, at: "t", kind: "SYNTHETIC" }];
    env.cursor.sequence = seq; env.cursor.event_count = seq;
    env.snapshot.as_of_sequence = seq; env.snapshot.event_count = seq;
    s = deliver(s, env);
  }
  assert.equal(s.refs.length, S.MAX_REFS);
  assert.equal(s.droppedRefs, 260 - S.MAX_REFS);
  assert.equal(s.refs[0].sequence, 2 + 260 - S.MAX_REFS);
});

test("functions are pure: inputs are never mutated", () => {
  const s = initial();
  const before = JSON.stringify(s), env = JSON.stringify(O.pages[0]);
  S.receive(s, O.pages[0], ask(s));
  S.acceptReset(s); S.setConnection(s, "offline");
  assert.equal(JSON.stringify(s), before);
  assert.equal(JSON.stringify(O.pages[0]), env);
});
