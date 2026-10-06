/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : list-view.js
 * Description : Scénarios et rendu de l'inventaire mission-list/1 dans le prototype (C-TASK-G018)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * The bench plays recorded pages (Codex's C-008e trace, badge "observé", and
 * labelled derived cases, badge "dérivé") into mission-list-state.js. Selecting
 * a mission asks only a client-sync/1 snapshot of that id. Every string coming
 * from a page is written with textContent (data-sync-text), never as HTML.
 */
(function (root) {
  "use strict";
  var L = root.EidolonMissionList, S = root.EidolonSync, F = root.EidolonListFixtures;
  var O = F.observed.trace;
  var OBS = "observé : trace Core C-008e";
  function at(path) { return path.split(".").reduce(function (o, k) { return o[k]; }, O); }

  function observed(path, label) {
    return { type: "page", source: OBS, label: label + " (observé)", env: function () { return JSON.parse(JSON.stringify(at(path))); } };
  }
  function derivedPage(name, label, index) {
    var d = F.derived[name];
    return { type: "page", source: "dérivé : " + name, label: label + " (dérivé)", why: d.why, env: function () {
      var v = index === undefined ? d.value : d.value[index];
      return JSON.parse(JSON.stringify(v)); } };
  }
  // A page answering the request sent BEFORE the last change (late or repeated answer).
  function lateObserved(path, label) {
    var st = observed(path, label);
    return { type: "late-page", source: OBS, label: label + " (réponse tardive, observé)", env: st.env };
  }
  function pick(id, label) { return { type: "select", id: id, label: label + " (geste simulé de l'utilisateur)" }; }
  function answer(n, label) { return { type: "select-answer", n: n, label: label + " (dérivé : capture client-sync construite depuis la liste)" }; }

  var ids = O.fresh_pages.map(function (p) { return p.items[0].mission.id; });

  var SCENARIOS = {
    "liste-pagination": { label: "Liste : pagination complète puis sélection", summary: "Trois pages observées d'une même génération, une page répétée ignorée, puis lecture client-sync de la mission choisie.",
      steps: [observed("fresh_pages.0", "Page 1"), observed("fresh_pages.1", "Page 2"), lateObserved("fresh_pages.1", "Page 2 répétée"),
        observed("fresh_pages.2", "Page 3"), pick(ids[0], "Choix de " + ids[0].slice(0, 10) + "…"), answer(0, "Capture de la mission choisie")] },
    "liste-reset": { label: "Liste : reset entre deux pages", summary: "Une annulation change la génération entre la page 1 et la page 2 : l'ancien inventaire reste affiché comme périmé ; la relecture est explicite.",
      steps: [observed("initial_page", "Page 1 (génération 3)"), observed("changed_between_pages", "RESET_REQUIRED (STATE_CHANGED)"),
        lateObserved("fresh_pages.1", "Page arrivant pendant l'attente"), observed("fresh_pages.0", "Page 1 (génération 4)"),
        observed("fresh_pages.1", "Page 2 (génération 4)"), observed("fresh_pages.2", "Page 3 (génération 4)")] },
    "liste-selection-en-vol": { label: "Liste : sélection changée pendant une réponse en vol", summary: "La réponse pour la première mission choisie arrive après un second choix : elle n'écrase pas la mission affichée.",
      steps: [observed("fresh_pages.0", "Page 1"), observed("fresh_pages.1", "Page 2"), observed("fresh_pages.2", "Page 3"),
        pick(ids[0], "Choix A"), pick(ids[1], "Choix B pendant que A est en vol"), answer(0, "Réponse pour A, en retard"), answer(1, "Réponse pour B")] },
    "liste-deconnexion": { label: "Liste : coupure entre deux pages", summary: "Une page arrive hors ligne : ignorée. Au retour, la même page est redemandée avec le même curseur.",
      steps: [observed("fresh_pages.0", "Page 1"), { type: "offline", label: "Coupure" }, observed("fresh_pages.1", "Page 2 reçue hors ligne"),
        { type: "online", label: "Retour de la connexion" }, observed("fresh_pages.1", "Page 2 redemandée"), observed("fresh_pages.2", "Page 3")] },
    "liste-variee": { label: "Liste : statuts à ne pas confondre", summary: "Objectif nul, revue requise avec annulation demandée, annulation demandée en cours, terminée : aucun bouton d'exécution.",
      steps: [derivedPage("varied_page", "Page unique variée")] },
    "liste-vide": { label: "Liste : aucune mission", summary: "Base sans mission : la liste vide est dite vide, pas « en chargement ».",
      steps: [derivedPage("empty_store", "Page vide")] },
    "liste-tronquee": { label: "Liste : 250 missions, plafond de 200", summary: "Le client s'arrête à 200 et le dit : jamais « tout affiché ».",
      steps: [derivedPage("big_inventory", "Page 1/3", 0), derivedPage("big_inventory", "Page 2/3", 1), derivedPage("big_inventory", "Page 3/3", 2)] },
    "liste-incoherente": { label: "Liste : fin de liste incohérente avec le total", summary: "Page 2 présentée comme la dernière alors que 3 missions sont annoncées : refusée, jamais « entièrement lue » ; relecture explicite.",
      steps: [observed("fresh_pages.0", "Page 1"), derivedPage("ended_early", "Page 2 marquée comme dernière"),
        observed("fresh_pages.0", "Page 1 (nouvelle lecture)"), observed("fresh_pages.1", "Page 2"), observed("fresh_pages.2", "Page 3")] },
    "liste-rejets": { label: "Liste : pages rejetées et texte hostile", summary: "Autorité prétendue, entier 2^53, génération mélangée : rejetés. Texte HTML affiché comme texte.",
      steps: [derivedPage("authority_claimed", "Page prétendant autoriser l'exécution"), derivedPage("unsafe_integer", "Entier 2^53"),
        observed("fresh_pages.0", "Page 1"), derivedPage("mixed_generation", "Page 2 d'une autre génération"),
        { type: "relist", label: "Relecture explicite" }, derivedPage("hostile_text", "Page avec texte HTML")] }
  };

  function create(key) {
    return { kind: "list", key: key, state: L.createState(), index: 0, minute: 0, log: [], lastRequest: null, pending: [] };
  }

  function clock(minute) {
    var d = new Date(Date.UTC(2026, 9, 6, 8, 20, 0) + minute * 60000);
    return String(d.getUTCHours()).padStart(2, "0") + ":" + String(d.getUTCMinutes()).padStart(2, "0") + " UTC (synthétique)";
  }

  function nextLabel(b) {
    var st = SCENARIOS[b.key].steps[b.index];
    if ((b.state.stale || b.state.halted) && st && st.type === "page") return "En attente : relis la liste explicitement dans la fenêtre Eidolon.";
    return st ? "Prochaine étape : " + st.label : "Fin du scénario.";
  }

  function step(bench) {
    var b = JSON.parse(JSON.stringify(bench));
    var st = SCENARIOS[b.key].steps[b.index];
    if (!st) return b;
    if ((b.state.stale || b.state.halted) && st.type === "page") return b; // a real transport stops asking too
    b.minute += 1;
    var when = clock(b.minute);
    if (st.type === "offline" || st.type === "online") b.state = L.setConnection(b.state, st.type);
    else if (st.type === "relist") b.state = L.relist(b.state);
    else if (st.type === "select") {
      b.state = L.select(b.state, st.id);
      var req = L.selectionRequest(b.state);
      if (req) b.pending.push(req); // in flight until its answer step
    } else if (st.type === "select-answer") {
      var r = b.pending[st.n];
      if (r) {
        var env = JSON.parse(JSON.stringify(F.derived.selection_snapshots.value[r.missionId]));
        b.state = L.receiveSelection(b.state, env, Object.assign({}, r, { receivedAt: when, source: "dérivé : selection_snapshots" }));
      }
    } else {
      var request = st.type === "late-page" && b.lastRequest ? JSON.parse(JSON.stringify(b.lastRequest))
        : (L.nextPageRequest(b.state) || { kind: "list", epoch: b.state.epoch, cursor: b.state.nextCursor });
      if (st.type !== "late-page") b.lastRequest = JSON.parse(JSON.stringify(request));
      b.state = L.receivePage(b.state, st.env(), Object.assign(request, { receivedAt: when, source: st.source }));
    }
    b.log.push(when + " — " + st.label);
    if (b.log.length > 30) b.log.shift();
    b.index += 1;
    return b;
  }

  function eye(b) {
    var st = b.state;
    if (st.connection !== "online") return { mode: "offline", label: "Injoignable", detail: "Dernière réponse " + (st.lastContactAt || "aucune") };
    if (st.stale) return { mode: "attention", label: "Liste à relire", detail: "Le serveur a changé entre deux pages" };
    if (st.halted) return { mode: "attention", label: "Liste à relire", detail: "Réponse incohérente avec le total annoncé" };
    var review = L.shownItems(st).some(function (it) { return it.mission.status === "REVIEW_REQUIRED"; });
    if (review) return { mode: "attention", label: "Une mission attend une revue", detail: "Lecture seule ici" };
    return { mode: "idle", label: "En veille", detail: L.summary(st).status };
  }

  var RESET_TEXT = {
    STATE_CHANGED: "Le serveur a changé entre deux pages (mission créée, avancée ou annulation demandée).",
    STORE_CHANGED: "La base du serveur n'est plus la même (restauration, changement de machine…)."
  };

  function render(b, h) {
    var st = b.state, texts = [];
    function t(value) { texts.push(String(value)); return '<span data-sync-text="' + (texts.length - 1) + '"></span>'; }
    var e = eye(b), sum = L.summary(st);
    var head = '<div class="titlebar"><div class="brand"><span class="brand-mark" aria-hidden="true">E</span>'
      + '<h1 class="visually-hidden">Eidolon</h1><span aria-hidden="true">Eidolon</span></div>'
      + '<div class="presence" role="img" aria-label="Présence d\'Eidolon : ' + h.esc(e.label) + ". " + h.esc(e.detail) + '">'
      + '<div class="presence-text" aria-hidden="true"><strong>' + h.esc(e.label) + "</strong><span>" + h.esc(e.detail) + "</span></div>"
      + h.eyeSvg(e.mode, 48, "list") + "</div></div>"
      + '<ul class="indicators" aria-label="Indicateurs">'
      + (st.connection === "online" ? '<li class="chip ok" data-indicator="connection">Connecté au serveur Eidolon</li>'
        : '<li class="chip warn" data-indicator="connection">Serveur Eidolon injoignable</li>')
      + '<li class="chip neutral">Lecture seule : cette liste n\'autorise aucune action</li></ul>';
    var banners = "";
    if (st.connection !== "online") {
      banners += '<div class="banner" role="status"><p><strong>Serveur Eidolon injoignable.</strong> Dernière réponse reçue à '
        + t(st.lastContactAt || "—") + ". Rien n'est demandé ni mis en file.</p></div>";
    }
    if (st.halted) {
      banners += '<div class="banner" role="alert" id="list-halted"><p><strong>Liste incomplète (' + t(st.halted.code) + ").</strong> "
        + "Le serveur a répondu de façon incohérente avec le nombre de missions qu'il annonce. Les missions déjà reçues restent affichées ; "
        + "aucune n'est inventée et la liste n'est pas déclarée complète. Relire ne lance ni ne décide rien.</p>"
        + '<div class="row">' + h.btn("Relire la liste", "list-relist", { kind: "primary", id: "list-relist" }) + "</div></div>";
    }
    if (st.stale) {
      banners += '<div class="banner" role="alert" id="list-reset"><p><strong>Liste périmée (' + t(st.stale.reason) + ").</strong> "
        + h.esc(RESET_TEXT[st.stale.reason] || "") + " Les missions affichées viennent de l'ancienne lecture et ne sont pas mélangées "
        + "avec une nouvelle. Relire ne lance ni ne décide rien.</p>"
        + '<div class="row">' + h.btn("Relire la liste", "list-relist", { kind: "primary", id: "list-relist" }) + "</div></div>";
    }
    var shown = L.shownItems(st);
    var staleList = sum.stale;
    var rows = shown.map(function (it) {
      var m = it.mission, note = S.cancelNote(m), selected = st.selection && st.selection.missionId === m.id;
      return '<li class="list-row' + (selected ? " selected" : "") + '"><div class="list-main"><strong>' + t(m.id.slice(0, 12) + "…") + "</strong> "
        + '<span class="state">' + h.esc(S.missionLabel(m)) + "</span>"
        + (note ? '<span class="small"> · ' + h.esc(note) + "</span>" : "")
        + '<span class="small muted"> · objectif ' + (m.objective_kind === null ? "aucun reconnu (hors catalogue)" : t(m.objective_kind))
        + " · capture jusqu'à l'événement " + t(it.asOf) + "</span>"
        + ' <span class="synthetic">' + t(it.source || "provenance inconnue") + "</span></div>"
        + h.btn("Voir la mission", "list-select", { arg: m.id, aria: "Voir la mission " + m.id }) + "</li>";
    }).join("");
    var list = '<section class="card" aria-labelledby="list-title"><div class="card-head"><h3 id="list-title">Missions'
      + (staleList ? ' <span class="synthetic">PÉRIMÉE</span>' : "") + '</h3><span class="state" id="list-status">' + h.esc(sum.status) + "</span></div>"
      + '<p class="small muted">Ordre stable par identifiant (pas par date ni priorité). Plafond d\'affichage : ' + L.MAX_ITEMS
      + " missions. « Entièrement lue » vaut pour cette capture seulement.</p>"
      + (shown.length ? '<ul class="list" id="list-items" aria-label="Missions">' + rows + "</ul>"
        : '<p class="small" id="list-empty">' + (st.pages && st.complete ? "Aucune mission sur ce serveur dans cette capture." : "Aucune mission affichée pour l'instant.") + "</p>")
      + "</section>";
    var sel = "";
    if (st.selection) {
      var ss = st.selection.sync, m = ss.view && ss.view.mission;
      sel = '<section class="card" aria-labelledby="sel-title"><div class="card-head"><h3 id="sel-title">Mission choisie '
        + t(st.selection.missionId.slice(0, 12) + "…") + (st.selection.source ? ' <span class="synthetic">' + t(st.selection.source) + "</span>" : "")
        + '</h3><span class="state" id="sel-state">' + (m ? h.esc(S.missionLabel(m)) : "Lecture client-sync demandée…") + "</span></div>";
      if (m) {
        sel += '<dl class="facts"><dt>Statut Core</dt><dd>' + t(m.status) + " · phase " + t(m.phase) + " · révision " + t(m.revision) + "</dd>"
          + "<dt>Annulation demandée</dt><dd>" + (m.cancel_requested ? h.esc(S.cancelNote(m)) : "non") + "</dd>"
          + (m.action_view ? '<dt>Effet</dt><dd id="sel-effect">' + t(m.action_view.effect.code) + " — " + t(m.action_view.effect.message) + "</dd>" : "")
          + "<dt>Capture</dt><dd>jusqu'à l'événement " + t(ss.view.asOf) + " (lecture client-sync/1 séparée de la liste)</dd></dl>";
      }
      sel += '<p class="small">Aucune décision ni exécution depuis cet écran.</p></section>';
    }
    var problems = st.stats.rejected.map(function (r) { return "<li>Réponse ignorée : " + t(r.code) + "</li>"; }).join("");
    var trouble = problems ? '<h3>Réponses refusées</h3><ul class="small" id="list-rejected">' + problems + "</ul>" : "";
    var journal = '<p class="small muted" id="list-stats">Pages reçues : ' + st.pages + " · pages répétées ou tardives ignorées : " + st.stats.repeatedPages
      + " · réponses périmées : " + st.stats.staleAnswers + " · réponses ignorées pendant le reset : " + st.stats.frozenAnswers
      + " · réponses de sélection périmées : " + st.stats.staleSelections + ".</p>";
    var html = '<div class="window extended">' + head + banners + '<div class="content">' + list + sel + journal + trouble + "</div></div>";
    return { html: html, texts: texts };
  }

  function fill(container, texts) {
    var nodes = container.querySelectorAll("[data-sync-text]");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = texts[Number(nodes[i].getAttribute("data-sync-text"))];
  }

  // User gestures in the window (not the bench): select and explicit relisting.
  function act(bench, intent) {
    var b = JSON.parse(JSON.stringify(bench));
    if (intent.type === "list-relist") b.state = L.relist(b.state);
    else if (intent.type === "list-select") {
      b.state = L.select(b.state, intent.id);
      var req = L.selectionRequest(b.state);
      if (req) {
        b.pending.push(req);
        var env = F.derived.selection_snapshots.value[req.missionId];
        if (env) b.state = L.receiveSelection(b.state, JSON.parse(JSON.stringify(env)),
          Object.assign({}, req, { receivedAt: clock(b.minute), source: "dérivé : selection_snapshots" }));
      }
    } else if (intent.type === "sim-disconnect") b.state = L.setConnection(b.state, "offline");
    else if (intent.type === "sim-reconnect") b.state = L.setConnection(b.state, "online");
    return b;
  }

  root.EidolonListView = { SCENARIOS: SCENARIOS, create: create, step: step, nextLabel: nextLabel, eye: eye, render: render, fill: fill, act: act };
})(window);
