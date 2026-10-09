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

test("G098: each reply names its profile and model; a change is said; nothing is invented", () => {
  const a = { model: { profile: "local-a", model_id: "dialogue/m-a@0123" } };
  const b = { model: { profile: "local-b", model_id: "dialogue/m-b@4567" } };
  assert.equal(C.modelLabel(a, null), "Modèle : profil « local-a », dialogue/m-a@0123");
  assert.equal(C.modelLabel(b, a), "Modèle : profil « local-b », dialogue/m-b@4567 — profil changé depuis la réponse précédente");
  assert.equal(C.modelLabel(a, a), "Modèle : profil « local-a », dialogue/m-a@0123");
  assert.equal(C.modelLabel({ model: { profile: "local-b", model_id: null } }, null), "Modèle : profil « local-b » (non chargé)");
  assert.equal(C.modelLabel({ model: { profile: null, model_id: null } }, null), "Modèle : aucun");
  assert.equal(C.modelLabel({ model: { profile: null, model_id: "simulated" } }, null), "Modèle : simulated");
  assert.equal(C.modelLabel({}, null), null);                         // older replies: nothing guessed
  assert.match(C.NOTES.DIALOGUE_PROFILE_UNAVAILABLE, /aucun autre n'est pris à sa place/);
});

test("G101: media results are plain text lines; wrong job, partial, copied reference, HTML", () => {
  const out = { artifact_id: "ma-1", display_name: "<b>sortie</b>.png", media_type: "image/png", verification: "hash_verified",
    provenance: { job_id: "media-1", node_id: "9", output_index: 0, collection_id: "mc-2" } };
  const view = { stage: "unknown_effect", state_received: "COLLECTION_INCOMPLETE", binding: "MATCHED",
    source: { artifact_id: "ma-0", verification: "unavailable" }, outputs: [out], excluded_outputs: 1,
    collection: { state: "COLLECTION_INCOMPLETE", expected: 3, imported: 1, partial: true },
    observation: { text: '<img src=x onerror="alert(1)">', verified: false } };
  const text = C.mediaResultLines(view).map((l) => l.text);
  assert.deepEqual(text.slice(0, 3), ["Effet inconnu : revue nécessaire (COLLECTION_INCOMPLETE)",
    "Fichier source ma-0 : indisponible", "Collecte partielle : 1 sur 3 fichier(s) importé(s)."]);
  assert.match(text[3], /^<b>sortie<\/b>\.png — image\/png — empreinte vérifiée ; contenu non vérifié ; travail media-1/);
  assert.match(text[4], /1 référence\(s\) sans lien avec ce travail/);
  assert.equal(text[5], 'Observation du modèle, non vérifiée : <img src=x onerror="alert(1)">');
  assert.match(text[6], /non disponible/);
  assert.ok(!text.some((t) => /succès|réussi|terminé avec succès/i.test(t)));
  assert.deepEqual(C.mediaResultLines({ stage: "result_unverified", state_received: "X", binding: "WRONG_JOB", outputs: [out] })
    .map((l) => l.text)[1], "Ce résultat appartient à un autre travail : il n'est pas affiché.");
  const made = [];
  const doc = { createElement: (tag) => { const e = { tag, children: [], appendChild(c) { this.children.push(c); } }; made.push(e); return e; } };
  const box = { textContent: "x", children: [], appendChild(c) { this.children.push(c); } };
  C.renderMediaResult(doc, box, view);
  assert.ok(made.every((e) => e.tag === "p" && !("innerHTML" in e)));           // text only, never a button
  assert.equal(box.children[5].textContent, text[5]);
});

const MID = "m-" + "4".repeat(32), OTHER = "m-" + "5".repeat(32);
const cancelProposal = { protocol: "eidolon-cancel-proposal/1", store_id: reply.store_id, conversation_id: "c-" + "2".repeat(32),
  client_id: "pc-exemple", mission_id: MID, mission_request_sha256: "a".repeat(64), link_sha256: "b".repeat(64),
  action: "REQUEST_MISSION_STOP", engine_interrupt: "NEVER", requires_human_submission: true,
  authorizes_execution: false, success_claim: "ONLY_FROM_MISSION_STATUS_CANCELLED" };

test("G100: two active missions ask which one; the request names the exact mission and digest; never 'cancelled' early", async () => {
  const sha = await C.digest(cancelProposal);
  const s = scripted([opened,
    ok({ kind: "CLARIFICATION", code: "MISSION_AMBIGUOUS", candidates: [MID, OTHER, "pas-un-id"] }),
    ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: sha, mission_status: "RUNNING" }),
    ok({ status: "RECORDED", cancel_outcome: "REQUESTED", stage: "request_received", mission_status: "RUNNING" }),
    ok({ status: "FOUND", receipt: { cancel_outcome: "REQUESTED" }, stage: "effect_observed", mission_status: "CANCELLED" })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  await conv.cancelPropose();
  assert.deepEqual([conv.state().cancel.status, conv.state().cancel.candidates], ["choose", [MID, OTHER]]);
  assert.equal(await conv.cancelPropose("pas-un-id"), false);              // only ids offered by Core
  await conv.cancelPropose(MID);
  assert.equal(conv.state().cancel.status, "review");
  assert.equal(await conv.cancelSubmit(" "), false);                       // a reason is required
  assert.equal(await conv.cancelSubmit("plus utile"), true);
  const body = s.calls[3].body;
  assert.deepEqual([body.mission_id, body.proposal_sha256, body.conversation_id], [MID, sha, "c-" + "2".repeat(32)]);
  assert.equal(C.cancelStatusText(conv.state().cancel), "Demande d'arrêt enregistrée — arrêt non confirmé.");
  await conv.cancelCheck();
  assert.equal(s.calls[4].body.command_key, body.command_key);
  assert.equal(C.cancelStatusText(conv.state().cancel), "Arrêt confirmé : la mission est annulée.");
});

test("G100: a tampered proposal is never sent; a lost answer is checked, then resent with the SAME key", async () => {
  const t = scripted([opened, ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: "0".repeat(64), mission_status: "NEW" })]);
  const bad = C.createConversation({ transport: t.transport });
  await bad.open(KEY); await bad.cancelPropose(MID);
  assert.deepEqual([bad.state().cancel.status, bad.state().cancel.error], ["error", "DIGEST_MISMATCH"]);
  assert.equal(await bad.cancelSubmit("x"), false);
  assert.equal(t.calls.length, 2);

  const sha = await C.digest(cancelProposal);
  const s = scripted([opened, ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: sha, mission_status: "NEW" }),
    new Error("network"), ok({ status: "NOT_FOUND", receipt: null, stage: "uncertain", mission_status: "NEW" }),
    ok({ status: "RECORDED", cancel_outcome: "REQUESTED", stage: "request_received", mission_status: "NEW" })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY); await conv.cancelPropose(MID);
  assert.equal(await conv.cancelSubmit("plus utile"), false);
  assert.equal(conv.state().cancel.status, "uncertain");
  assert.equal(await conv.cancelSubmit("plus utile"), false);              // no blind resend while uncertain
  await conv.cancelCheck();
  assert.equal(conv.state().cancel.status, "not_recorded");
  assert.equal(await conv.cancelSubmit("plus utile"), true);
  assert.equal(s.calls[4].body.command_key, s.calls[2].body.command_key);
});

test("G100: finished missions and media jobs are said, nothing is offered", async () => {
  const s = scripted([opened, ok({ kind: "REFUSED", code: "MISSION_ALREADY_FINISHED" }),
    ok({ kind: "CLARIFICATION", code: "NO_ACTIVE_MISSION", candidates: [] })]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  await conv.cancelPropose(MID);
  assert.equal(C.cancelStatusText(conv.state().cancel), "Cette mission est déjà terminée : rien à arrêter.");
  await conv.cancelPropose();
  assert.equal(C.cancelStatusText(conv.state().cancel), "Aucune mission en cours créée depuis cette conversation.");
  assert.equal(conv.state().cancel.proposal, null);
});

test("G101: media results are read on demand, errors are said, closing forgets them", async () => {
  const view = { agent: "image", operation: "edit", stage: "result_unverified", state_received: "OUTPUTS_IMPORTED_UNVERIFIED",
    binding: "MATCHED", outputs: [], excluded_outputs: 0 };
  const s = scripted([opened, ok({ results: [view] }), { status: 503, json: { error: "CONVERSATION_UNAVAILABLE" } }]);
  const conv = C.createConversation({ transport: s.transport });
  await conv.open(KEY);
  assert.equal(conv.state().media, null);                                     // nothing read before asked
  await conv.loadMedia();
  assert.deepEqual([conv.state().media.status, conv.state().media.results.length], ["ready", 1]);
  assert.equal(s.calls[1].path.split("/").pop(), "media_results");
  await conv.loadMedia();
  assert.deepEqual([conv.state().media.status, conv.state().media.error], ["error", "CONVERSATION_UNAVAILABLE"]);
  conv.close();
  assert.equal(conv.state().media, null);
});


function deferredResponse() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}
async function preparedCancellation(answers, recent) {
  const sha = await C.digest(cancelProposal);
  const script = scripted([opened, ok({ kind: "PROPOSAL", proposal: cancelProposal,
    proposal_sha256: sha, mission_status: "RUNNING" }), ...answers], recent);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.cancelPropose(MID);
  return { conv, script };
}

test("G124-R1: a late cancellation of A cannot confirm the newly selected B", async () => {
  const late = deferredResponse(), p2 = { ...cancelProposal, mission_id: OTHER };
  const { conv, script } = await preparedCancellation([() => late.promise,
    ok({ kind: "PROPOSAL", proposal: p2, proposal_sha256: await C.digest(p2), mission_status: "RUNNING" })]);
  const pending = conv.cancelSubmit("Arrêter A");
  await conv.cancelPropose(OTHER);
  const before = conv.state().cancel;
  late.resolve(ok({ mission_id: MID, stage: "effect_observed", mission_status: "CANCELLED" }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().cancel, before);
  assert.equal(conv.state().cancel.proposal.mission_id, OTHER);
  assert.equal(script.calls.filter((c) => c.path.endsWith("/cancel")).length, 1);
  assert.ok(!C.cancelStatusText(conv.state().cancel).includes("Arrêt confirmé"));
});

test("G124-R1: a late error cannot erase a new review, even for the same mission", async () => {
  const late = deferredResponse();
  const { conv } = await preparedCancellation([() => late.promise,
    ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: await C.digest(cancelProposal), mission_status: "RUNNING" })]);
  const pending = conv.cancelSubmit("première sélection");
  await conv.cancelPropose(MID);
  const before = conv.state().cancel;
  late.resolve({ status: 503, json: { error: "STATE_BUSY" } });
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().cancel, before);
});

test("G124-R1: cancellation proposals arriving out of order keep the latest selection", async () => {
  const late = deferredResponse(), p2 = { ...cancelProposal, mission_id: OTHER };
  const script = scripted([opened, () => late.promise,
    ok({ kind: "PROPOSAL", proposal: p2, proposal_sha256: await C.digest(p2), mission_status: "RUNNING" })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.cancelPropose(MID);
  await conv.cancelPropose(OTHER);
  const before = conv.state().cancel;
  late.resolve(ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: await C.digest(cancelProposal),
    mission_status: "RUNNING" }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().cancel, before);
});

test("G124-R1: a hashed proposal for another requested mission is refused", async () => {
  const { conv } = await preparedCancellation([
    ok({ kind: "PROPOSAL", proposal: cancelProposal, proposal_sha256: await C.digest(cancelProposal), mission_status: "RUNNING" })]);
  assert.equal(await conv.cancelPropose(OTHER), false);
  assert.equal(conv.state().cancel.error, "DIGEST_MISMATCH");
  assert.equal(await conv.cancelSubmit("ne rien envoyer"), false);
});

test("G124-R1: receipt lookup from A cannot rewrite a review of B", async () => {
  const late = deferredResponse(), p2 = { ...cancelProposal, mission_id: OTHER };
  const { conv } = await preparedCancellation([new Error("lost"), () => late.promise,
    ok({ kind: "PROPOSAL", proposal: p2, proposal_sha256: await C.digest(p2), mission_status: "RUNNING" })]);
  await conv.cancelSubmit("arrêt");
  const pending = conv.cancelCheck();
  await conv.cancelPropose(OTHER);
  const before = conv.state().cancel;
  late.resolve(ok({ status: "FOUND", receipt: { mission_id: MID }, stage: "effect_observed", mission_status: "CANCELLED" }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().cancel, before);
});

test("G124-R1: receipt queries cannot race the initial submission", async () => {
  const late = deferredResponse();
  const { conv, script } = await preparedCancellation([() => late.promise]);
  const pending = conv.cancelSubmit("arrêt");
  assert.equal(await conv.cancelCheck(), false);
  assert.equal(script.calls.filter((c) => c.path.endsWith("/cancel_receipt")).length, 0);
  late.resolve(ok({ stage: "request_received", mission_status: "RUNNING" }));
  await pending;
});

test("G124-R1: older NOT_FOUND cannot undo a newer confirmed receipt", async () => {
  const late = deferredResponse();
  const { conv } = await preparedCancellation([new Error("lost"), () => late.promise,
    ok({ status: "FOUND", receipt: { mission_id: MID }, stage: "effect_observed", mission_status: "CANCELLED" })]);
  await conv.cancelSubmit("arrêt");
  const pending = conv.cancelCheck();
  await conv.cancelCheck();
  const before = conv.state().cancel;
  late.resolve(ok({ status: "NOT_FOUND", receipt: null, mission_status: "RUNNING" }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().cancel, before);
  assert.equal(await conv.cancelSubmit("pas de deuxième arrêt"), false);
});

test("G124-R1: unknown receipt status and disappearance of a known receipt never permit resend", async () => {
  for (const known of [false, true]) {
    const { conv, script } = await preparedCancellation([
      known ? ok({ stage: "request_received", mission_status: "RUNNING" }) : new Error("lost"),
      ok({ status: known ? "NOT_FOUND" : "UNRECOGNIZED", receipt: null, mission_status: "RUNNING" })]);
    await conv.cancelSubmit("arrêt");
    assert.equal(await conv.cancelCheck(), false);
    assert.equal(conv.state().cancel.status, "uncertain");
    assert.equal(await conv.cancelSubmit("pas de renvoi"), false);
    assert.equal(script.calls.filter((c) => c.path.endsWith("/cancel")).length, 1);
  }
});

test("G124-R1: an explicit resend keeps the entire original command including its reason", async () => {
  const { conv, script } = await preparedCancellation([new Error("lost"),
    ok({ status: "NOT_FOUND", receipt: null, mission_status: "RUNNING" }),
    ok({ stage: "request_received", mission_status: "RUNNING" })]);
  await conv.cancelSubmit("motif original");
  await conv.cancelCheck();
  assert.equal(await conv.cancelSubmit("motif changé pendant la coupure"), true);
  const sent = script.calls.filter((c) => c.path.endsWith("/cancel"));
  assert.deepEqual(sent[1].body, sent[0].body);
});

test("G124-R1: closing and resuming discard outstanding cancellation responses", async () => {
  for (const resume of [false, true]) {
    const late = deferredResponse(), cid = "c-" + "9".repeat(32);
    const { conv } = await preparedCancellation([() => late.promise,
      ok({ items: [], has_more: false, next_after: 0 })], [{ conversation_id: cid, turn_count: 0 }]);
    const pending = conv.cancelSubmit("arrêt");
    if (resume) await conv.resume(cid); else conv.close();
    late.resolve(ok({ mission_id: MID, stage: "effect_observed", mission_status: "CANCELLED" }));
    assert.equal(await pending, false);
    assert.equal(conv.state().cancel, null);
  }
});

test("G123: an older media refresh cannot replace the latest view", async () => {
  const late = deferredResponse(), script = scripted([opened, () => late.promise, ok({ results: [{ job_id: "new" }] })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.loadMedia();
  await conv.loadMedia();
  const before = conv.state().media;
  late.resolve(ok({ results: [{ job_id: "old" }] }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().media, before);
});

test("G125: busy storage is explained without converting uncertainty into absence or retrying", async () => {
  for (const code of ["STATE_BUSY", "CONVERSATION_STORE_BUSY", "CREDENTIALS_BUSY", "BUSY"]) {
    const { conv, script } = await preparedCancellation([{ status: 503, json: { error: code } }]);
    await conv.cancelSubmit("arrêt");
    assert.equal(conv.state().cancel.status, "uncertain");
    assert.match(C.cancelStatusText(conv.state().cancel), /occupé/);
    assert.match(C.cancelStatusText(conv.state().cancel), /reçu avant tout renvoi/);
    assert.equal(script.calls.filter((c) => c.path.endsWith("/cancel")).length, 1);
    assert.equal(await conv.cancelSubmit("pas de nouvel envoi"), false);
  }
  for (const code of ["CONVERSATION_UNAVAILABLE", "STORE_CHANGED", "CREDENTIALS_MISSING"]) {
    assert.equal(C.busyNote(code), null);
  }
});

test("G125: a busy receipt read retains the old receipt without claiming a fresh confirmation", async () => {
  const { conv, script } = await preparedCancellation([
    ok({ stage: "request_received", mission_status: "RUNNING" }),
    { status: 503, json: { error: "STATE_BUSY" } }]);
  await conv.cancelSubmit("arrêt");
  const before = conv.state().cancel.receipt;
  assert.equal(await conv.cancelCheck(), false);
  assert.deepEqual(conv.state().cancel.receipt, before);
  assert.match(C.cancelStatusText(conv.state().cancel), /n’a pas pu être vérifié/);
  assert.equal(script.calls.filter((c) => c.path.endsWith("/cancel")).length, 1);
});

function nextMissionReply() {
  const proposal = { ...reply.proposal, version: 2, request: "nouvelle demande synthétique" };
  return C.digest(proposal).then(sha => ({ ...reply, proposal, proposal_sha256: sha }));
}

test("C069: a delayed mission submission cannot become the new proposal's receipt", async () => {
  const late = deferredResponse(), newer = await nextMissionReply();
  const script = scripted([opened, turnReply(reply), () => late.promise, turnReply(newer),
    body => ok({ status: "MISSION_CREATED", mission_id: OTHER, command_key: body.command_key })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("première demande");
  const pending = conv.submit("première validation");
  await new Promise(resolve => setImmediate(resolve));
  await conv.send("nouvelle demande");
  await conv.submit("nouvelle validation");
  const before = conv.state();
  late.resolve(ok({ status: "MISSION_CREATED", mission_id: MID }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state(), before);
  assert.equal(conv.state().submission.receipt.mission_id, OTHER);
});

test("C069: closing during the asynchronous digest sends no mission command", async () => {
  const script = scripted([opened, turnReply(reply)]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("demande");
  const pending = conv.submit("motif");
  conv.close();
  assert.equal(await pending, false);
  assert.equal(script.calls.filter(c => c.path.endsWith("/submit")).length, 0);
  assert.equal(conv.state().phase, "closed");
  assert.equal(conv.state().submission, null);
});

test("C069: rapid duplicate validation emits only one submission", async () => {
  const late = deferredResponse(), script = scripted([opened, turnReply(reply), () => late.promise,
    () => { throw Error("duplicate command"); }]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("demande");
  const first = conv.submit("motif"), second = conv.submit("motif");
  await new Promise(resolve => setImmediate(resolve));
  late.resolve(ok({ status: "MISSION_CREATED", mission_id: MID }));
  assert.deepEqual(await Promise.all([first, second]), [true, false]);
  assert.equal(script.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  assert.equal(await conv.submit("encore"), false);
  assert.equal(script.calls.filter(c => c.path.endsWith("/submit")).length, 1);
});

test("C069: a late receipt lookup cannot overwrite a newer mission submission", async () => {
  const late = deferredResponse(), newer = await nextMissionReply();
  const script = scripted([opened, turnReply(reply), new Error("lost"), () => late.promise,
    turnReply(newer), body => ok({ status: "MISSION_CREATED", mission_id: OTHER, command_key: body.command_key })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("première demande"); await conv.submit("motif");
  const pending = conv.checkReceipt();
  await conv.send("nouvelle demande"); await conv.submit("motif 2");
  const before = conv.state().submission;
  late.resolve(ok({ status: "FOUND", receipt: { status: "MISSION_CREATED", mission_id: MID } }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().submission, before);
});

test("C069: an old mission receipt lookup cannot downgrade a more recent FOUND", async () => {
  const late = deferredResponse(), script = scripted([opened, turnReply(reply), new Error("lost"),
    () => late.promise, ok({ status: "FOUND", receipt: { status: "MISSION_CREATED", mission_id: MID } })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("demande"); await conv.submit("motif");
  const pending = conv.checkReceipt();
  await conv.checkReceipt();
  const before = conv.state().submission;
  late.resolve(ok({ status: "NOT_FOUND", receipt: null }));
  assert.equal(await pending, false);
  assert.deepEqual(conv.state().submission, before);
});

test("C069: switching conversations ignores the previous conversation's late turn", async () => {
  const late = deferredResponse(), cid = "c-" + "9".repeat(32);
  const script = scripted([opened, () => late.promise, ok({ items: [], has_more: false, next_after: 0 })],
    [{ conversation_id: cid, turn_count: 0 }]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.send("ancienne conversation");
  await conv.resume(cid);
  late.resolve(turnReply(reply));
  assert.equal(await pending, false);
  assert.equal(conv.state().conversationId, cid);
  assert.equal(conv.state().items.length, 0);
});

test("C069: concurrent conversation resumes keep the last requested conversation", async () => {
  const late = deferredResponse(), ca = "c-" + "8".repeat(32), cb = "c-" + "9".repeat(32);
  const script = scripted([opened, () => late.promise, ok({ items: [], has_more: false, next_after: 0 })],
    [{ conversation_id: ca, turn_count: 0 }, { conversation_id: cb, turn_count: 0 }]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.resume(ca);
  await conv.resume(cb);
  late.resolve(ok({ items: [], has_more: false, next_after: 0 }));
  assert.equal(await pending, false);
  assert.equal(conv.state().conversationId, cb);
});

test("C069: a malformed replacement key closes the previous session and drops its response", async () => {
  const late = deferredResponse(), script = scripted([opened, () => late.promise]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.send("demande");
  assert.equal(await conv.open("invalid"), false);
  late.resolve(turnReply(reply));
  assert.equal(await pending, false);
  assert.equal(conv.state().phase, "closed");
  assert.equal(conv.state().proposal, null);
  assert.equal(conv.state().items.length, 0);
});

test("C069: out-of-order turn answers do not replace a newer proposal or erase its receipt", async () => {
  const late = deferredResponse(), newer = await nextMissionReply();
  const script = scripted([opened, () => late.promise, turnReply(newer),
    ok({ status: "MISSION_CREATED", mission_id: OTHER })]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY);
  const pending = conv.send("première demande");
  await conv.send("deuxième demande"); await conv.submit("validation de la deuxième");
  const before = conv.state().submission;
  late.resolve(turnReply(reply)); await pending;
  assert.equal(conv.state().proposal.version, 2);
  assert.deepEqual(conv.state().submission, before);
});

test("C069: a receipt check during submission sends no concurrent lookup", async () => {
  const late = deferredResponse(), script = scripted([opened, turnReply(reply), () => late.promise]);
  const conv = C.createConversation({ transport: script.transport });
  await conv.open(KEY); await conv.send("demande");
  const pending = conv.submit("validation");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(await conv.checkReceipt(), false);
  late.resolve(ok({ status: "MISSION_CREATED", mission_id: MID })); await pending;
  assert.equal(script.calls.filter(c => c.path.endsWith("/receipt")).length, 0);
});
