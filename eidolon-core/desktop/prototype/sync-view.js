/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : sync-view.js
 * Description : Scénarios et rendu de la synchronisation client-sync/1 dans le prototype (C-TASK-G012)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * The bench plays recorded envelopes (Codex's real trace, plus labelled derived
 * cases) into sync-state.js. Every string coming from an envelope is written
 * with textContent after rendering (data-sync-text), never as HTML.
 */
(function (root) {
  "use strict";
  var S = root.EidolonSync, F = root.EidolonSyncFixtures;

  function real(path, label) {
    return { type: "deliver", source: "observé : trace Core C-008a", label: label + " (trace réelle)", env: function () {
      return path.split(".").reduce(function (o, k) { return o[k]; }, F.original); } };
  }
  function derived(name, label, patch) {
    return { type: "deliver", source: "dérivé : " + name, label: label + " (cas dérivé)", env: function () {
      var env = JSON.parse(JSON.stringify(F.derived[name].envelope));
      return patch ? patch(env) : env; } };
  }
  var asSnapshot = function (env) { env.status = "SNAPSHOT"; env.events = []; return env; };
  function observed(name, label) {
    return { type: "deliver", source: "observé : capture Core " + name, label: label + " (capture Core observée)", env: function () {
      return JSON.parse(JSON.stringify(F.observed[name].envelope)); } };
  }
  // A late answer to the request sent before the reset (same epoch): it must change nothing.
  function late(path, label) {
    var step = real(path, label);
    return { type: "late", source: step.source, label: label + " (réponse tardive, trace réelle)", env: step.env };
  }

  var SCENARIOS = {
    "sync-rattrapage": { label: "Sync : reconnexion et rattrapage paginé", summary: "Capture initiale, coupure, puis cinq pages de la trace C-008a, dont une répétée.",
      steps: [real("initial", "Capture initiale"), { type: "offline", label: "Coupure" }, { type: "online", label: "Retour de la connexion" },
        real("pages.0", "Page 1"), real("pages.1", "Page 2"), real("pages.1", "Page 2 répétée"), real("pages.2", "Page 3"),
        real("pages.3", "Page 4"), real("pages.4", "Page 5")] },
    "sync-hors-ordre": { label: "Sync : réponse en retard, hors ordre", summary: "Une réponse plus ancienne arrive après une plus récente : elle ne remplace rien.",
      steps: [real("initial", "Capture initiale"), real("pages.0", "Page 1"), real("pages.1", "Page 2"),
        derived("late_older_answer", "Ancienne réponse en retard")] },
    "sync-annulation": { label: "Sync : annulation demandée, révision inchangée", summary: "La demande d'annulation se voit par la capture, sans être affichée comme annulée.",
      steps: [derived("cancel_before", "Capture RUNNING", asSnapshot), derived("cancel_requested_same_revision", "Événement CANCEL_REQUESTED")] },
    "sync-reset": { label: "Sync : RESET_REQUIRED et rechargement explicite", summary: "Historique changé puis base changée : rien n'est remplacé sans ton geste.",
      steps: [real("initial", "Capture initiale"), real("pages.0", "Page 1"), real("reset_example", "RESET_REQUIRED (ANCHOR_CHANGED)"),
        late("pages.1", "Page 2 arrivant après le reset"), derived("reset_store_changed", "RESET_REQUIRED (STORE_CHANGED)")] },
    "sync-rejets": { label: "Sync : réponses rejetées et texte hostile", summary: "Mauvaise mission, version inconnue, entier non exact, erreur Core, puis texte HTML affiché comme texte.",
      steps: [real("initial", "Capture initiale"), derived("wrong_mission_cursor", "Curseur d'une autre mission"),
        derived("unknown_protocol", "Version de protocole inconnue"), derived("unsafe_integer", "Entier 2^53"),
        { type: "error", code: "INVALID_CURSOR", label: "Erreur Core INVALID_CURSOR" }, real("pages.0", "Page 1"),
        derived("hostile_text", "Texte HTML dans les données")] },
    "sync-accord": { label: "Sync : accord en attente (axes séparés)", summary: "Décision, applicabilité et effet affichés séparément ; aucun bouton actif.",
      steps: [derived("action_pending", "Capture avec proposition PENDING", asSnapshot)] },
    "sync-objectif-null": { label: "Sync : demande hors catalogue (objectif nul)", summary: "Vraie capture Core : BLOCKED, issue CLARIFICATION, objective_kind=null. Aucun objectif inventé.",
      steps: [observed("core_unsupported", "Capture hors catalogue")] },
    "sync-revue-annulation": { label: "Sync : revue requise et annulation demandée", summary: "La revue reste l'état principal ; la demande d'annulation est affichée à part, sans promettre d'issue.",
      steps: [derived("review_with_cancel", "Capture REVIEW_REQUIRED avec annulation demandée", asSnapshot)] },
    "sync-revue": { label: "Sync : revue requise, effet inconnu", summary: "Accord consommé, effet inconnu : aucune relance proposée.",
      steps: [derived("action_review", "Capture REVIEW_REQUIRED", asSnapshot)] }
  };

  function create(key) {
    return { key: key, state: S.createState(), index: 0, minute: 0, log: [] };
  }

  function clock(minute) {
    var d = new Date(Date.UTC(2026, 9, 6, 6, 0, 0) + minute * 60000);
    return String(d.getUTCHours()).padStart(2, "0") + ":" + String(d.getUTCMinutes()).padStart(2, "0") + " UTC (synthétique)";
  }

  function nextLabel(sync) {
    var step = SCENARIOS[sync.key].steps[sync.index];
    if (sync.state.reset && !(step && step.type === "late")) return "En attente : recharge la vue explicitement dans la fenêtre Eidolon.";
    return step ? "Prochaine étape : " + step.label : "Fin du scénario.";
  }

  function step(sync) {
    var s = JSON.parse(JSON.stringify(sync));
    var st = SCENARIOS[s.key].steps[s.index];
    if (!st) return s;
    if (s.state.reset && st.type === "deliver") return s; // a real transport stops polling too ("late" answers still arrive)
    s.minute += 1;
    var at = clock(s.minute);
    if (st.type === "offline") s.state = S.setConnection(s.state, "offline");
    else if (st.type === "online") s.state = S.setConnection(s.state, "online");
    else {
      var request = st.type === "late" && s.lastRequest ? JSON.parse(JSON.stringify(s.lastRequest))
        : (S.nextRequest(s.state) || { kind: "poll", epoch: s.state.epoch, cursorSequence: null });
      if (st.type !== "late") s.lastRequest = JSON.parse(JSON.stringify(request));
      request.receivedAt = at;
      var before = s.state.view && s.state.view.asOf;
      s.state = st.type === "error" ? S.receiveError(s.state, st.code, request) : S.receive(s.state, st.env(), request);
      if (st.source && s.state.view && s.state.view.asOf !== before) s.source = st.source; // provenance of the capture shown
    }
    s.log.push(at + " — " + st.label);
    if (s.log.length > 30) s.log.shift();
    s.index += 1;
    return s;
  }

  // Eye for the sync view: Core says nothing about a live process from a capture.
  function eye(sync) {
    var st = sync.state, m = st.view && st.view.mission;
    if (st.connection !== "online") return { mode: "offline", label: "Injoignable", detail: "Dernière réponse " + (st.lastContactAt || "aucune") };
    if (st.reset) return { mode: "attention", label: "Rechargement à confirmer", detail: "Historique ou base changés" };
    if (m && (m.status === "REVIEW_REQUIRED" || (m.action_view && m.action_view.decision.status === "PENDING"))) return { mode: "attention", label: "Attend une revue ou un accord", detail: "Lecture seule ici" };
    if (m && m.status === "RUNNING") return { mode: "work", label: "En cours (capture)", detail: "Ne prouve pas qu'un processus vit" };
    return { mode: "idle", label: "En veille", detail: m ? "Dernière capture reçue" : "Aucune capture" };
  }

  var RESET_TEXT = {
    ANCHOR_CHANGED: "L'événement où s'arrêtait ce client a changé : l'historique n'est plus continu.",
    HISTORY_CHANGED: "Le nombre d'événements antérieurs a changé : l'historique n'est plus continu.",
    STORE_CHANGED: "La base du serveur n'est plus la même (restauration, changement de machine…).",
    CURSOR_AHEAD: "Ce client croit avoir vu plus d'événements que le serveur n'en a."
  };

  // Returns { html, texts }: the caller writes texts[i] into [data-sync-text="i"] with textContent.
  function render(sync, h) {
    var st = sync.state, texts = [];
    function t(value) { texts.push(String(value)); return '<span data-sync-text="' + (texts.length - 1) + '"></span>'; }
    var e = eye(sync), sum = S.summary(st), m = st.view && st.view.mission;
    var head = '<div class="titlebar"><div class="brand"><span class="brand-mark" aria-hidden="true">E</span>'
      + '<h1 class="visually-hidden">Eidolon</h1><span aria-hidden="true">Eidolon</span></div>'
      + '<div class="presence" role="img" aria-label="Présence d\'Eidolon : ' + h.esc(e.label) + ". " + h.esc(e.detail) + '">'
      + '<div class="presence-text" aria-hidden="true"><strong>' + h.esc(e.label) + "</strong><span>" + h.esc(e.detail) + "</span></div>"
      + h.eyeSvg(e.mode, 48, "sync") + "</div></div>"
      + '<ul class="indicators" aria-label="Indicateurs">'
      + (st.connection === "online" ? '<li class="chip ok" data-indicator="connection">Connecté au serveur Eidolon</li>'
        : '<li class="chip warn" data-indicator="connection">Serveur Eidolon injoignable</li>')
      + '<li class="chip neutral">Lecture seule : ce protocole n\'autorise aucune action</li></ul>';
    var banners = "";
    if (st.connection !== "online") {
      banners += '<div class="banner" role="status"><p><strong>Serveur Eidolon injoignable.</strong> Dernière capture faite par le serveur : '
        + (st.view ? t(st.view.observedAt) : "aucune") + ", reçue ici à " + t(st.lastContactAt || "—")
        + ". Son état actuel est inconnu ; rien n'est envoyé ni mis en file.</p></div>";
    }
    if (st.reset) {
      banners += '<div class="banner" role="alert" id="sync-reset"><p><strong>Rattrapage impossible (' + t(st.reset.reason) + ").</strong> "
        + h.esc(RESET_TEXT[st.reset.reason] || "") + " La vue affichée reste l'ancienne. Recharger remplace la vue et le journal ; "
        + "cela ne relance aucune mission et ne décide rien.</p>"
        + '<div class="row">' + h.btn("Recharger explicitement la vue", "sync-accept-reset", { kind: "primary", id: "sync-accept-reset" }) + "</div></div>";
    }
    var card = '<section class="card" aria-labelledby="sync-title"><div class="card-head"><h3 id="sync-title">Mission '
      + (m ? t(m.id) : "—") + ' <span class="synthetic" id="sync-source">' + t(sync.source || "aucune capture") + "</span></h3>"
      + '<span class="state" id="sync-state">' + h.esc(S.missionLabel(m)) + "</span></div>";
    if (m) {
      var av = m.action_view;
      card += '<dl class="facts">'
        + "<dt>Objectif</dt><dd id=\"sync-objective\">" + (m.objective_kind === null ? "Aucun objectif reconnu (hors catalogue)" : t(m.objective_kind)) + "</dd>"
        + "<dt>Statut Core</dt><dd>" + t(m.status) + " · phase " + t(m.phase) + " · révision " + t(m.revision) + "</dd>"
        + "<dt>Issue</dt><dd>" + t(m.outcome_status) + "</dd>"
        + "<dt>Progression</dt><dd>" + t(m.progress.completed) + " / " + t(m.progress.total === null ? "?" : m.progress.total) + "</dd>"
        + "<dt>Annulation demandée</dt><dd id=\"sync-cancel\">" + (m.cancel_requested ? h.esc(S.cancelNote(m)) : "non") + "</dd>"
        + "<dt>Capture</dt><dd>jusqu'à l'événement " + t(st.view.asOf) + ", faite par le serveur à " + t(st.view.observedAt)
        + " (ne prouve pas la santé actuelle)</dd>"
        + '<dt>Journal reçu</dt><dd id="sync-cursor">jusqu\'à l\'événement ' + t(sum.cursorSequence)
        + (sum.catchingUp ? " — rattrapage en cours, pages restantes demandées" : "") + "</dd>";
      if (av) {
        card += "<dt>Décision</dt><dd>" + t(av.decision.status) + " — " + t(av.decision.message) + "</dd>"
          + "<dt>Applicabilité</dt><dd>" + t(av.applicability.code) + " — " + t(av.applicability.message) + "</dd>"
          + "<dt>Effet</dt><dd>" + t(av.effect.code) + " — " + t(av.effect.message) + "</dd>";
      } else {
        card += "<dt>Proposition</dt><dd>Aucune (cette mission n'a pas d'action à approuver)</dd>";
      }
      card += "</dl>";
      if (av) card += '<p class="small">Les décisions ne passent pas par ce protocole de lecture : aucun bouton d\'accord ici. '
        + "Une capture n'autorise jamais l'exécution.</p>";
    } else {
      card += '<p class="small muted">Aucune capture reçue.</p>';
    }
    card += "</section>";
    var refs = st.refs.slice(-12).map(function (r) {
      return "<li>n° " + t(r.sequence) + " · " + t(r.kind) + " · " + t(r.at) + "</li>";
    }).join("");
    var journal = "<h3>Références d'événements reçues</h3>"
      + '<p class="small muted">Des références d\'historique, pas des changements appliqués à la vue. Doublons ignorés : '
      + st.stats.duplicateRefs + " · réponses périmées ignorées : " + st.stats.staleAnswers + " · captures plus anciennes ignorées : "
      + st.stats.staleViews + (st.stats.frozenAnswers ? " · réponses ignorées pendant le reset : " + st.stats.frozenAnswers : "")
      + (st.droppedRefs ? " · anciennes références retirées : " + st.droppedRefs : "") + ".</p>"
      + '<ul class="small" id="sync-refs" aria-label="Références d\'événements">' + refs + "</ul>";
    var problems = st.stats.rejected.map(function (r) { return "<li>Réponse ignorée : " + t(r.code) + "</li>"; }).join("")
      + st.stats.coreErrors.map(function (r) { return "<li>Erreur signalée par Core : " + t(r.code) + " — aucune capture n'en est déduite.</li>"; }).join("");
    var trouble = problems ? '<h3>Réponses refusées</h3><ul class="small" id="sync-rejected">' + problems + "</ul>" : "";
    var html = '<div class="window extended">' + head + banners + '<div class="content">' + card + journal + trouble + "</div></div>";
    return { html: html, texts: texts };
  }

  function fill(container, texts) {
    var nodes = container.querySelectorAll("[data-sync-text]");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = texts[Number(nodes[i].getAttribute("data-sync-text"))];
  }

  root.EidolonSyncView = { SCENARIOS: SCENARIOS, create: create, step: step, nextLabel: nextLabel, eye: eye, render: render, fill: fill };
})(window);
