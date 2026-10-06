/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : app.js
 * Description : Rendu et interactions du prototype bureau Eidolon (C-TASK-G009)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Renders model.js state into the page. No network, timer, storage or OS call.
 * Every control is a native <button>, <select>, <input> or <textarea>.
 */
(function () {
  "use strict";
  var M = window.EidolonModel;
  var state = M.initialState(initialScenario());

  function initialScenario() {
    var wanted = (location.hash || "").replace("#", "");
    return M.SCENARIOS[wanted] ? wanted : "accord-succes";
  }

  // ---- helpers ----------------------------------------------------------------------------

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function btn(label, intent, opts) {
    opts = opts || {};
    var attrs = ' type="button" class="btn' + (opts.kind ? " " + opts.kind : "") + '"'
      + ' data-intent="' + esc(intent) + '"';
    if (opts.id) attrs += ' id="' + esc(opts.id) + '"';
    if (opts.arg) attrs += ' data-arg="' + esc(opts.arg) + '"';
    if (opts.disabled) attrs += " disabled";
    if (opts.describedby) attrs += ' aria-describedby="' + esc(opts.describedby) + '"';
    if (opts.current) attrs += ' aria-current="page"';
    if (opts.pressed !== undefined) attrs += ' aria-pressed="' + (opts.pressed ? "true" : "false") + '"';
    if (opts.aria) attrs += ' aria-label="' + esc(opts.aria) + '"';
    return "<button" + attrs + ">" + esc(label) + "</button>";
  }

  var EYES = {
    idle: { iris: "#2a5bc0", ring: "#2a3f66", dash: "3 7", pupil: 6, lid: 0 },
    listen: { iris: "#4c8dff", ring: "#8fb6ff", dash: "none", pupil: 8.5, lid: 0 },
    work: { iris: "#3f7bea", ring: "#8fb6ff", dash: "22 9", pupil: 5.5, lid: 0 },
    attention: { iris: "#e0913f", ring: "#f0a050", dash: "5 4", pupil: 6, lid: 0 },
    silence: { iris: "#24448a", ring: "#2a3f66", dash: "2 8", pupil: 6, lid: 30 },
    offline: { iris: "#3a404b", ring: "#3a404b", dash: "2 6", pupil: 3, lid: 44 }
  };

  function eyeSvg(mode, size, id) {
    var e = EYES[mode];
    return '<svg class="eye eye-' + mode + '" width="' + size + '" height="' + size + '" viewBox="0 0 64 64" aria-hidden="true">'
      + '<defs><clipPath id="clip-' + id + '"><circle cx="32" cy="32" r="27"></circle></clipPath></defs>'
      + '<circle cx="32" cy="32" r="31" fill="#0b0d11" stroke="#3a404b" stroke-width="1.5"></circle>'
      + '<circle class="ring" cx="32" cy="32" r="25" fill="none" stroke="' + e.ring + '" stroke-width="2" stroke-dasharray="' + e.dash + '"></circle>'
      + '<g clip-path="url(#clip-' + id + ')">'
      + '<circle class="iris" cx="32" cy="32" r="16" fill="' + e.iris + '"></circle>'
      + '<circle class="pupil" cx="32" cy="32" r="' + e.pupil + '" fill="#05070a"></circle>'
      + '<circle cx="26.5" cy="26" r="2.6" fill="#ffffff" fill-opacity="0.85"></circle>'
      + '<rect x="0" y="0" width="64" height="' + e.lid + '" fill="#14171c"></rect>'
      + "</g></svg>";
  }

  function stateClass(m) {
    if (!m) return "";
    if (m.status === "BLOCKED" && m.proposal.status === "PENDING") return "wait";
    if (m.status === "SUCCEEDED") return "done";
    if (m.status === "REVIEW_REQUIRED") return "review";
    return "";
  }

  // ---- simulation bench (not part of the application) -------------------------------------

  function renderBench() {
    var options = Object.keys(M.SCENARIOS).map(function (k) {
      return '<option value="' + k + '"' + (k === state.scenario ? " selected" : "") + ">" + esc(M.SCENARIOS[k].label) + "</option>";
    }).join("");
    var c = state.client;
    return '<h2 id="bench-title">Banc de simulation — hors application</h2>'
      + "<p>Tout est synthétique : Core simulé, heures fictives, aucune connexion réseau ni accès au système.</p>"
      + '<div class="row"><label for="scenario">Scénario</label>'
      + '<select id="scenario">' + options + "</select>"
      + btn("Recharger le scénario", "load-scenario") + "</div>"
      + '<p class="small">' + esc(M.SCENARIOS[state.scenario].summary) + "</p>"
      + '<div class="row">' + btn("Étape suivante de Core", "server-step", { kind: "primary", id: "server-step" })
      + '<span class="next-step" id="next-step">' + esc(M.nextServerStep(state)) + "</span></div>"
      + '<div class="row">'
      + (c.connection === "online" ? btn("Couper la connexion", "sim-disconnect") : btn("Rétablir la connexion", "sim-reconnect"))
      + btn(c.mic === "on" ? "Arrêter le micro simulé" : "Activer le micro simulé", "sim-mic", { pressed: c.mic === "on" })
      + btn(c.session === "open" ? "Verrouiller la session" : "Déverrouiller la session", "sim-lock", { pressed: c.session !== "open" })
      + "</div>";
  }

  // ---- application window ------------------------------------------------------------------

  function renderApp() {
    var c = state.client;
    var e = M.eye(state);
    var mode = c.view;
    if (!c.windowOpen) {
      return '<div class="window compact"><div class="closed">'
        + "<h2>Fenêtre fermée</h2>"
        + '<p class="muted">Eidolon reste dans la zone de notification. Fermer la fenêtre n\'a rien décidé, rien révoqué ni rien annulé.</p>'
        + btn("Rouvrir Eidolon", "open-window", { kind: "primary", id: "reopen" }) + "</div></div>";
    }
    var head = '<div class="titlebar">'
      + '<div class="brand"><span class="brand-mark" aria-hidden="true">E</span><h1 class="visually-hidden">Eidolon</h1><span aria-hidden="true">Eidolon</span></div>'
      + '<div class="presence" role="img" aria-label="Présence d\'Eidolon : ' + esc(e.label) + ". " + esc(e.detail) + '">'
      + '<div class="presence-text" aria-hidden="true"><strong>' + esc(e.label) + "</strong><span>" + esc(e.detail) + "</span></div>"
      + eyeSvg(e.mode, 48, "main") + "</div>"
      + '<div class="row">'
      + btn(mode === "compact" ? "Vue étendue" : "Vue compacte", "set-view", { arg: mode === "compact" ? "extended" : "compact", id: "toggle-view" })
      + btn("Fermer", "close-window", { aria: "Fermer la fenêtre (ne décide rien)", id: "close-window" })
      + "</div></div>";
    var chips = '<ul class="indicators" aria-label="Indicateurs">' + M.indicators(state).map(function (i) {
      return '<li class="chip ' + i.tone + '" data-indicator="' + i.id + '">' + esc(i.text) + "</li>";
    }).join("") + "</ul>";
    var banner = "";
    if (c.connection !== "online") {
      banner = '<div class="banner" role="status"><p><strong>Serveur Eidolon injoignable.</strong> Cette déconnexion n\'annule pas les missions ; '
        + "leur état actuel est inconnu. Dernier état connu : " + esc(M.clockLabel(c.lastContact)) + ". Rien n'est envoyé ni mis en file.</p></div>";
    }
    var body;
    if (mode === "compact") {
      body = '<div class="content">' + renderConversation() + "</div>";
    } else {
      var tabs = [["conversation", "Conversation"], ["missions", "Missions"], ["systeme", "Système"], ["parametres", "Paramètres"]];
      body = '<div class="body"><nav class="nav" aria-label="Sections">' + tabs.map(function (t) {
        return btn(t[1], "set-tab", { arg: t[0], current: c.tab === t[0], id: "tab-" + t[0] });
      }).join("") + '</nav><div class="content">' + renderTab(c.tab) + "</div></div>";
    }
    var notice = c.notice ? '<p class="reason" role="status" id="notice">' + esc(c.notice) + "</p>" : "";
    return '<div class="window ' + mode + '">' + head + chips + banner
      + (notice ? '<div class="content">' + notice + "</div>" : "") + body + "</div>";
  }

  function renderTab(tab) {
    if (tab === "missions") return renderMissions();
    if (tab === "systeme") return renderSystem();
    if (tab === "parametres") return renderSettings();
    return renderConversation();
  }

  function renderConversation() {
    var c = state.client;
    var items = c.messages.map(function (m) {
      var who = m.from === "user" ? "Toi" : "Eidolon";
      var extra = m.reading ? '<div class="row">' + btn("Lecture assistée", "open-reading", { id: "open-reading" }) + "</div>" : "";
      var pending = m.pending ? " · envoyé, sans réponse dans ce prototype" : "";
      return '<li class="msg ' + (m.from === "user" ? "user" : "") + '"><span class="meta">' + who + " · " + esc(M.clockLabel(m.minute)) + pending + "</span>"
        + esc(m.text) + extra + "</li>";
    }).join("");
    var blocked = M.sendBlocker(state);
    return '<h2 class="visually-hidden">Conversation</h2><ul class="messages" aria-label="Messages">' + items + "</ul>"
      + renderDecisionCard()
      + '<div class="composer"><label class="visually-hidden" for="draft">Message à Eidolon</label>'
      + '<textarea id="draft" rows="2" placeholder="Écrire à Eidolon…">' + esc(c.draft) + "</textarea>"
      + btn("Envoyer", "send-chat", { kind: "primary", id: "send-chat", disabled: Boolean(blocked), describedby: blocked ? "send-reason" : null })
      + "</div>" + (blocked ? '<p class="reason" id="send-reason">' + esc(blocked) + "</p>" : "");
  }

  function renderDecisionCard() {
    var c = state.client, m = c.mission;
    if (!m) return "";
    var label = M.missionLabel(m);
    var p = m.proposal;
    var blocker = M.decisionBlocker(state);
    var off = c.connection !== "online";
    var openDecision = M.unresolvedCommands(state, "decision").length > 0;
    var actions = [];
    if (p.status === "PENDING" && m.status === "BLOCKED" && !openDecision) {
      actions.push(btn("Autoriser", "approve", { kind: "primary", id: "approve", disabled: Boolean(blocker), describedby: blocker ? "decision-reason" : null }));
      actions.push(btn("Refuser", "reject", { id: "reject", disabled: Boolean(blocker), describedby: blocker ? "decision-reason" : null }));
    }
    if (p.status === "APPROVED" && m.status === "BLOCKED") {
      actions.push(btn("Révoquer l'accord", "revoke", { kind: "danger", id: "revoke",
        disabled: Boolean(M.sendBlocker(state)) || M.unresolvedCommands(state, "revoke").length > 0 }));
    }
    if ((m.status === "RUNNING" || (m.status === "BLOCKED" && p.status === "APPROVED")) && !m.cancelRequested) {
      actions.push(btn("Demander l'annulation de la mission", "request-cancel", { id: "request-cancel",
        disabled: Boolean(M.sendBlocker(state)) || M.unresolvedCommands(state, "cancel").length > 0 }));
    }
    actions.push(btn("Voir les preuves", "set-tab", { arg: "missions", id: "see-evidence" }));
    var uncertain = c.commands.some(function (x) { return x.phase === "unknown" || x.phase === "not-found"; });
    var reason = "";
    if (uncertain && off) reason = "Hors ligne : les reçus seront consultables au retour de la connexion.";
    else if (blocker && p.status === "PENDING" && m.status === "BLOCKED") reason = blocker;
    var notes = [];
    if (p.status === "USED") notes.push("Accord consommé : il ne peut plus être révoqué.");
    if (m.status === "REVIEW_REQUIRED") notes.push("Aucune relance automatique : l'effet de la première tentative doit d'abord être établi par une revue.");
    if (openDecision && p.status !== "PENDING") {
      notes.push("La mission indique une décision enregistrée ; seul le reçu de ta demande dira si c'est la tienne.");
    }
    var commands = c.commands.length ? '<h4 class="small">Demandes envoyées</h4><ul class="commands" id="commands" aria-label="Demandes envoyées">'
      + c.commands.map(function (x) {
        var check = (x.phase === "unknown" || x.phase === "not-found" || x.phase === "checking")
          ? btn("Consulter le reçu", "check-receipt", { arg: x.key, id: "receipt-" + x.key, disabled: off || x.phase === "checking",
            aria: "Consulter le reçu de la demande " + x.key }) : "";
        return '<li class="command" id="command-' + esc(x.key) + '" data-phase="' + esc(x.phase) + '"><span>' + esc(M.commandLabel(x))
          + ' <code class="muted">' + esc(x.key) + "</code></span>" + check + "</li>";
      }).join("") + "</ul>" : "";
    return '<section class="card ' + (stateClass(m) === "wait" ? "awaiting" : "") + '" aria-labelledby="card-title">'
      + '<div class="card-head"><h3 id="card-title">' + esc(m.title) + ' <span class="synthetic">SIMULÉ</span></h3>'
      + '<span class="state ' + stateClass(m) + '" id="mission-state">' + esc(label.text) + "</span></div>"
      + (label.detail ? '<p class="small muted">' + esc(label.detail) + "</p>" : "")
      + '<dl class="facts">'
      + "<dt>Action proposée</dt><dd>Redémarrer <code>" + esc(p.target) + "</code> par <code>" + esc(p.tool) + "</code> (aucun service réel)</dd>"
      + "<dt>Condition approuvée</dt><dd>" + esc(p.condition) + "</dd>"
      + "<dt>Proposition</dt><dd><code>" + esc(p.id) + "</code>, empreinte <code>" + esc(p.sha256.slice(0, 16)) + "…</code>, révision " + m.revision + "</dd>"
      + '<dt>Accord</dt><dd id="decision-state">' + esc(M.DECISION_LABELS[p.status] || p.status) + "</dd>"
      + '<dt>Effet</dt><dd id="effect-state">' + esc(M.EFFECT_LABELS[m.effect] || m.effect) + "</dd>"
      + "</dl>"
      + commands
      + notes.map(function (n) { return '<p class="small">' + esc(n) + "</p>"; }).join("")
      + '<div class="row">' + actions.join("") + "</div>"
      + (reason ? '<p class="reason" id="decision-reason">' + esc(reason) + "</p>" : "")
      + '<p class="small muted">Fermer la fenêtre, le silence ou ton absence ne décident jamais à ta place.</p>'
      + "</section>";
  }

  function renderMissions() {
    var c = state.client, m = c.mission;
    if (!m) return "<h2>Missions</h2><p>Aucune mission connue.</p>";
    var rows = m.evidence.map(function (e) {
      return "<tr><td>" + esc(e.label) + "</td><td>" + esc(e.origin) + "</td><td><code>" + esc(M.syntheticTime(e.minute)) + "</code></td><td>"
        + (e.sha256 ? "<code>" + esc(e.sha256.slice(0, 16)) + "…</code> calculée par le serveur" : "aucune : pas de reçu") + "</td></tr>";
    }).join("");
    return "<h2>Missions</h2>" + renderDecisionCard()
      + "<h3>Preuves</h3>"
      + '<p class="small muted">Dates synthétiques. Une empreinte fixe un contenu ; elle ne prouve ni sa vérité ni son origine humaine.</p>'
      + '<div class="table-wrap"><table><thead><tr><th scope="col">Élément</th><th scope="col">Origine</th><th scope="col">Date</th><th scope="col">Empreinte</th></tr></thead><tbody>'
      + rows + "</tbody></table></div>"
      + "<h3>Journal reçu par ce client</h3>"
      + '<p class="small" id="journal">Événements appliqués : ' + c.seen.length + " (dernier n° " + c.cursor + "). Doublons ignorés : "
      + c.duplicatesIgnored + "." + (c.snapshotRequested ? " Trou détecté : nouvel état complet demandé." : "") + "</p>";
  }

  function renderSystem() {
    var c = state.client, online = c.connection === "online";
    var since = "inconnue depuis " + M.clockLabel(c.lastContact);
    function table(caption, rows) {
      return "<h3>" + esc(caption) + '</h3><div class="table-wrap"><table><thead><tr><th scope="col">Nom</th><th scope="col">Nature</th>'
        + '<th scope="col">Déploiement</th><th scope="col">Capacités configurées</th><th scope="col">Disponibilité</th></tr></thead><tbody>'
        + rows.map(function (r) {
          return "<tr>" + r.map(function (cell) { return "<td>" + esc(cell) + "</td>"; }).join("") + "</tr>";
        }).join("") + "</tbody></table></div>";
    }
    return '<h2>Système <span class="synthetic">SYNTHÉTIQUE</span></h2>'
      + '<p class="small muted">Valeurs de démonstration, pas des observations en direct. Configuré ne veut pas dire disponible.</p>'
      + table("Agents", [
        ["Eidolon (dialogue)", "Agent conversationnel", "Simulé dans ce prototype", "Dialoguer, proposer une mission", online ? "Simulée" : since]
      ]) + '<p class="small">Aucun autre agent autonome n\'est déployé.</p>'
      + table("Services et capacités", [
        ["Missions et accords", "Service du serveur", "Socle Core v0.1 sur le serveur ; données simulées ici", "Missions, propositions, accords, preuves", online ? "Simulée" : since],
        ["Recherche web", "Capacité candidate", "Hors runtime, non activée", "Rechercher, lire une page publique", "Non disponible"],
        ["Memory Engine", "Service", "Rappel Python présent ; accès réseau absent", "Rappel de contexte", "Non disponible à distance"],
        ["Documents du PC (C-003W)", "Connecteur local", "Prévu", "Lire/écrire des dossiers choisis", "Non disponible"],
        ["Vision", "Capacité", "Prévue", "Analyser des images", "Non disponible"]
      ])
      + table("Appareils", [
        ["Serveur Eidolon", "Hôte d'Eidolon", "En service (simulé)", "Missions, calcul", online ? "Joignable (simulé)" : since],
        ["Ce PC", "Poste client", "Prototype dans un navigateur", "Fenêtre, micro simulé", "Ce prototype"],
        ["WALL-E", "Robot", "Prévu, jamais connecté", "Caméra, audio, navigation (prévues)", "Non connecté — aucune commande possible"],
        ["NAS", "Stockage", "Non relié au serveur", "—", "Non relié"]
      ]);
  }

  function renderSettings() {
    var c = state.client;
    return "<h2>Paramètres</h2>"
      + '<p class="small muted">Réglages d\'affichage uniquement : ce prototype ne se connecte à rien et n\'écrit rien.</p>'
      + '<fieldset class="card"><legend>Connexion au serveur Eidolon</legend>'
      + '<label class="check"><input type="radio" name="route" checked disabled> Réseau local autorisé (selon configuration)</label>'
      + '<label class="check"><input type="radio" name="route" disabled> Depuis l\'extérieur, uniquement via le VPN (C-D08)</label>'
      + '<p class="small">Le tunnel VPN n\'authentifie ni l\'utilisateur ni l\'appareil. Vérification de l\'identité du serveur : prévue, non implémentée. '
      + "Appairage révocable de ce PC : futur, non disponible.</p></fieldset>"
      + '<fieldset class="card"><legend>Notifications</legend>'
      + '<label class="check"><input type="checkbox" checked disabled> Une décision m\'attend (aperçu générique si la session est verrouillée)</label>'
      + '<label class="check"><input type="checkbox" checked disabled> Une mission échoue ou demande une revue</label>'
      + '<div class="row">' + btn(c.silence ? "Quitter le silence" : "Activer le silence", "toggle-silence", { pressed: c.silence, id: "silence" }) + "</div>"
      + '<p class="small">En silence, les demandes attendent ; rien n\'est accepté à ta place.</p></fieldset>'
      + '<fieldset class="card"><legend>Démarrage</legend>'
      + '<label class="check"><input type="checkbox" disabled> Lancer Eidolon à l\'ouverture de session (désactivé par défaut, non qualifié sous Windows)</label></fieldset>';
  }

  // ---- simulated Windows integration --------------------------------------------------------

  function renderWindows() {
    var c = state.client, e = M.eye(state);
    var decisions = c.mission && c.mission.status === "BLOCKED" && c.mission.proposal.status === "PENDING" ? 1 : 0;
    // A decision toast stays only while a decision is actually pending; silence holds it back.
    var visible = decisions && !c.silence ? c.toasts.filter(function (t) { return t.kind === "decision"; }) : [];
    var toasts = visible.length ? visible.map(function (t, i) {
      var text = M.toastText(state, t);
      return '<div class="toast" data-toast="' + i + '"><p><strong>' + esc(text.title) + "</strong></p><p>" + esc(text.body) + "</p>"
        + btn(text.action, "open-decision", { id: "toast-open-" + i }) + "</div>";
    }).join("") : '<p class="small muted">' + (c.silence ? "Silence : notifications retenues, aucune décision prise." : "Aucune notification.") + "</p>";
    return '<h2 id="windows-title">Intégration Windows simulée</h2>'
      + '<p class="small muted">Zone de notification et notifications dessinées ici, non qualifiées sous Windows.</p>'
      + "<h3>Menu de la zone de notification</h3>"
      + '<div class="tray" role="group" aria-label="Menu Eidolon (simulé)">'
      + '<div class="tray-head">' + eyeSvg(e.mode, 28, "tray") + '<span class="small">Eidolon — ' + esc(e.label) + "</span></div>"
      + btn("Ouvrir la conversation", "open-window", { id: "tray-open" })
      + btn(decisions ? "Missions — 1 à décider" : "Missions", "open-decision", { id: "tray-missions" })
      + btn(c.silence ? "Quitter le silence" : "Silence", "toggle-silence", { pressed: c.silence })
      + btn("Fermer la fenêtre", "close-window")
      + "</div>"
      + "<h3>Notifications</h3>" + toasts;
  }

  // ---- assisted reading dialog -------------------------------------------------------------

  function renderDialog() {
    var c = state.client, r = c.reading;
    if (!r.open) return "";
    var blocked = M.sendBlocker(state);
    var canSend = !blocked && r.reviewed && r.text.trim();
    return '<div class="backdrop"><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="reading-title" id="reading-dialog">'
      + '<h2 id="reading-title">Lecture assistée</h2>'
      + '<p class="small">Source bloquée : <code>forum.example/svc-demo</code> (fictive). Ouvre-la toi-même, puis colle ici uniquement ce que tu veux transmettre.</p>'
      + '<label for="reading-text">Texte à transmettre</label>'
      + '<textarea id="reading-text">' + esc(r.text) + "</textarea>"
      + '<p class="small" id="reading-count">' + r.text.length + " caractères.</p>"
      + "<p><strong>Aperçu exact de ce qui partira</strong></p>"
      + '<pre class="preview" id="reading-preview">' + esc(r.text) + "</pre>"
      + '<p class="small">Aucune suppression automatique de secrets ni de données personnelles : relis ce texte. '
      + "Provenance enregistrée : « fourni par toi ».</p>"
      + '<label class="check"><input type="checkbox" id="reading-reviewed"' + (r.reviewed ? " checked" : "") + "> J'ai relu exactement ce texte</label>"
      + '<div class="row">' + btn("Envoyer à Eidolon", "reading-send", { kind: "primary", id: "reading-send", disabled: !canSend,
        describedby: blocked ? "reading-reason" : null })
      + btn("Annuler", "close-reading", { id: "reading-cancel" }) + "</div>"
      + (blocked ? '<p class="reason" id="reading-reason">' + esc(blocked) + "</p>" : "")
      + "</div></div>";
  }

  // ---- render loop ------------------------------------------------------------------------

  var lastLive = "";
  function render() {
    var focused = document.activeElement && document.activeElement.id;
    document.getElementById("bench").innerHTML = renderBench();
    document.getElementById("app").innerHTML = renderApp();
    document.getElementById("windows").innerHTML = renderWindows();
    document.getElementById("dialog-root").innerHTML = renderDialog();
    var live = [state.client.notice].concat(M.unresolvedCommands(state).map(M.commandLabel), [M.eye(state).label])
      .filter(Boolean).join(" ");
    if (live !== lastLive) { document.getElementById("live").textContent = live; lastLive = live; }
    var target = focused && document.getElementById(focused);
    if (state.client.reading.open && !document.getElementById("reading-dialog").contains(target)) {
      target = document.getElementById("reading-text");
    }
    if (target && !target.disabled) {
      target.focus();
      if (target.tagName === "TEXTAREA") target.setSelectionRange(target.value.length, target.value.length);
    }
    else if (focused && focused !== "scenario") document.getElementById("app").focus();
  }

  function act(intent) {
    if (intent.type === "server-step") state = M.serverStep(state);
    else if (intent.type === "load-scenario") state = M.initialState(document.getElementById("scenario").value);
    else state = M.dispatch(state, intent);
    render();
  }

  document.addEventListener("click", function (event) {
    var el = event.target.closest("[data-intent]");
    if (!el || el.disabled) return;
    var intent = { type: el.getAttribute("data-intent") };
    var arg = el.getAttribute("data-arg");
    if (intent.type === "set-view") intent.view = arg;
    if (intent.type === "set-tab") intent.tab = arg;
    if (intent.type === "check-receipt") intent.key = arg;
    act(intent);
  });

  // Typing updates the model without a full re-render (keeps the caret where it is).
  document.addEventListener("input", function (event) {
    var t = event.target;
    if (t.id === "draft") state = M.dispatch(state, { type: "draft", text: t.value });
    if (t.id === "reading-text") {
      state = M.dispatch(state, { type: "reading-text", text: t.value });
      document.getElementById("reading-preview").textContent = t.value;
      document.getElementById("reading-count").textContent = t.value.length + " caractères.";
      document.getElementById("reading-reviewed").checked = false;
      document.getElementById("reading-send").disabled = true;
    }
  });

  document.addEventListener("change", function (event) {
    if (event.target.id === "reading-reviewed") act({ type: "reading-reviewed", value: event.target.checked });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && state.client.reading.open) act({ type: "close-reading" });
  });

  window.EidolonPrototype = { getState: function () { return state; } }; // read-only hook for tests
  render();
})();
