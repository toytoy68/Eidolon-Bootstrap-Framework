/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : conversation.js
 * Description : Accueil conversationnel : tours, réponses, proposition, soumission et suivi de mission (C-TASK-G088)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// The conversation key (ecc_…) lives in this closure only, like the read token: never in the DOM,
// storage or a cookie. Without an accepted key there is no command control on the page at all.
// Displayed states are those recorded by Core; nothing here simulates progress or success.
(function (root) {
  "use strict";
  var PREFIX = "/v1/conversations/";
  var KEY = /^ecc_[A-Za-z0-9_-]{43}$/;
  var MISSION = /^m-[0-9a-f]{32}$/;
  // Mission status → stage shown to the user. Unknown statuses are shown as received.
  var STAGES = { NEW: "created", RUNNING: "running", BLOCKED: "running", SUCCEEDED: "result",
    FAILED: "result", CANCELLED: "result", ABANDONED: "result", REVIEW_REQUIRED: "unknown_effect" };
  var LABELS = {
    draft: "Brouillon", sent: "Envoyé — en attente de la réponse", received: "Reçu",
    uncertain: "Envoi incertain — renvoyer ne crée pas de doublon", refused: "Refusé",
    pending: "Réponse en préparation par une autre tentative — vérifier à nouveau",
    created: "Mission créée — pas encore lancée", running: "En cours", result: "Résultat disponible",
    unknown_effect: "Effet inconnu — voir les preuves, ne pas relancer"
  };
  // Core's reasons in plain French; an unknown code is shown as received.
  var NOTES = {
    TARGET_AMBIGUOUS: "Plusieurs services correspondent : précisez lequel.",
    TARGET_ABSENT: "Ce service n'est pas dans le catalogue : précisez le service.",
    PARAMETERS_INVALID: "La demande est incomplète : précisez-la.",
    TEMPLATE_UNSUPPORTED: "Cette action ne fait pas partie de ce que la conversation peut proposer.",
    CAPABILITY_ABSENT: "Ce service ne permet pas cette action.",
    MODEL_DECLINED: "Le modèle indique que la demande sort de ses capacités.",
    MODEL_UNAVAILABLE: "Le modèle n'a pas répondu : rien n'a été deviné.",
    MODEL_OUTPUT_INVALID: "La réponse du modèle était illisible : rien n'a été deviné.",
    MODEL_TIMEOUT: "Le modèle n'a pas répondu dans le délai : une réponse tardive est ignorée.",
    MODEL_ATTEMPT_INTERRUPTED: "La tentative de réponse a été interrompue : elle n'est pas relancée. Renvoyez le message si besoin.",
    DIALOGUE_PROFILE_NOT_SELECTED: "Aucun modèle de dialogue n'est choisi sur le serveur : aucun autre n'est pris à sa place.",
    DIALOGUE_PROFILE_UNAVAILABLE: "Le modèle de dialogue choisi n'est pas disponible : aucun autre n'est pris à sa place."
  };
  // G098: which profile and model produced this reply; a change from the previous reply is said in words.
  function modelLabel(reply, previous) {
    var m = reply && reply.model;
    if (!m || typeof m !== "object") return null;
    var name = m.profile ? "profil « " + m.profile + " »" : null;
    var text = "Modèle : " + [name, m.model_id].filter(Boolean).join(", ") + (m.model_id ? "" : " (non chargé)");
    if (!name && !m.model_id) text = "Modèle : aucun";
    var before = previous && previous.model;
    if (before && typeof before === "object" && before.profile !== m.profile && m.profile) text += " — profil changé depuis la réponse précédente";
    return text;
  }
  // G100: what a cancellation may say. Only the mission itself confirms a stop.
  var CANCEL_STAGES = {
    request_received: "Demande d'arrêt enregistrée — arrêt non confirmé.",
    effect_observed: "Arrêt confirmé : la mission est annulée.",
    finished_without_cancellation: "La mission s'est terminée avant l'arrêt : son résultat est conservé.",
    already_finished: "La mission était déjà terminée : rien n'a été arrêté.",
    uncertain: "État incertain — vérifier, ne pas renvoyer à l'aveugle." };
  var CANCEL_CODES = {
    NO_ACTIVE_MISSION: "Aucune mission en cours créée depuis cette conversation.",
    MISSION_AMBIGUOUS: "Plusieurs missions sont en cours : choisissez celle à arrêter.",
    MISSION_ALREADY_FINISHED: "Cette mission est déjà terminée : rien à arrêter.",
    MEDIA_CANCEL_NOT_AVAILABLE: "L'arrêt d'une tâche image ou vidéo n'est pas disponible.",
    MISSION_UNKNOWN: "Mission inconnue pour cette conversation.",
    PROPOSAL_CHANGED: "La proposition d'arrêt a changé : redemandez-la avant de confirmer.",
    DIGEST_MISMATCH: "La proposition affichée ne correspond pas à celle figée par Core : rien n'a été envoyé." };
  var FINAL_STAGES = ["effect_observed", "finished_without_cancellation", "already_finished"];
  // Submission refusals worth explaining in words (others are shown with their code).
  var SUBMIT_ERRORS = {
    PROPOSAL_ALREADY_SUBMITTED: "Cette proposition a déjà été validée (peut-être avant une reprise) : voir les missions.",
    PROPOSAL_STALE: "Une version plus récente de la proposition existe : relisez-la avant de valider.",
    PROPOSAL_CHANGED: "La proposition a changé : relisez-la avant de valider.",
    DIGEST_MISMATCH: "La proposition affichée ne correspond pas à celle figée par Core : rien n'a été envoyé."
  };
  var REPLY_KINDS = { ANSWER: "Réponse", CLARIFICATION: "Question en retour", PROPOSAL: "Proposition de mission",
    OUT_OF_SCOPE: "Hors capacités", UNAVAILABLE: "Indisponible" };

  function randomKey(prefix) {
    var bytes = new Uint8Array(8);
    (root.crypto || require("node:crypto").webcrypto).getRandomValues(bytes);
    return prefix + "-" + Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
  }

  // Same canonical JSON as Core's contracts.digest (sorted keys, no spaces, UTF-8): the page checks
  // that what it shows is exactly what Core froze before letting anyone submit it.
  function canonical(v) {
    if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
    if (v !== null && typeof v === "object") {
      return "{" + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ":" + canonical(v[k]); }).join(",") + "}";
    }
    return JSON.stringify(v);
  }

  function digest(value) {
    var subtle = (root.crypto || require("node:crypto").webcrypto).subtle;
    return subtle.digest("SHA-256", new TextEncoder().encode(canonical(value))).then(function (buf) {
      return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    });
  }

  // G091 presentation rule: a partial context is always said, in words, before the sources.
  function contextNote(context) {
    if (!context || !context.partial) return null;
    var parts = [];
    if (context.history_excluded > 0) {
      parts.push(context.history_excluded + (context.history_excluded > 1 ? " échanges plus anciens non transmis au modèle"
        : " échange plus ancien non transmis au modèle"));
    }
    if (context.memory === "dropped_for_budget") parts.push("mémoire non transmise (taille)");
    if (context.memory === "unavailable") parts.push("mémoire indisponible");
    if (context.memory_truncated_items > 0) parts.push(context.memory_truncated_items + " extrait(s) de mémoire déjà tronqué(s)");
    return parts.length ? "Contexte partiel : " + parts.join(" ; ") + "." : null;
  }

  function busyNote(code) {
    if (code === "BUSY") return "Serveur occupé : réessayez explicitement plus tard.";
    if (["STATE_BUSY", "CONVERSATION_STORE_BUSY", "CREDENTIALS_BUSY"].indexOf(code) >= 0) {
      return "Stockage occupé : réessayez explicitement plus tard.";
    }
    return null;
  }

  function stageOf(status) { return Object.prototype.hasOwnProperty.call(STAGES, status) ? STAGES[status] : null; }

  function createConversation(options) {
    var transport = options.transport, onChange = options.onChange || function () {};
    var token = null, epoch = 0, cancelRead = 0, submissionRead = 0, resumeRead = 0;
    var state = { phase: "closed", error: null, conversationId: null, identity: null, items: [],
      proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, media: null };

    function emit() { onChange(JSON.parse(JSON.stringify(state))); }
    function errorOf(res) { return res && res.json && typeof res.json.error === "string" ? res.json.error : "NETWORK"; }

    async function call(route, body) {
      var mine = epoch;
      var res;
      try { res = await transport("POST", PREFIX + route, body, token); } catch (err) { res = null; }
      if (mine !== epoch) return { stale: true };                       // closed or reopened meanwhile
      if (!res) return { ok: false, network: true, code: "NETWORK" };
      if (res.status === 200 && res.json && typeof res.json === "object") return { ok: true, json: res.json };
      return { ok: false, network: false, code: errorOf(res), status: res.status };
    }

    async function open(key) {
      if (typeof key !== "string" || !KEY.test(key)) {
        close(); state.error = "KEY_FORMAT"; emit(); return false;
      }
      epoch += 1; token = key;
      state = { phase: "opening", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, media: null };
      emit();
      var r = await call("open", { client_key: randomKey("page") });
      if (r.stale) return false;
      if (!r.ok) { token = null; state.phase = "closed"; state.error = r.code; emit(); return false; }
      state.phase = "open";
      state.conversationId = r.json.conversation_id;
      state.identity = { clientId: r.json.client_id, actor: r.json.actor, storeId: r.json.store_id };
      state.recent = [];
      emit();
      var rec = await call("recent", { limit: 5 });
      if (!rec.stale && rec.ok && Array.isArray(rec.json.conversations)) {
        state.recent = rec.json.conversations.filter(function (c) { return c.conversation_id !== state.conversationId; });
        emit();
      }
      return true;
    }

    // G092: resume a previous conversation after a reload. Only reads; nothing is resent. A turn
    // without a reply becomes "pending": checking it reuses ITS key, so Core replays, never duplicates.
    async function resume(conversationId) {
      if (state.phase !== "open" || !state.recent.some(function (c) { return c.conversation_id === conversationId; })) return false;
      var mine = epoch, read = ++resumeRead;
      var items = [], after = 0;
      for (var i = 0; i < 20; i++) {
        var r = await call("page", { conversation_id: conversationId, after: after, limit: 50 });
        if (r.stale || mine !== epoch || read !== resumeRead) return false;
        if (!r.ok) { state.error = r.code; emit(); return false; }
        r.json.items.forEach(function (it) {
          items.push({ key: it.turn.client_turn_key, text: it.turn.text, reply: it.reply, error: null,
            status: it.reply ? "received" : "pending" });
        });
        after = r.json.next_after;
        if (!r.json.has_more) break;
      }
      var last = items.filter(function (it) { return it.reply && it.reply.kind === "PROPOSAL"; }).pop();
      epoch += 1;                                       // outstanding requests belong to the previous conversation
      state.conversationId = conversationId;
      state.items = items;
      state.proposal = last ? last.reply.proposal : null;
      state.proposalSha = last ? last.reply.proposal_sha256 : null;
      state.submission = null;                            // unknown after a reload: never assumed, never resent
      state.cancel = null; state.media = null;
      state.recent = state.recent.filter(function (c) { return c.conversation_id !== conversationId; });
      state.resumed = true;
      emit();
      return true;
    }

    function close() {
      epoch += 1; token = null;
      state = { phase: "closed", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, media: null };
      emit();
    }

    async function send(text, retryKey) {
      if (state.phase !== "open") return false;
      var item;
      if (retryKey) {
        item = state.items.filter(function (i) { return i.key === retryKey; })[0];
        if (!item || (item.status !== "uncertain" && item.status !== "pending")) return false;
      } else {
        if (typeof text !== "string" || !text.trim() || text.length > 8000) return false;
        item = { key: randomKey("turn"), text: text, status: "draft", reply: null, error: null };
        state.items.push(item);
      }
      var mine = epoch, conversationId = state.conversationId;
      item.status = "sent"; emit();
      var r = await call("turn", { conversation_id: conversationId, client_turn_key: item.key, text: item.text });
      if (r.stale || mine !== epoch || state.conversationId !== conversationId || state.items.indexOf(item) < 0) return false;
      if (r.ok && r.json.pending) {
        item.status = "pending";                          // another attempt owns this turn (G090-R1)
      } else if (r.ok) {
        item.status = "received"; item.reply = r.json.reply;
        if (r.json.reply && r.json.reply.kind === "PROPOSAL") {
          var latest = state.items.filter(function (i) { return i.reply && i.reply.kind === "PROPOSAL"; }).pop().reply;
          if (state.proposalSha !== latest.proposal_sha256) {
            state.proposal = latest.proposal; state.proposalSha = latest.proposal_sha256; state.submission = null;
          }
        }
      } else {
        // A lost answer may still have been recorded: same key again is safe (Core replays the turn).
        item.status = r.network || r.status >= 500 ? "uncertain" : "refused";
        item.error = r.code;
      }
      emit();
      return r.ok;
    }

    async function submit(reason) {
      if (state.phase !== "open" || !state.proposal || !state.identity) return false;
      if (typeof reason !== "string" || !reason.trim() || reason.length > 4000) return false;
      if (state.submission && (state.submission.status === "sent" || state.submission.status === "recorded")) return false;
      var p = state.proposal, sha = state.proposalSha, mine = epoch, identity = state.identity;
      var local = await digest(p);
      if (mine !== epoch || p !== state.proposal || identity !== state.identity || sha !== state.proposalSha) return false;
      if (state.submission && (state.submission.status === "sent" || state.submission.status === "recorded")) return false;
      if (local !== sha) {                  // shown ≠ frozen: never submitted
        state.submission = { key: null, proposalVersion: p.version, reason: reason, status: "refused",
          receipt: null, error: "DIGEST_MISMATCH" };
        emit();
        return false;
      }
      if (!state.submission || state.submission.proposalVersion !== p.version || state.submission.status === "refused") {
        state.submission = { key: randomKey("submit"), proposalVersion: p.version, reason: reason.trim(),
          status: "draft", receipt: null, error: null };
      }
      var s = state.submission, read = ++submissionRead;
      s.status = "sent"; emit();
      var body = { protocol: "eidolon-proposal-submission/1", store_id: p.store_id, client_id: state.identity.clientId,
        command_key: s.key, conversation_id: p.conversation_id, proposal_id: p.proposal_id,
        proposal_version: p.version, proposal_sha256: local, actor: state.identity.actor, reason: s.reason };
      var r = await call("submit", body);
      if (r.stale || mine !== epoch || s !== state.submission || read !== submissionRead) return false;
      if (r.ok) { s.status = "recorded"; s.receipt = r.json; s.error = null; }
      else { s.status = r.network || r.status >= 500 ? "uncertain" : "refused"; s.error = r.code; }
      emit();
      return r.ok;
    }

    // ---- G100: targeted cancellation (proposal → human confirmation → request, never a confirmed stop)
    async function cancelPropose(missionId) {
      if (state.phase !== "open") return false;
      var body = { conversation_id: state.conversationId };
      if (missionId !== undefined && missionId !== null) {
        if (!MISSION.test(missionId)) return false;
        body.mission_id = missionId;
      }
      var mine = epoch, read = ++cancelRead;
      var c = state.cancel = { status: "loading", proposal: null, sha: null, missionStatus: null, candidates: [], code: null,
        key: null, receipt: null, stage: null, error: null };
      emit();
      var r = await call("cancel_proposal", body);
      if (r.stale || c !== state.cancel || read !== cancelRead) return false;
      if (!r.ok) { c.status = "error"; c.error = r.code; emit(); return false; }
      if (r.json.kind === "PROPOSAL") {
        var local = await digest(r.json.proposal);
        if (mine !== epoch || c !== state.cancel || read !== cancelRead) return false;
        if (local !== r.json.proposal_sha256 || !MISSION.test(r.json.proposal.mission_id)
            || (body.mission_id && body.mission_id !== r.json.proposal.mission_id)) {
          c.status = "error"; c.error = "DIGEST_MISMATCH"; emit(); return false;
        }
        c.status = "review"; c.proposal = r.json.proposal; c.sha = local; c.missionStatus = r.json.mission_status;
      } else if (r.json.kind === "CLARIFICATION") {
        c.code = r.json.code;
        c.candidates = (r.json.candidates || []).filter(function (m) { return MISSION.test(m); });
        c.status = c.candidates.length ? "choose" : "unavailable";
      } else {
        c.status = "unavailable"; c.code = r.json.code || null;
      }
      emit();
      return true;
    }

    async function cancelSubmit(reason) {
      var c = state.cancel;
      if (state.phase !== "open" || !c || !c.proposal || (c.status !== "review" && c.status !== "not_recorded")) return false;
      if (typeof reason !== "string" || !reason.trim() || reason.length > 4000) return false;
      if (!c.key) {
        c.key = randomKey("cancel");
        c.reason = reason.trim();                       // one key always keeps the same command body
      }
      var read = ++cancelRead;
      c.status = "sent"; c.error = null; emit();
      var r = await call("cancel", { command_key: c.key, conversation_id: state.conversationId,
        mission_id: c.proposal.mission_id, proposal_sha256: c.sha, reason: c.reason });
      if (r.stale || c !== state.cancel || read !== cancelRead) return false;
      if (r.ok) { c.status = "recorded"; c.receipt = r.json; c.stage = r.json.stage; c.missionStatus = r.json.mission_status; }
      else { c.status = r.network || r.status >= 500 ? "uncertain" : "refused"; c.error = r.code; }
      emit();
      return r.ok;
    }

    async function cancelCheck() {
      var c = state.cancel;
      if (state.phase !== "open" || !c || !c.key || !c.proposal
          || (c.status !== "uncertain" && c.status !== "recorded")) return false;
      var read = ++cancelRead;
      var r = await call("cancel_receipt", { command_key: c.key, conversation_id: state.conversationId,
        mission_id: c.proposal.mission_id });
      if (r.stale || c !== state.cancel || read !== cancelRead) return false;
      if (!r.ok) { c.error = r.code; emit(); return false; }
      c.missionStatus = r.json.mission_status;
      if (r.json.status === "FOUND") { c.status = "recorded"; c.receipt = r.json.receipt; c.stage = r.json.stage; c.error = null; }
      else if (r.json.status === "NOT_FOUND" && !c.receipt) {
        c.status = "not_recorded"; c.stage = null; c.error = null;
      } else {
        // An unknown status or a missing receipt previously seen is not evidence of no command.
        c.status = "uncertain"; c.stage = null; c.error = "INVALID_RESPONSE";
        emit(); return false;
      }
      emit();
      return true;
    }

    // ---- G101: media results linked to this conversation, read fresh from the server
    async function loadMedia() {
      if (state.phase !== "open") return false;
      var previous = state.media && state.media.results ? state.media.results : [];
      var media = state.media = { status: "loading", results: previous, error: null };
      emit();
      var r = await call("media_results", { conversation_id: state.conversationId });
      if (r.stale || state.media !== media) return false;
      state.media = r.ok && Array.isArray(r.json.results)
        ? { status: "ready", results: r.json.results, error: null }
        : { status: "error", results: [], error: r.code || "INVALID_RESPONSE" };
      emit();
      return r.ok;
    }

    async function checkReceipt() {
      var s = state.submission;
      if (state.phase !== "open" || !s || s.status !== "uncertain") return false;
      var mine = epoch, read = ++submissionRead;
      var r = await call("receipt", { command_key: s.key });
      if (r.stale || mine !== epoch || s !== state.submission || read !== submissionRead) return false;
      if (!r.ok) { s.error = r.code; emit(); return false; }
      if (r.json.status === "FOUND") { s.status = "recorded"; s.receipt = r.json.receipt; s.error = null; }
      else s.status = "uncertain";
      emit();
      return true;
    }

    return { open: open, close: close, send: send, submit: submit, checkReceipt: checkReceipt, resume: resume,
      cancelPropose: cancelPropose, cancelSubmit: cancelSubmit, cancelCheck: cancelCheck, loadMedia: loadMedia,
      state: function () { return JSON.parse(JSON.stringify(state)); } };
  }

  // ---- rendering --------------------------------------------------------------------------------

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  // G101: a media result view (eidolon-media-result-view/1) in plain-text lines. Nothing here is a
  // button: opening an artifact is not available from the page, and no state is shown as a success.
  var MEDIA_STAGES = { created: "Travail créé", running: "En cours", result_unverified: "Résultat reçu, non vérifié",
    unknown_effect: "Effet inconnu : revue nécessaire", draft: "Brouillon", received_as_is: "État reçu" };
  var VERIFICATION = { hash_verified: "empreinte vérifiée", modified: "modifié depuis l'import : ne pas utiliser",
    unavailable: "indisponible", busy: "magasin occupé, réessayer plus tard" };
  var BINDING = { WRONG_JOB: "Ce résultat appartient à un autre travail : il n'est pas affiché.",
    LEGACY_UNVERIFIABLE: "Historique ancien : identité du travail non vérifiable, aucun fichier n'est affiché.",
    UNVERIFIABLE: "Résultat impossible à rattacher : rien n'est affiché.",
    UNREADABLE: "Résultat illisible : rien n'est affiché." };
  function mediaResultLines(view) {
    if (!view || typeof view !== "object") return [];
    var lines = [];
    var stage = MEDIA_STAGES[view.stage] || ("État reçu : " + (view.state_received || "inconnu"));
    lines.push({ cls: "conv-media-stage", text: stage + (view.state_received ? " (" + view.state_received + ")" : "") });
    if (view.binding !== "MATCHED") {
      lines.push({ cls: "conv-media-binding", text: BINDING[view.binding] || "Résultat non rattaché : rien n'est affiché." });
      return lines;
    }
    if (view.source) lines.push({ cls: "conv-media-source", text: "Fichier source " + view.source.artifact_id + " : " +
      (VERIFICATION[view.source.verification] || view.source.verification) });
    var c = view.collection;
    if (c && c.state === "WRONG_JOB") lines.push({ cls: "conv-media-binding", text: "Collecte d'un autre travail : ignorée." });
    else if (c && c.partial) lines.push({ cls: "conv-media-partial", text: "Collecte partielle : " + c.imported +
      (c.expected === null || c.expected === undefined ? "" : " sur " + c.expected) + " fichier(s) importé(s)." });
    (view.outputs || []).forEach(function (o) {
      var p = o.provenance || {};
      lines.push({ cls: "conv-media-output", text: String(o.display_name) + " — " + String(o.media_type) + " — " +
        (VERIFICATION[o.verification] || o.verification) + " ; contenu non vérifié ; travail " + p.job_id +
        ", nœud " + p.node_id + ", sortie " + p.output_index });
    });
    if (view.excluded_outputs) lines.push({ cls: "conv-media-excluded", text: view.excluded_outputs +
      " référence(s) sans lien avec ce travail : non affichée(s)." });
    if (view.observation) lines.push({ cls: "conv-media-observation", text: "Observation du modèle, non vérifiée : " + view.observation.text });
    lines.push({ cls: "help conv-media-open", text: "Ouverture depuis la page : non disponible (export par l'opérateur)." });
    return lines;
  }
  function renderMediaResult(doc, container, view) {
    container.textContent = "";
    mediaResultLines(view).forEach(function (line) { container.appendChild(el(doc, "p", line.cls, line.text)); });
  }

  function missionView(submission, missionStatus) {
    if (!submission || !submission.receipt) return null;
    var r = submission.receipt;
    if (r.status === "MISSION_CREATION_UNCERTAIN") return { stage: "unknown_effect", text: "Création incertaine après une coupure : décision humaine requise, rien n'est recréé." };
    if (r.status !== "MISSION_CREATED" || !MISSION.test(r.mission_id || "")) return { stage: null, text: "Soumission : " + r.status };
    var stage = missionStatus ? stageOf(missionStatus) : "created";
    return { stage: stage, missionId: r.mission_id,
      text: stage ? LABELS[stage] : "Statut reçu : " + missionStatus };
  }

  function render(doc, st, missionStatus) {
    var closed = st.phase !== "open";
    // G088-R1: the header states the actual mode; the read token itself never gains a right.
    var badge = doc.getElementById("mode-badge");
    if (badge) {
      badge.textContent = closed ? "Consultation seule" : "Conversation active";
      badge.title = closed ? "Aucune commande : ni accord, ni lancement, ni annulation"
        : "Une proposition que vous validez crée une mission ; le jeton de lecture reste en lecture seule.";
    }
    doc.getElementById("conv-connect").hidden = !closed;
    doc.getElementById("conv-body").hidden = closed;
    doc.getElementById("conv-close").hidden = closed;
    var status = doc.getElementById("conv-status");
    status.textContent = st.phase === "opening" ? "Ouverture…" :
      st.phase === "open" ? "Conversation ouverte (" + st.identity.actor + ")." :
      st.error === "KEY_FORMAT" ? "Clé de conversation au mauvais format." :
      st.error === "READ_TOKEN_NOT_ALLOWED" ? "Le jeton de lecture ne permet pas de converser : utilisez une clé de conversation." :
      st.error ? (busyNote(st.error) || "Conversation refusée ou indisponible (" + st.error + ").") :
      "Sans clé de conversation, cette page reste en lecture seule.";
    var recentBox = doc.getElementById("conv-recent"), recentList = doc.getElementById("conv-recent-list");
    recentList.textContent = "";
    var recent = closed ? [] : (st.recent || []);
    recentBox.hidden = recent.length === 0;
    recent.forEach(function (c) {
      var li = el(doc, "li");
      var b = el(doc, "button", "media-secondary", "Reprendre (" + c.turn_count + " échange" + (c.turn_count > 1 ? "s" : "") +
        ", dernier le " + String(c.last_turn_at || "").slice(0, 16).replace("T", " à ") + " UTC)");
      b.type = "button"; b.dataset.resume = c.conversation_id;
      li.appendChild(b); recentList.appendChild(li);
    });
    var log = doc.getElementById("conv-log");
    log.textContent = "";
    var previousReply = null;
    st.items.forEach(function (item) {
      var li = el(doc, "li", "conv-turn");
      li.appendChild(el(doc, "p", "conv-user", item.text));
      li.appendChild(el(doc, "p", "conv-state state-" + item.status, LABELS[item.status] + (item.error ? " — " + (busyNote(item.error) || item.error) : "")));
      if (item.status === "uncertain" || item.status === "pending") {
        var retry = el(doc, "button", "media-secondary", item.status === "pending" ? "Vérifier la réponse" : "Renvoyer le même message");
        retry.type = "button"; retry.dataset.retry = item.key;
        li.appendChild(retry);
      }
      var reply = item.reply;
      if (reply) {
        var box = el(doc, "div", "conv-reply kind-" + reply.kind.toLowerCase());
        box.appendChild(el(doc, "p", "conv-kind", REPLY_KINDS[reply.kind] || reply.kind));
        if (reply.core_note) {
          // Core decided; the model's own words are secondary and labelled as such.
          box.appendChild(el(doc, "p", "conv-note", NOTES[reply.core_note] || "Note de Core : " + reply.core_note));
          if (reply.model_text) box.appendChild(el(doc, "p", "conv-model", "Texte du modèle : " + reply.model_text));
        } else if (reply.model_text) {
          box.appendChild(el(doc, "p", "conv-text", reply.model_text));
        }
        // G096: a reference the model wrote but Core never sent is flagged, never presented as a source.
        var unsupported = reply.citations && Array.isArray(reply.citations.unsupported) ? reply.citations.unsupported : [];
        if (unsupported.length) {
          box.appendChild(el(doc, "p", "help conv-citation", "Citation non vérifiée : " + unsupported.join(", ") +
            (unsupported.length > 1 ? " ne figurent" : " ne figure") + " pas parmi les sources transmises au modèle."));
        }
        var partial = contextNote(reply.context);
        if (partial) box.appendChild(el(doc, "p", "help conv-context", partial));
        if (reply.candidates && reply.candidates.length) box.appendChild(el(doc, "p", "help", "Choix possibles : " + reply.candidates.join(", ")));
        if (reply.sources && reply.sources.length) box.appendChild(el(doc, "p", "help", "Sources : " + reply.sources.join(", ")));
        var label = modelLabel(reply, previousReply);
        if (label) box.appendChild(el(doc, "p", "help conv-model-id", label));
        previousReply = reply;
        li.appendChild(box);
      }
      log.appendChild(li);
    });
    log.scrollTop = log.scrollHeight;                   // the newest exchange stays in view
    var card = doc.getElementById("conv-proposal");
    var p = st.proposal;
    card.hidden = !p || closed;
    if (p && !closed) {
      doc.getElementById("conv-proposal-request").textContent = p.request;
      doc.getElementById("conv-proposal-meta").textContent = "Version " + p.version + " · cible " + p.target_id +
        " · rien n'est lancé tant que vous ne validez pas.";
      var s = st.submission;
      var sstate = doc.getElementById("conv-submission-state");
      sstate.textContent = !s ? LABELS.draft : s.status === "sent" ? "Validation envoyée…" :
        s.status === "uncertain" ? (busyNote(s.error) ? busyNote(s.error) + " La validation a peut-être été enregistrée : vérifiez son reçu avant tout renvoi."
          : LABELS.uncertain + (s.error ? " (" + s.error + ")" : "")) :
        s.status === "refused" ? (SUBMIT_ERRORS[s.error] || "Validation refusée (" + s.error + ").") : "Validation enregistrée.";
      doc.getElementById("conv-check").hidden = !(s && s.status === "uncertain");
      var mv = missionView(s, missionStatus);
      var track = doc.getElementById("conv-mission");
      track.hidden = !mv;
      if (mv) {
        doc.getElementById("conv-mission-state").textContent = mv.text;
        doc.getElementById("conv-mission-state").className = "conv-state" + (mv.stage ? " stage-" + mv.stage : "");
        doc.getElementById("conv-follow").hidden = !mv.missionId;
        doc.getElementById("conv-follow").dataset.missionId = mv.missionId || "";
      }
      doc.getElementById("conv-submit").disabled = !!(s && (s.status === "sent" || s.status === "recorded"));
    }
    renderCancel(doc, st, closed);
    renderMedia(doc, st, closed);
  }

  function cancelStatusText(c) {
    if (!c) return "";
    if (busyNote(c.error)) return busyNote(c.error) + (c.key
      ? " L’état de la demande n’a pas pu être vérifié : consultez son reçu avant tout renvoi."
      : " Aucune proposition d’arrêt disponible.");
    if (c.status === "loading") return "Préparation de la proposition d'arrêt…";
    if (c.status === "choose") return CANCEL_CODES.MISSION_AMBIGUOUS;
    if (c.status === "review") return "Rien n'est envoyé tant que vous ne confirmez pas.";
    if (c.status === "sent") return "Demande d'arrêt envoyée…";
    if (c.status === "recorded") return CANCEL_STAGES[c.stage] || ("État reçu : " + c.stage);
    if (c.status === "uncertain") return "Réponse perdue : la demande a peut-être été enregistrée. Vérifiez avant tout renvoi." +
      (c.error ? " (" + c.error + ")" : "");
    if (c.status === "not_recorded") return "Aucune demande enregistrée : vous pouvez confirmer à nouveau, sans risque de doublon.";
    if (c.status === "refused") return CANCEL_CODES[c.error] || ("Demande refusée (" + c.error + ").");
    if (c.status === "unavailable") return CANCEL_CODES[c.code] || ("Arrêt non disponible (" + c.code + ").");
    return CANCEL_CODES[c.error] || ("Impossible de préparer l'arrêt (" + c.error + ").");
  }

  function renderCancel(doc, st, closed) {
    var c = closed ? null : st.cancel;
    var choices = doc.getElementById("conv-cancel-choices");
    choices.textContent = "";
    choices.hidden = !(c && c.status === "choose");
    if (c && c.status === "choose") {
      c.candidates.forEach(function (id) {
        var li = doc.createElement("li"), b = el(doc, "button", "media-secondary", "Arrêter la mission " + id);
        b.type = "button"; b.dataset.cancelMission = id;
        li.appendChild(b); choices.appendChild(li);
      });
    }
    var review = doc.getElementById("conv-cancel-review");
    review.hidden = !(c && c.proposal);
    if (c && c.proposal) {
      doc.getElementById("conv-cancel-target").textContent = "Mission " + c.proposal.mission_id +
        (c.missionStatus ? " — statut actuel : " + c.missionStatus : "");
      doc.getElementById("conv-cancel-submit").disabled = !(c.status === "review" || c.status === "not_recorded");
    }
    var line = doc.getElementById("conv-cancel-state");
    line.textContent = cancelStatusText(c);
    line.className = "conv-state" + (c && c.stage ? " cancel-" + c.stage : "");
    doc.getElementById("conv-cancel-check").hidden = !(c && c.key &&
      (c.status === "uncertain" || (c.status === "recorded" && FINAL_STAGES.indexOf(c.stage) < 0)));
  }

  function renderMedia(doc, st, closed) {
    var m = closed ? null : st.media;
    var line = doc.getElementById("conv-media-state"), list = doc.getElementById("conv-media-list");
    list.textContent = "";
    line.textContent = !m ? "" : m.status === "loading" ? "Lecture des résultats…" :
      m.status === "error" ? (busyNote(m.error) || "Résultats indisponibles (" + m.error + ").") :
      !m.results.length ? "Aucun résultat image ou vidéo lié à cette conversation." :
      m.results.length + " résultat(s) lu(s) maintenant sur le serveur.";
    if (!m) return;
    m.results.forEach(function (view) {
      var box = el(doc, "div", "conv-media-result");
      box.appendChild(el(doc, "p", "conv-kind", (view.agent === "video" ? "Vidéo" : "Image") + " — " +
        ({ create: "création", edit: "retouche", analyze: "analyse" }[view.operation] || view.operation)));
      var body = el(doc, "div");
      renderMediaResult(doc, body, view);
      box.appendChild(body);
      list.appendChild(box);
    });
  }

  function mount(doc, deps) {
    var conv = createConversation({ transport: deps.transport, onChange: function (st) { render(doc, st, deps.missionStatus(st)); } });
    doc.getElementById("conv-connect").addEventListener("submit", function (event) {
      event.preventDefault();
      var input = doc.getElementById("conv-key"), value = input.value.trim();
      input.value = "";                                 // the DOM never keeps the key
      conv.open(value).then(function (ok) { (ok ? doc.getElementById("conv-text") : input).focus(); });
    });
    doc.getElementById("conv-close").addEventListener("click", function () { conv.close(); doc.getElementById("conv-key").focus(); });
    doc.getElementById("conv-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var input = doc.getElementById("conv-text"), text = input.value;
      if (!text.trim()) return;
      input.value = "";
      conv.send(text).then(function () { input.focus(); });
    });
    doc.getElementById("conv-log").addEventListener("click", function (event) {
      var b = event.target.closest("button[data-retry]");
      if (b) conv.send(null, b.dataset.retry);
    });
    doc.getElementById("conv-submit-form").addEventListener("submit", function (event) {
      event.preventDefault();
      conv.submit(doc.getElementById("conv-reason").value);
    });
    doc.getElementById("conv-check").addEventListener("click", function () { conv.checkReceipt(); });
    doc.getElementById("conv-recent-list").addEventListener("click", function (event) {
      var b = event.target.closest("button[data-resume]");
      if (b) conv.resume(b.dataset.resume).then(function (ok) { if (ok) doc.getElementById("conv-text").focus(); });
    });
    doc.getElementById("conv-cancel-start").addEventListener("click", function () { conv.cancelPropose(); });
    doc.getElementById("conv-cancel-choices").addEventListener("click", function (event) {
      var b = event.target.closest("button[data-cancel-mission]");
      if (b) conv.cancelPropose(b.dataset.cancelMission).then(function () { doc.getElementById("conv-cancel-reason").focus(); });
    });
    doc.getElementById("conv-cancel-form").addEventListener("submit", function (event) {
      event.preventDefault();
      conv.cancelSubmit(doc.getElementById("conv-cancel-reason").value);
    });
    doc.getElementById("conv-cancel-check").addEventListener("click", function () { conv.cancelCheck(); });
    doc.getElementById("conv-media-load").addEventListener("click", function () { conv.loadMedia(); });
    doc.getElementById("conv-follow").addEventListener("click", function (event) {
      var id = event.currentTarget.dataset.missionId;
      if (MISSION.test(id)) deps.follow(id);
    });
    render(doc, conv.state(), null);
    return { conversation: conv, refresh: function () { var st = conv.state(); render(doc, st, deps.missionStatus(st)); },
      clear: function () { conv.close(); } };
  }

  var api = { busyNote: busyNote, createConversation: createConversation, NOTES: NOTES, contextNote: contextNote, modelLabel: modelLabel, CANCEL_STAGES: CANCEL_STAGES, CANCEL_CODES: CANCEL_CODES, cancelStatusText: cancelStatusText, mediaResultLines: mediaResultLines, renderMediaResult: renderMediaResult, canonical: canonical, digest: digest, stageOf: stageOf, missionView: missionView, LABELS: LABELS, mount: mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonConversation = api;
})(typeof window !== "undefined" ? window : this);
