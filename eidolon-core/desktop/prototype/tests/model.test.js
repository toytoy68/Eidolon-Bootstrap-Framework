/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : model.test.js
 * Description : Transitions du prototype bureau : effets visibles et absence d'envoi indu
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../model.js");

const sent = (s, type) => s.client.outbox.filter((o) => !type || o.type === type);
const cmd = (s, kind) => s.client.commands.filter((x) => !kind || x.kind === kind).slice(-1)[0];
function steps(s, n) { for (let i = 0; i < n; i++) s = M.serverStep(s); return s; }
function run(s, ...intents) { for (const i of intents) s = M.dispatch(s, typeof i === "string" ? { type: i } : i); return s; }

test("approve sends one request and changes nothing before the acknowledgement", () => {
  let s = run(M.initialState("accord-succes"), "approve");
  assert.equal(sent(s, "DECIDE").length, 1);
  assert.equal(cmd(s).phase, "sending");
  assert.equal(s.client.mission.proposal.status, "PENDING");
  assert.match(M.commandLabel(cmd(s)), /envoi en cours/);
  assert.equal(M.eye(s).mode, "attention");
  s = run(s, "approve");
  assert.equal(sent(s, "DECIDE").length, 1, "no second emission while one is in flight");
});

test("recorded approval is not execution; execution and verified result are later, distinct events", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 1);
  assert.equal(s.client.mission.proposal.status, "APPROVED");
  assert.equal(s.client.mission.status, "BLOCKED");
  assert.equal(s.client.mission.effect, "NOT_STARTED");
  assert.notEqual(M.eye(s).mode, "work");
  assert.equal(M.missionLabel(s.client.mission).text, "Bloquée — accord enregistré");
  s = steps(s, 1);
  assert.equal(s.client.mission.status, "RUNNING");
  assert.equal(s.client.mission.proposal.status, "USED");
  assert.equal(M.eye(s).mode, "work");
  s = steps(s, 1);
  const m = s.client.mission;
  assert.equal(m.status, "SUCCEEDED");
  assert.equal(m.outcome, "ACHIEVED");
  assert.equal(m.effect, "VERIFIED_PAST_EFFECT");
  const verification = m.evidence.find((e) => e.kind === "verification");
  assert.ok(verification && /^[0-9a-f]{64}$/.test(verification.sha256));
  assert.match(M.syntheticTime(verification.minute), /^2026-10-05T/);
});

test("refusal never leads to work or execution", () => {
  let s = steps(run(M.initialState("refus"), "reject"), 6);
  assert.equal(s.client.mission.proposal.status, "REJECTED");
  assert.equal(s.client.mission.status, "BLOCKED");
  assert.equal(s.sim.mission.status, "BLOCKED");
  assert.notEqual(M.eye(s).mode, "work");
  assert.deepEqual(sent(s).map((o) => o.type), ["DECIDE"]);
});

test("offline: nothing is sent or queued, drafts stay local", () => {
  let s = run(M.initialState("accord-succes"), "sim-disconnect", "approve", "reject",
    { type: "draft", text: "brouillon" }, "send-chat", "open-reading",
    { type: "reading-text", text: "texte" }, { type: "reading-reviewed", value: true }, "reading-send");
  assert.deepEqual(sent(s), []);
  assert.equal(s.client.draft, "brouillon");
  assert.match(s.client.notice, /Hors ligne/);
  s = steps(s, 3);
  assert.deepEqual(sent(s), [], "no deferred send appears later");
  assert.equal(M.eye(s).mode, "offline");
});

test("lost acknowledgement: unknown decision, replay without duplicate, receipt before any new emission", () => {
  let s = steps(run(M.initialState("accuse-perdu"), "approve"), 1);
  assert.equal(s.client.connection, "offline");
  assert.equal(cmd(s).phase, "unknown");
  assert.equal(s.sim.mission.proposal.status, "APPROVED", "Core recorded it");
  assert.equal(s.client.mission.proposal.status, "PENDING", "the client does not know yet");
  s = run(s, "sim-reconnect", "approve");
  assert.equal(sent(s, "DECIDE").length, 1, "no re-emission while the receipt is unknown");
  s = steps(s, 1); // SYNC with a deliberate duplicate
  assert.ok(s.client.duplicatesIgnored >= 1);
  assert.equal(new Set(s.client.seen).size, s.client.seen.length);
  assert.equal(s.client.mission.proposal.status, "APPROVED");
  assert.equal(cmd(s).phase, "unknown", "a shared event is not this client's receipt");
  s = steps(run(s, "check-receipt"), 1);
  assert.equal(cmd(s).phase, "acknowledged");
  assert.equal(cmd(s).viaReceipt, true);
  assert.equal(sent(s, "DECIDE").length, 1);
  s = steps(s, 2);
  assert.equal(s.client.mission.status, "SUCCEEDED");
  assert.equal(s.client.mission.id, "m-0042");
});

test("a consumed approval cannot be undone; revocation and cancellation are separate requests", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 2); // RUNNING, USED
  s = run(s, "revoke");
  assert.equal(sent(s, "REVOKE").length, 0);
  assert.match(s.client.notice, /consommé/);
  s = run(s, "request-cancel");
  assert.equal(sent(s, "CANCEL_REQUEST").length, 1);
  assert.equal(s.client.mission.cancelRequested, false, "unchanged until Core answers");
});

test("revoking a recorded approval prevents execution", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 1);
  s = run(s, "revoke");
  assert.equal(sent(s, "REVOKE").length, 1);
  assert.equal(s.client.mission.proposal.status, "APPROVED", "unchanged until Core answers");
  s = steps(s, 4);
  assert.equal(s.client.mission.proposal.status, "REVOKED");
  assert.equal(s.sim.mission.status, "BLOCKED");
  assert.notEqual(M.eye(s).mode, "work");
});

test("cancellation request before execution closes the mission without running it", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 1);
  s = steps(run(s, "request-cancel"), 1);
  assert.equal(s.client.mission.cancelRequested, true);
  assert.equal(M.missionLabel(s.client.mission).text, "Annulation demandée");
  s = steps(s, 3);
  assert.equal(s.client.mission.status, "CANCELLED");
  assert.ok(!s.sim.log.some((e) => e.type === "MISSION_RUNNING"));
});

test("review required: no automatic retry and no decision offered", () => {
  let s = M.initialState("revue-requise");
  assert.equal(M.missionLabel(s.client.mission).text, "Revue requise — effet à vérifier");
  assert.equal(M.eye(s).mode, "attention");
  s = steps(run(s, "approve", { type: "retry" }), 5);
  assert.deepEqual(sent(s), []);
  assert.equal(s.client.mission.status, "REVIEW_REQUIRED");
  assert.equal(s.client.mission.effect, "UNKNOWN");
});

test("offline endpoint view: last known state is dated, nothing claimed about now", () => {
  const s = M.initialState("hors-ligne");
  assert.equal(M.eye(s).mode, "offline");
  assert.match(M.eye(s).detail, /14:00 UTC \(synthétique\)/);
  assert.ok(M.indicators(s).some((i) => i.id === "connection" && i.tone === "warn"));
  assert.equal(M.nextServerStep(s), "Aucun événement ne peut atteindre ce client (hors ligne).");
});

test("locked session: generic notification, no decision through toast, silence or closing", () => {
  let s = M.initialState("session-verrouillee");
  const text = M.toastText(s, s.client.toasts[0]);
  assert.ok(!/svc-demo|Redémarrer/.test(text.body + text.title), "no mission detail on a locked screen");
  s = run(s, "open-decision");
  assert.match(s.client.notice, /Déverrouille/);
  assert.equal(s.client.windowOpen, false);
  s = run(s, "approve");
  assert.match(s.client.notice, /Session verrouillée/);
  s = run(s, "toggle-silence", "close-window");
  assert.deepEqual(sent(s), []);
  s = run(s, "sim-lock", "toggle-silence", "open-decision");
  assert.equal(s.client.windowOpen, true);
  assert.equal(s.client.tab, "missions");
  assert.deepEqual(sent(s), [], "opening the decision decides nothing");
});

test("local microphone stays signalled while Core is unreachable", () => {
  const s = M.initialState("micro-hors-ligne");
  assert.equal(M.eye(s).mode, "offline");
  const mic = M.indicators(s).find((i) => i.id === "mic");
  assert.ok(mic && mic.tone === "alert");
});

test("closing the window decides and cancels nothing", () => {
  const s = run(M.initialState("accord-succes"), "close-window");
  assert.equal(s.client.windowOpen, false);
  assert.deepEqual(sent(s), []);
  assert.equal(s.client.mission.proposal.status, "PENDING");
});

test("a sequence gap asks for a snapshot instead of guessing", () => {
  const s = M.initialState("accord-succes");
  M.applyEvent(s, { seq: 5, type: "MISSION_RUNNING", minute: 1, data: { revision: 9 } });
  assert.equal(s.client.mission.status, "BLOCKED");
  assert.equal(s.client.snapshotRequested, true);
  assert.equal(sent(s, "SNAPSHOT_REQUEST").length, 1);
});

test("a decision on a changed proposal is reported as not recorded", () => {
  let s = run(M.initialState("accord-succes"), "approve");
  s.sim.mission.revision += 1; // someone else changed the mission meanwhile
  s = steps(s, 1);
  assert.equal(cmd(s).phase, "refused");
  assert.equal(s.sim.mission.proposal.status, "PENDING");
});

test("assisted reading sends exactly the reviewed text, and any edit requires a new review", () => {
  let s = run(M.initialState("accord-succes"), "open-reading", { type: "reading-text", text: "Ligne A" },
    { type: "reading-reviewed", value: true }, { type: "reading-text", text: "Ligne A modifiée" }, "reading-send");
  assert.equal(sent(s, "READ_SUBMIT").length, 0);
  s = run(s, { type: "reading-reviewed", value: true }, "reading-send");
  const submit = sent(s, "READ_SUBMIT");
  assert.equal(submit.length, 1);
  assert.equal(submit[0].text, "Ligne A modifiée");
  assert.equal(submit[0].provenance, "fourni par l'utilisateur");
});

test("model functions are pure: the input state is never mutated", () => {
  const s = M.initialState("accord-succes");
  const before = JSON.stringify(s);
  M.dispatch(s, { type: "approve" });
  M.serverStep(s);
  assert.equal(JSON.stringify(s), before);
});
