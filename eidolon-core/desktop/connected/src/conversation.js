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
    MODEL_ATTEMPT_INTERRUPTED: "La tentative de réponse a été interrompue : elle n'est pas relancée. Renvoyez le message si besoin."
  };
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

  function stageOf(status) { return Object.prototype.hasOwnProperty.call(STAGES, status) ? STAGES[status] : null; }

  function createConversation(options) {
    var transport = options.transport, onChange = options.onChange || function () {};
    var token = null, epoch = 0;
    var state = { phase: "closed", error: null, conversationId: null, identity: null, items: [],
      proposal: null, proposalSha: null, submission: null, recent: [] };

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
        state.phase = "closed"; state.error = "KEY_FORMAT"; emit(); return false;
      }
      epoch += 1; token = key;
      state = { phase: "opening", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [] };
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
      var items = [], after = 0;
      for (var i = 0; i < 20; i++) {
        var r = await call("page", { conversation_id: conversationId, after: after, limit: 50 });
        if (r.stale) return false;
        if (!r.ok) { state.error = r.code; emit(); return false; }
        r.json.items.forEach(function (it) {
          items.push({ key: it.turn.client_turn_key, text: it.turn.text, reply: it.reply, error: null,
            status: it.reply ? "received" : "pending" });
        });
        after = r.json.next_after;
        if (!r.json.has_more) break;
      }
      var last = items.filter(function (it) { return it.reply && it.reply.kind === "PROPOSAL"; }).pop();
      state.conversationId = conversationId;
      state.items = items;
      state.proposal = last ? last.reply.proposal : null;
      state.proposalSha = last ? last.reply.proposal_sha256 : null;
      state.submission = null;                            // unknown after a reload: never assumed, never resent
      state.recent = state.recent.filter(function (c) { return c.conversation_id !== conversationId; });
      state.resumed = true;
      emit();
      return true;
    }

    function close() {
      epoch += 1; token = null;
      state = { phase: "closed", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [] };
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
      item.status = "sent"; emit();
      var r = await call("turn", { conversation_id: state.conversationId, client_turn_key: item.key, text: item.text });
      if (r.stale) return false;
      item = state.items.filter(function (i) { return i.key === item.key; })[0];
      if (r.ok && r.json.pending) {
        item.status = "pending";                          // another attempt owns this turn (G090-R1)
      } else if (r.ok) {
        item.status = "received"; item.reply = r.json.reply;
        if (r.json.reply && r.json.reply.kind === "PROPOSAL") {
          state.proposal = r.json.reply.proposal; state.proposalSha = r.json.reply.proposal_sha256; state.submission = null;
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
      var p = state.proposal;
      var local = await digest(p);
      if (local !== state.proposalSha) {                  // shown ≠ frozen: never submitted
        state.submission = { key: null, proposalVersion: p.version, reason: reason, status: "refused",
          receipt: null, error: "DIGEST_MISMATCH" };
        emit();
        return false;
      }
      if (!state.submission || state.submission.proposalVersion !== p.version || state.submission.status === "refused") {
        state.submission = { key: randomKey("submit"), proposalVersion: p.version, reason: reason.trim(),
          status: "draft", receipt: null, error: null };
      }
      var s = state.submission;
      s.status = "sent"; emit();
      var body = { protocol: "eidolon-proposal-submission/1", store_id: p.store_id, client_id: state.identity.clientId,
        command_key: s.key, conversation_id: p.conversation_id, proposal_id: p.proposal_id,
        proposal_version: p.version, proposal_sha256: local, actor: state.identity.actor, reason: s.reason };
      var r = await call("submit", body);
      if (r.stale) return false;
      s = state.submission;
      if (r.ok) { s.status = "recorded"; s.receipt = r.json; }
      else { s.status = r.network || r.status >= 500 ? "uncertain" : "refused"; s.error = r.code; }
      emit();
      return r.ok;
    }

    async function checkReceipt() {
      if (state.phase !== "open" || !state.submission) return false;
      var r = await call("receipt", { command_key: state.submission.key });
      if (r.stale || !r.ok) return false;
      if (r.json.status === "FOUND") { state.submission.status = "recorded"; state.submission.receipt = r.json.receipt; }
      else state.submission.status = "uncertain";
      emit();
      return true;
    }

    return { open: open, close: close, send: send, submit: submit, checkReceipt: checkReceipt, resume: resume,
      state: function () { return JSON.parse(JSON.stringify(state)); } };
  }

  // ---- rendering --------------------------------------------------------------------------------

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
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
      st.error ? "Conversation refusée ou indisponible (" + st.error + ")." :
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
    st.items.forEach(function (item) {
      var li = el(doc, "li", "conv-turn");
      li.appendChild(el(doc, "p", "conv-user", item.text));
      li.appendChild(el(doc, "p", "conv-state state-" + item.status, LABELS[item.status] + (item.error ? " (" + item.error + ")" : "")));
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
        s.status === "uncertain" ? LABELS.uncertain + (s.error ? " (" + s.error + ")" : "") :
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
    doc.getElementById("conv-follow").addEventListener("click", function (event) {
      var id = event.currentTarget.dataset.missionId;
      if (MISSION.test(id)) deps.follow(id);
    });
    render(doc, conv.state(), null);
    return { conversation: conv, refresh: function () { var st = conv.state(); render(doc, st, deps.missionStatus(st)); },
      clear: function () { conv.close(); } };
  }

  var api = { createConversation: createConversation, NOTES: NOTES, contextNote: contextNote, canonical: canonical, digest: digest, stageOf: stageOf, missionView: missionView, LABELS: LABELS, mount: mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonConversation = api;
})(typeof window !== "undefined" ? window : this);
