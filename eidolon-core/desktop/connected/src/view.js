/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : view.js
 * Description : Rendu DOM du client connecté, texte via textContent seulement (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * render(doc, snapshot) rewrites the dynamic regions from a session snapshot.
 * Every value from Core is written with textContent; no HTML is ever parsed from data.
 * Buttons carry only a mission id read back by main.js; they never start a command.
 */
(function (root) {
  "use strict";
  var NODE = typeof module === "object" && module.exports;
  var C = NODE ? require("./session.js") : root.EidolonConnected;

  var PHASES = {
    disconnected: "Non connecté.",
    connecting: "Connexion en cours…",
    connected: "Connecté en lecture seule.",
    offline: "Serveur injoignable : l'affichage est le dernier état reçu, périmé.",
    unavailable: "Base Core indisponible : l'affichage est le dernier état reçu, périmé.",
    unauthorized: "Jeton refusé : saisir de nouveau le jeton pour reprendre.",
    refused: "Accès refusé par le serveur : ouvrir l'adresse servie par Core (127.0.0.1 ou localhost, même port)."
  };

  function fmt(iso) {
    if (typeof iso !== "string") return "—";
    var d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
  }

  function el(doc, tag, cls, text) {
    var node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function byId(doc, id) { return doc.getElementById(id); }
  function shortId(id) { return typeof id === "string" ? id.slice(0, 10) + "…" : "—"; }

  function renderConnection(doc, s) {
    var online = s.phase === "connected";
    var status = byId(doc, "connection-status");
    status.textContent = PHASES[s.phase] || s.phase;
    status.className = "status phase-" + s.phase;
    var parts = [];
    if (s.storeId) parts.push("Base " + s.storeId);
    parts.push("Dernière réponse reçue : " + (s.lastSuccessAt ? fmt(s.lastSuccessAt) : "aucune"));
    if (s.problem) parts.push("Dernier problème : " + s.problem.code + " (" + fmt(s.problem.at) + ")");
    byId(doc, "connection-detail").textContent = parts.join(" · ");
    var notice = byId(doc, "connection-notice");
    notice.hidden = !s.notice;
    notice.textContent = s.notice || "";
    byId(doc, "disconnect").disabled = s.phase === "disconnected";
    byId(doc, "relist").disabled = !online;
    var selected = Boolean(s.list.selection);
    byId(doc, "refresh").disabled = !online || !selected;
    byId(doc, "auto").disabled = !online || !selected;
  }

  function renderList(doc, s) {
    var summary = C.listSummary(s.list);
    var stale = s.phase !== "connected" && s.list.items.length > 0;
    var text = summary.status + (stale ? " — périmé (hors connexion)" : "");
    if (s.list.lastError) text += " — erreur Core : " + s.list.lastError;
    byId(doc, "list-status").textContent = s.phase === "disconnected" ? "" : text;
    var list = byId(doc, "mission-list");
    clear(list);
    var selectedId = s.list.selection ? s.list.selection.missionId : null;
    var oldInventory = !s.list.items.length && s.list.previous;
    C.shownItems(s.list).forEach(function (item) {
      var m = item.mission;
      var li = el(doc, "li", "mission" + (oldInventory || stale ? " stale" : ""));
      var button = el(doc, "button", "mission-button");
      button.type = "button";
      button.dataset.missionId = m.id;
      button.setAttribute("aria-pressed", m.id === selectedId ? "true" : "false");
      button.appendChild(el(doc, "span", "mission-label", C.missionLabel(m)));
      button.appendChild(el(doc, "span", "mission-meta",
        shortId(m.id) + " · révision " + m.revision + " · " + m.status + " / " + m.phase));
      var note = C.cancelNote(m);
      if (note) button.appendChild(el(doc, "span", "mission-note", note));
      li.appendChild(button);
      list.appendChild(li);
    });
  }

  function row(doc, dl, term, value) {
    dl.appendChild(el(doc, "dt", null, term));
    dl.appendChild(el(doc, "dd", null, value));
  }

  function renderDetails(doc, s) {
    var body = byId(doc, "details-body");
    var banner = byId(doc, "reset-banner");
    clear(body);
    var sel = s.list.selection;
    if (!sel) {
      banner.hidden = true;
      body.appendChild(el(doc, "p", "empty", "Sélectionner une mission dans la liste."));
      return;
    }
    var sync = sel.sync;
    banner.hidden = !sync.reset;
    byId(doc, "reset-text").textContent = sync.reset
      ? "Rattrapage impossible (" + sync.reset.reason + "). L'affichage reste celui d'avant tant que la capture n'est pas rechargée explicitement."
      : "";
    if (!sync.view) {
      body.appendChild(el(doc, "p", "empty", sync.lastError
        ? "Aucune capture : erreur Core " + sync.lastError + "."
        : "Capture demandée pour " + sel.missionId + "…"));
      return;
    }
    var m = sync.view.mission;
    var sum = C.syncSummary(sync);
    var stale = s.phase !== "connected";
    body.appendChild(el(doc, "p", "mission-title", C.missionLabel(m)));
    if (stale) body.appendChild(el(doc, "p", "stale-note", "Capture périmée : connexion interrompue."));
    var note = C.cancelNote(m);
    if (note) body.appendChild(el(doc, "p", "mission-note", note));
    var dl = el(doc, "dl", "fields");
    row(doc, dl, "Mission", m.id);
    row(doc, dl, "Statut / phase", m.status + " / " + m.phase);
    row(doc, dl, "Révision", m.revision);
    row(doc, dl, "Progression", m.progress.completed + " / " + (m.progress.total === null ? "inconnu" : m.progress.total));
    row(doc, dl, "Objectif", m.objective_kind === null ? "hors catalogue" : m.objective_kind);
    row(doc, dl, "Issue", m.outcome_status);
    if (m.action_view) {
      row(doc, dl, "Décision", m.action_view.decision.status + " — " + m.action_view.decision.message);
      row(doc, dl, "Applicabilité", m.action_view.applicability.code + " — " + m.action_view.applicability.message);
      row(doc, dl, "Effet", m.action_view.effect.code + " — " + m.action_view.effect.message);
    }
    row(doc, dl, "Capture Core", fmt(sync.view.observedAt) + " (séquence " + sync.view.asOf + ")");
    row(doc, dl, "Reçue à", fmt(sync.view.receivedAt));
    row(doc, dl, "Journal lu jusqu'à", sum.cursorSequence === null ? "—" : "séquence " + sum.cursorSequence
      + (sum.catchingUp ? " (rattrapage en cours)" : ""));
    if (sync.lastError) row(doc, dl, "Dernière erreur Core", sync.lastError);
    body.appendChild(dl);
    body.appendChild(el(doc, "h3", null, "Événements reçus depuis la sélection"));
    if (!sync.refs.length) {
      body.appendChild(el(doc, "p", "empty", "Aucun nouvel événement depuis la capture."));
    } else {
      var ol = el(doc, "ol", "events");
      sync.refs.slice(-20).forEach(function (e) {
        ol.appendChild(el(doc, "li", null, "#" + e.sequence + " · " + e.kind + " · " + fmt(e.at)));
      });
      body.appendChild(ol);
    }
  }

  function render(doc, s) {
    renderConnection(doc, s);
    renderList(doc, s);
    renderDetails(doc, s);
  }

  var api = { render: render, PHASES: PHASES };
  if (NODE) module.exports = api;
  else root.EidolonConnectedView = api;
})(typeof window !== "undefined" ? window : this);
