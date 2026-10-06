/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : commands.test.js
 * Description : Suivi indépendant des commandes incertaines (C-TASK-G013)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: node --test "desktop/prototype/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../model.js");

const sent = (s, type) => s.client.outbox.filter((o) => !type || o.type === type);
const byKind = (s, kind) => s.client.commands.filter((x) => x.kind === kind);
function steps(s, n) { for (let i = 0; i < n; i++) s = M.serverStep(s); return s; }
function run(s, ...intents) { for (const i of intents) s = M.dispatch(s, typeof i === "string" ? { type: i } : i); return s; }

// Lost acknowledgement, reconnection and replay: the approval is APPROVED on the
// mission view but its own command is still unknown (the G013 starting point).
function uncertainApproval() {
  let s = steps(run(M.initialState("accuse-perdu"), "approve"), 1);
  s = steps(run(s, "sim-reconnect"), 1);
  assert.equal(s.client.mission.proposal.status, "APPROVED");
  assert.equal(byKind(s, "approve")[0].phase, "unknown");
  return s;
}

test("G013 reproduction inverted: revoke keeps the uncertain approval tracked and resolvable", () => {
  let s = uncertainApproval();
  const approveKey = byKind(s, "approve")[0].key;
  s = run(s, "revoke");
  assert.equal(s.client.commands.length, 2);
  assert.equal(byKind(s, "approve")[0].key, approveKey);
  assert.equal(byKind(s, "approve")[0].phase, "unknown");
  assert.equal(byKind(s, "revoke")[0].phase, "sending");
  s = steps(s, 1); // revoke acknowledged
  assert.equal(byKind(s, "revoke")[0].phase, "acknowledged");
  assert.equal(byKind(s, "approve")[0].phase, "unknown", "the revoke reply does not settle the approval");
  s = steps(run(s, { type: "check-receipt", key: approveKey }), 1);
  assert.equal(byKind(s, "approve")[0].phase, "acknowledged");
  assert.equal(byKind(s, "approve")[0].viaReceipt, true);
  assert.equal(sent(s, "DECIDE").length, 1, "the approval was never re-emitted");
  assert.deepEqual(s.client.decisionHistory.map((h) => h.kind).sort(), ["approve", "revoke"]);
});

test("G013: a cancellation request is allowed and tracked independently of the uncertain approval", () => {
  let s = uncertainApproval();
  s = run(s, "request-cancel");
  assert.equal(sent(s, "CANCEL_REQUEST").length, 1, "cancellation is not blocked by principle");
  s = steps(s, 1);
  assert.equal(byKind(s, "cancel")[0].phase, "acknowledged");
  assert.equal(byKind(s, "approve")[0].phase, "unknown");
  s = steps(run(s, "check-receipt"), 1); // without a key: the first uncertain command
  assert.equal(byKind(s, "approve")[0].phase, "acknowledged");
  assert.equal(sent(s, "DECIDE").length, 1);
});

test("G013: double click on revoke or cancel sends one request each", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 1);
  s = run(s, "revoke", "revoke");
  assert.equal(sent(s, "REVOKE").length, 1);
  assert.match(s.client.notice, /déjà en cours/);
  s = run(s, "request-cancel", "request-cancel");
  assert.equal(sent(s, "CANCEL_REQUEST").length, 1);
  assert.equal(s.client.commands.length, 3);
});

test("G013: no new decision while a previous one is unresolved, whatever the mission view shows", () => {
  let s = steps(run(M.initialState("accuse-perdu"), "approve"), 1);
  s = run(s, "sim-reconnect", "approve", "reject");
  assert.equal(sent(s, "DECIDE").length, 1);
  assert.match(M.decisionBlocker(s), /pas réconciliée/);
});

test("G013: out-of-order replies each settle their own command", () => {
  let s = steps(run(M.initialState("accord-succes"), "approve"), 1);
  s = run(s, "revoke", "request-cancel");
  const revokeKey = byKind(s, "revoke")[0].key, cancelKey = byKind(s, "cancel")[0].key;
  s = M.receiveReply(s, { type: "ACK", key: cancelKey, found: true, receipt: "r-cancel" });
  assert.equal(byKind(s, "cancel")[0].phase, "acknowledged");
  assert.equal(byKind(s, "revoke")[0].phase, "sending");
  s = M.receiveReply(s, { type: "ACK", key: revokeKey, found: true, receipt: "r-revoke" });
  assert.equal(byKind(s, "revoke")[0].receipt, "r-revoke");
  assert.equal(byKind(s, "cancel")[0].receipt, "r-cancel");
});

test("G013: duplicate and late replies never change a resolved command or the history", () => {
  let s = run(M.initialState("accord-succes"), "approve");
  const key = byKind(s, "approve")[0].key;
  s = M.receiveReply(s, { type: "ACK", key, found: true, receipt: "r-1" });
  const history = s.client.decisionHistory.length;
  s = M.receiveReply(s, { type: "RECEIPT", key, found: true, receipt: "r-1" });
  s = M.receiveReply(s, { type: "ACK", key, found: false }); // late contradicting reply
  assert.equal(byKind(s, "approve")[0].phase, "acknowledged");
  assert.equal(byKind(s, "approve")[0].receipt, "r-1");
  assert.equal(s.client.decisionHistory.length, history);
  assert.equal(s.client.duplicateReplies, 2);
});

test("G013: a reply for an unknown key is counted and changes nothing", () => {
  let s = run(M.initialState("accord-succes"), "approve");
  const before = JSON.stringify(s.client.commands);
  const outbox = sent(s).length;
  s = M.receiveReply(s, { type: "ACK", key: "k-never-sent", found: true, receipt: "r-x" });
  assert.equal(JSON.stringify(s.client.commands), before);
  assert.equal(s.client.strayReplies, 1);
  assert.equal(sent(s).length, outbox, "a reply never emits anything");
});

test("G013: receipt not found keeps the command uncertain and blocks re-emission", () => {
  let s = steps(run(M.initialState("accuse-perdu"), "approve"), 1);
  const key = byKind(s, "approve")[0].key;
  s = run(s, "sim-reconnect");
  s = M.receiveReply(s, { type: "RECEIPT", key, found: false });
  assert.equal(byKind(s, "approve")[0].phase, "not-found");
  assert.match(M.commandLabel(byKind(s, "approve")[0]), /pas la preuve/);
  s = run(s, "approve");
  assert.equal(sent(s, "DECIDE").length, 1);
  s = run(s, { type: "check-receipt", key });
  assert.equal(sent(s, "RECEIPT_QUERY").length, 1, "the receipt can be queried again");
});

test("G013: a server refusal is a definitive answer for that key only", () => {
  let s = run(M.initialState("accord-succes"), "approve");
  s.sim.mission.revision += 1; // the proposal changed on the server meanwhile
  s = steps(s, 1);
  assert.equal(byKind(s, "approve")[0].phase, "refused");
  assert.equal(M.unresolvedCommands(s).length, 0);
});

test("G013: disconnection turns sending and checking into unknown, never into a resend", () => {
  let s = steps(run(M.initialState("accuse-perdu"), "approve"), 1);
  s = run(s, "sim-reconnect", "check-receipt");
  assert.equal(byKind(s, "approve")[0].phase, "checking");
  s = run(s, "sim-disconnect");
  assert.equal(byKind(s, "approve")[0].phase, "unknown");
  assert.equal(sent(s, "DECIDE").length, 1);
});

test("G013 retention: unresolved commands are never purged, resolved ones are bounded", () => {
  let s = run(M.initialState("accord-succes"), "approve"); // stays unresolved below
  const keep = byKind(s, "approve")[0].key;
  for (let i = 0; i < 25; i++) {
    s.client.commands.push({ kind: "cancel", key: "synthetic-" + i, phase: "sending", receipt: null,
      viaReceipt: false, sentMinute: 0, resolvedMinute: null });
    s = M.receiveReply(s, { type: "ACK", key: "synthetic-" + i, found: true, receipt: "r-" + i });
  }
  const resolved = s.client.commands.filter((x) => !M.unresolvedCommands(s).includes(x));
  assert.ok(s.client.commands.some((x) => x.key === keep && x.phase === "sending"));
  assert.equal(resolved.length, M.MAX_RESOLVED_COMMANDS);
  assert.equal(resolved[0].key, "synthetic-15", "the oldest resolved ones go first");
  s = M.receiveReply(s, { type: "ACK", key: "synthetic-0", found: true, receipt: "r-0" });
  assert.equal(s.client.strayReplies, 1, "a reply for a purged command is counted, not applied");
});

test("G012 eye: an uncertain command shows « Reçu à vérifier », below offline, microphone and silence", () => {
  let s = uncertainApproval();
  s = run(s, "revoke"); s = steps(s, 1); // mission view REVOKED, approval still unknown
  assert.equal(M.eye(s).label, "Reçu à vérifier");
  assert.equal(M.eye(s).mode, "attention");
  assert.equal(M.eye(run(s, "toggle-silence")).mode, "silence");
  assert.equal(M.eye(run(s, "sim-mic")).mode, "listen");
  assert.equal(M.eye(run(s, "sim-disconnect")).mode, "offline");
  const outbox = sent(s).length;
  assert.equal(sent(run(s, "toggle-silence", "close-window")).length, outbox, "no resend, no decision");
  s = steps(run(s, "check-receipt"), 1);
  assert.notEqual(M.eye(s).label, "Reçu à vérifier");
});
