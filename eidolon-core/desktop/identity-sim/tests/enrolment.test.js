/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : enrolment.test.js
 * Description : Parcours simulés G170-E : consentement, prises, arrêt, effacement, réenregistrement, suggestions sans droit
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../enrolment.js");

// Invented profiles only.
const PROFILES = [{ profile_id: "profil-alpha", display_name: "Alpha", confirmed: true },
  { profile_id: "profil-beta", display_name: "Beta", confirmed: true },
  { profile_id: "profil-gamma", display_name: "Gamma", confirmed: false }];

function run(state, actions) {
  return actions.reduce((s, a) => { const n = S.act(s, a); assert.equal(n.flow.error, undefined, JSON.stringify(a) + " " + n.flow.error); return n; }, state);
}
const OK_VOICE = { type: "finish", sample: { duration_s: 6, quality: "ok" } };
const OK_FACE = { type: "finish", sample: { quality: "ok" } };
const take = (ok) => [{ type: "start" }, ok];

function enrolled(modality) {
  const ok = modality === "voice" ? OK_VOICE : OK_FACE;
  return run(S.create(PROFILES), [{ type: "begin", profile_id: "profil-alpha", modality },
    { type: "consent", present: true, agree: true }, ...take(ok), ...take(ok), ...take(ok), { type: "confirm" }]);
}

test("full voice enrolment: consent, three takes, review, confirm; no right, no sample kept", () => {
  const state = enrolled("voice");
  assert.equal(state.profiles[0].voice, "enrolled");
  assert.equal(state.flow.step, "idle");
  assert.match(S.view(state).text, /Aucun droit/);
  assert.deepEqual(state.log, [{ event: "enrolled", modality: "voice", discarded: 3 }]);
  assert.deepEqual([state.simulated, state.grants], [true, []]);
  assert.equal(JSON.stringify(state).includes("audio"), false);
});

test("only a confirmed profile can be enrolled, and consent needs presence AND agreement", () => {
  const s = S.create(PROFILES);
  assert.equal(S.act(s, { type: "begin", profile_id: "profil-gamma", modality: "voice" }).flow.error, "PROFILE_NOT_CONFIRMED");
  assert.equal(S.act(s, { type: "begin", profile_id: "inconnu", modality: "voice" }).flow.error, "PROFILE_UNKNOWN");
  assert.equal(S.act(s, { type: "begin", profile_id: "profil-alpha", modality: "iris" }).flow.error, "MODALITY_UNKNOWN");
  const c = S.act(s, { type: "begin", profile_id: "profil-alpha", modality: "face" });
  assert.equal(S.act(c, { type: "consent", present: true }).flow.error, "CONSENT_INCOMPLETE");
  assert.equal(S.act(c, { type: "start" }).flow.error, "NOT_READY");               // no capture before consent
});

test("the capture indicator is on only while capturing, and stop is always offered", () => {
  let s = run(S.create(PROFILES), [{ type: "begin", profile_id: "profil-alpha", modality: "face" },
    { type: "consent", present: true, agree: true }]);
  assert.deepEqual([S.view(s).indicator, S.view(s).stop_available], [false, true]);
  s = S.act(s, { type: "start" });
  assert.deepEqual([S.view(s).indicator, S.view(s).title], [true, "Caméra active (simulation)"]);
  assert.ok(S.view(s).actions.includes("stop"));
  s = S.act(s, OK_FACE);
  assert.equal(S.view(s).indicator, false);
});

test("stop during a capture wipes the session's takes and enrols nothing", () => {
  const s = run(S.create(PROFILES), [{ type: "begin", profile_id: "profil-alpha", modality: "voice" },
    { type: "consent", present: true, agree: true }, ...take(OK_VOICE), { type: "start" }, { type: "stop" }]);
  assert.equal(s.profiles[0].voice, "not_enrolled");
  assert.deepEqual(s.log, [{ event: "cancelled", modality: "voice", discarded: 1 }]);
  assert.match(S.view(s).text, /effacées/);
});

test("bad takes ask to retry without counting; voice must last 5 to 8 seconds", () => {
  let s = run(S.create(PROFILES), [{ type: "begin", profile_id: "profil-alpha", modality: "voice" },
    { type: "consent", present: true, agree: true }]);
  for (const [sample, why] of [[{ duration_s: 3 }, "too_short"], [{ duration_s: 12 }, "too_long"],
    [{ quality: "silence" }, "silence"], [{ quality: "several_people" }, "several_people"], [{}, "too_short"]]) {
    s = S.act(S.act(s, { type: "start" }), { type: "finish", sample });
    assert.deepEqual([s.flow.step, s.flow.retry, s.flow.samples.length], ["ready", why, 0]);
  }
  assert.match(S.view(s).text, /^Prise trop courte/);
  assert.equal(S.act(S.act(s, { type: "start" }), { type: "finish", sample: { quality: "no_face" } }).flow.error,
    "QUALITY_NOT_FOR_MODALITY");
  s = S.act(S.act(s, { type: "start" }), OK_VOICE);
  assert.deepEqual([s.flow.samples.length, s.flow.retry], [1, undefined]);
});

test("delete needs a confirmation; cancel keeps it; re-enrolment is possible after delete only", () => {
  let s = enrolled("face");
  assert.equal(S.act(s, { type: "begin", profile_id: "profil-alpha", modality: "face" }).flow.error,
    "ALREADY_ENROLLED_DELETE_FIRST");
  s = S.act(s, { type: "ask_delete", profile_id: "profil-alpha", modality: "face" });
  const kept = S.act(s, { type: "cancel" });
  assert.deepEqual([kept.profiles[0].face, S.view(kept).text], ["enrolled", "Effacement annulé : rien n'a changé."]);
  s = S.act(s, { type: "delete" });
  assert.equal(s.profiles[0].face, "not_enrolled");
  assert.equal(S.act(s, { type: "ask_delete", profile_id: "profil-alpha", modality: "face" }).flow.error, "NOTHING_TO_DELETE");
  assert.equal(S.act(s, { type: "begin", profile_id: "profil-alpha", modality: "face" }).flow.step, "consent");
});

test("a refused action never changes the state", () => {
  const s = enrolled("voice");
  for (const action of [{ type: "confirm" }, { type: "delete" }, { type: "finish" }, { type: "nope" }, { type: "cancel" }]) {
    const n = S.act(s, action);
    assert.ok(n.flow.error);
    assert.deepEqual(n.profiles, s.profiles);
    assert.deepEqual(n.log, s.log);
  }
});

const proposal = (extra) => Object.assign({ schema: "eidolon-identity-proposal/1", modality: "voice", state: "known",
  profile_id: "profil-alpha", grants: [], authorizes_execution: false }, extra);

test("a recognition is a suggestion only; profile switch stays the manual connection", () => {
  const v = S.proposalView(proposal(), PROFILES);
  assert.equal(v.suggestion, "Alpha");
  assert.match(v.text, /non vérifié.*connexion manuelle/);
  assert.deepEqual([v.grants, v.switch_profile], [[], "manual_connection_only"]);
  const fused = S.proposalView(proposal({ modality: "fused", basis: ["face", "voice"] }), PROFILES);
  assert.match(fused.text, /visage et voix/);
});

test("uncalibrated, ambiguous, stale and unavailable never name anyone", () => {
  for (const state of ["uncalibrated", "ambiguous", "stale", "unavailable", "unknown", "several_people"]) {
    const v = S.proposalView(proposal({ state, profile_id: null,
      candidates: [{ profile_id: "profil-alpha", score: 0.9 }] }), PROFILES);
    assert.equal(v.suggestion, null);
    assert.equal(/Alpha|Beta|profil-/.test(v.text), false, state);
  }
});

test("a proposal carrying a right, an unconfirmed or unknown profile is ignored", () => {
  assert.equal(S.proposalView(proposal({ grants: ["admin"] }), PROFILES).suggestion, null);
  assert.equal(S.proposalView(proposal({ authorizes_execution: true }), PROFILES).suggestion, null);
  assert.equal(S.proposalView(proposal({ profile_id: "profil-gamma" }), PROFILES).suggestion, null);
  assert.equal(S.proposalView(proposal({ profile_id: "intrus" }), PROFILES).suggestion, null);
  assert.equal(S.proposalView(proposal({ schema: "autre/1" }), PROFILES).suggestion, null);
  assert.equal(S.proposalView(null, PROFILES).suggestion, null);
});
