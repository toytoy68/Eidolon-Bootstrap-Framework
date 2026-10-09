/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : conversation.test.js
 * Description : État de l'accueil conversationnel sur transport scripté : clé, envois, soumission, étapes (C-TASK-G088)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path");
const C = require("../src/conversation.js");

const KEY = "ecc_" + "A".repeat(43);
const EXAMPLES = path.resolve(__dirname, "..", "..", "..", "docs", "examples", "conversation");
const reply = JSON.parse(fs.readFileSync(path.join(EXAMPLES, "03-reply-proposal.json"), "utf8"));

function scripted(answers, recent) {
  const calls = [];
  const transport = async (method, p, body, token) => {
    if (p.endsWith("/recent")) return { status: 200, json: { conversations: recent || [] } };   // G092, not scripted
    calls.push({ method, path: p, body, token });
    const next = answers.shift();
    if (next instanceof Error) throw next;
    return typeof next === "function" ? next(body) : next;
  };
  return { calls, transport };
}
const ok = (json) => ({ status: 200, json });
const opened = ok({ conversation_id: "c-" + "2".repeat(32), client_id: "pc-exemple", actor: "toytoy", store_id: reply.store_id });
const turnReply = (r) => ok({ turn: {}, reply: r, replayed: false, model_called: true });

test("the canonical digest matches Core's published proposal digest", async () => {
  assert.equal(await C.digest(reply.proposal), reply.proposal_sha256);
});

test("a malformed key is refused locally and the key never appears in the state", async () => {
  const s = scripted([opened]);
  const conv = C.createConversation({ transport: s.transport });
  assert.equal(await conv.open("pas-une-cle"), false);
  assert.equal(s.calls.length, 0);
  assert.equal(await conv.open(KEY), true);
  assert.equal(s.calls[0].token, KEY);
  assert.ok(!JSON.stringify(conv.state()).includes(KEY));
  assert.deepEqual(conv.state().identity, { clientId: "pc-exemple", actor: "toytoy", storeId: reply.store_id });
});

test("read token refused by the server keeps the conversation closed", async () => {
  const s = scripted([{ status: 403, json: { error: "READ_TOKEN_NOT_ALLOWED" } }]);
  const conv = C.createConversation({ transport: s.transport });
  assert.equal(await conv.open(KEY), false);
  assert.deepEqual([conv.state().phase, conv.state().error], ["closed", "READ_TOKEN_NOT_ALLOWED"]);
});

test("a lost answer is uncertain and is resent with the SAME key; a 4xx is a refusal", async () => {
  const s = scripted([opened, new Error("network"), turnReply(reply), { status: 409, json: { error: "TURN_KEY_REUSED" } }]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  assert.equal(await conv.send("Peux-tu vérifier l'état du NAS ?"), false);
  const item = conv.state().items[0];
  assert.equal(item.status, "uncertain");
  assert.equal(await conv.send(null, item.key), true);
  assert.equal(s.calls[2].body.client_turn_key, s.calls[1].body.client_turn_key);
  assert.equal(conv.state().items[0].status, "received");
  assert.equal(conv.state().proposal.request, reply.proposal.request);
  assert.equal(await conv.send("autre"), false);
  assert.equal(conv.state().items[1].status, "refused");
});

test("submission sends the locally verified digest and identity; a tampered proposal is never sent", async () => {
  const s = scripted([opened, turnReply(reply),
    (body) => ok({ status: "MISSION_CREATED", mission_id: "m-" + "4".repeat(32), command_key: body.command_key })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY); await conv.send("Peux-tu vérifier l'état du NAS ?");
  assert.equal(await conv.submit(" "), false);                         // a reason is required
  assert.equal(await conv.submit("Diagnostic demandé"), true);
  const body = s.calls[2].body;
  assert.equal(body.proposal_sha256, reply.proposal_sha256);
  assert.deepEqual([body.client_id, body.actor, body.proposal_version], ["pc-exemple", "toytoy", 1]);
  assert.equal(conv.state().submission.status, "recorded");

  const t = scripted([opened, turnReply({ ...reply, proposal_sha256: "0".repeat(64) })]);
  const other = C.createConversation({ transport: t.transport });
  await other.open(KEY); await other.send("Peux-tu vérifier l'état du NAS ?");
  assert.equal(await other.submit("Diagnostic demandé"), false);
  assert.deepEqual([other.state().submission.status, other.state().submission.error], ["refused", "DIGEST_MISMATCH"]);
  assert.equal(t.calls.length, 2);                                      // nothing was submitted
});

test("an uncertain submission is resolved by its receipt, never by a new key", async () => {
  const s = scripted([opened, turnReply(reply), new Error("network"),
    ok({ status: "FOUND", receipt: { status: "MISSION_CREATED", mission_id: "m-" + "4".repeat(32) } })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY); await conv.send("Peux-tu vérifier l'état du NAS ?");
  assert.equal(await conv.submit("Diagnostic demandé"), false);
  assert.equal(conv.state().submission.status, "uncertain");
  assert.equal(await conv.checkReceipt(), true);
  assert.equal(s.calls[3].body.command_key, s.calls[2].body.command_key);
  assert.equal(conv.state().submission.status, "recorded");
});

test("answers that arrive after closing are ignored", async () => {
  let release;
  const s = scripted([opened, () => new Promise((r) => { release = () => r(turnReply(reply)); })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  const pending = conv.send("Peux-tu vérifier l'état du NAS ?");
  await new Promise((r) => setImmediate(r));
  conv.close();
  release();
  assert.equal(await pending, false);
  assert.deepEqual([conv.state().phase, conv.state().items.length], ["closed", 0]);
});

test("mission stages: created, running, result, unknown effect, never invented", () => {
  const sub = (receipt) => ({ receipt });
  const created = { status: "MISSION_CREATED", mission_id: "m-" + "4".repeat(32) };
  assert.equal(C.missionView(sub(created), null).stage, "created");
  assert.equal(C.missionView(sub(created), "RUNNING").stage, "running");
  assert.equal(C.missionView(sub(created), "SUCCEEDED").stage, "result");
  assert.equal(C.missionView(sub(created), "REVIEW_REQUIRED").stage, "unknown_effect");
  assert.equal(C.missionView(sub(created), "NOUVEAU_STATUT").text, "Statut reçu : NOUVEAU_STATUT");
  assert.equal(C.missionView(sub({ status: "MISSION_CREATION_UNCERTAIN", mission_id: null }), null).stage, "unknown_effect");
  assert.equal(C.missionView({ receipt: null }, null), null);
});

test("G091: a partial context is said in words; a complete one says nothing", () => {
  const base = { history_sent: 20, history_excluded: 0, memory: "sent", memory_items: 1, memory_truncated_items: 0, partial: false };
  assert.equal(C.contextNote(base), null);
  assert.equal(C.contextNote(null), null);
  assert.equal(C.contextNote({ ...base, history_excluded: 10, partial: true }),
    "Contexte partiel : 10 échanges plus anciens non transmis au modèle.");
  assert.equal(C.contextNote({ ...base, history_excluded: 1, memory: "dropped_for_budget", memory_items: 0, partial: true }),
    "Contexte partiel : 1 échange plus ancien non transmis au modèle ; mémoire non transmise (taille).");
  assert.equal(C.contextNote({ ...base, memory_truncated_items: 1, partial: true }),
    "Contexte partiel : 1 extrait(s) de mémoire déjà tronqué(s).");
  assert.equal(C.contextNote({ ...base, memory: "unavailable", memory_items: 0, partial: true }),
    "Contexte partiel : mémoire indisponible.");
});

test("G092: resuming reads the conversation back, marks unanswered turns pending and resends nothing", async () => {
  const id = "c-" + "9".repeat(32);
  const items = [
    { turn: { client_turn_key: "turn-a", text: "Bonjour" }, reply: { kind: "ANSWER", model_text: "Salut" } },
    { turn: { client_turn_key: "turn-b", text: "Diagnostique le nas." }, reply },
    { turn: { client_turn_key: "turn-c", text: "Et après ?" }, reply: null }];
  const s = scripted([opened, ok({ items, has_more: false, next_after: 3 })],
    [{ conversation_id: id, turn_count: 3, last_turn_at: "2026-10-09T10:00:00" }]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  assert.deepEqual(conv.state().recent.map((c) => c.conversation_id), [id]);
  assert.equal(await conv.resume("c-" + "0".repeat(32)), false);       // not offered: not resumed
  assert.equal(await conv.resume(id), true);
  const st = conv.state();
  assert.deepEqual(st.items.map((i) => i.status), ["received", "received", "pending"]);
  assert.equal(st.proposal.request, reply.proposal.request);
  assert.equal(st.submission, null);
  assert.deepEqual(s.calls.map((c) => c.path.split("/").pop()), ["open", "page"]);   // read only
  assert.equal(s.calls[1].body.conversation_id, id);
});
