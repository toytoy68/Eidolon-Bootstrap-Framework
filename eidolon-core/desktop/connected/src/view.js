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
    busy: "Serveur occupé (BUSY) : la dernière demande n'a pas été traitée. L'affichage date de la dernière lecture acceptée ; réessayer avec « Actualiser » ou « Relire la liste ».",
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
    var online = s.phase === "connected" || s.phase === "busy";   // explicit retries allowed when busy
    var status = byId(doc, "connection-status");
    status.textContent = s.phase === "busy" && s.problem && s.problem.code === "STATE_BUSY"
      ? "Stockage Core occupé : la lecture n’a pas abouti. L’affichage conserve la dernière lecture acceptée ; réessayez explicitement."
      : PHASES[s.phase] || s.phase;
    status.className = "status phase-" + s.phase;
    var parts = [];
    if (s.storeId) parts.push("Base " + s.storeId);
    parts.push("Dernière lecture acceptée : " + (s.lastSuccessAt ? fmt(s.lastSuccessAt) : "aucune"));
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
    var text = summary.status + (!stale ? "" : s.phase === "busy" ? " — non actualisé (serveur occupé)" : " — périmé (hors connexion)");
    if (s.list.lastError) text += " — erreur Core : " + s.list.lastError;
    byId(doc, "list-status").textContent = s.phase === "disconnected" ? "" : text;
    var list = byId(doc, "mission-list");
    // G037: the buttons are rebuilt on every render; keep the keyboard focus on the same mission.
    var active = doc.activeElement;
    var focusedId = active && active.dataset && list.contains(active) ? active.dataset.missionId : null;
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
      if (m.id === focusedId) button.focus();
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
    if (stale) body.appendChild(el(doc, "p", "stale-note", s.phase === "busy"
      ? "Capture non actualisée : serveur ou stockage occupé, aucune nouvelle lecture acceptée."
      : "Capture périmée : connexion interrompue."));
    else if (!C.viewIsCurrent(s)) {
      // G043: a pending reset or a refused answer means the shown capture is not the current state.
      body.appendChild(el(doc, "p", "stale-note", sync.reset
        ? "Capture figée : rattrapage impossible, elle ne représente plus l'état actuel."
        : "Capture non actualisée : la dernière réponse a été refusée (" + sync.lastError + ")."));
    }
    var note = C.cancelNote(m);
    if (note) body.appendChild(el(doc, "p", "mission-note", note));
    var research = C.researchNote(m);
    if (research) body.appendChild(el(doc, "p", "mission-note research-note", research));
    var dl = el(doc, "dl", "fields");
    row(doc, dl, "Mission", m.id);
    row(doc, dl, "Statut / phase", m.status + " / " + m.phase);
    row(doc, dl, "Révision", m.revision);
    row(doc, dl, "Progression", m.progress.completed + " / " + (m.progress.total === null ? "inconnu" : m.progress.total));
    row(doc, dl, "Objectif", C.objectiveLabel(m.objective_kind));
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

  var RECEIPT_ERRORS = {
    INVALID_QUERY: "Identifiant client ou clé invalide : 1 à 80 caractères A-Z, a-z, 0-9, « _ », « . », « - », commençant par une lettre ou un chiffre. Rien n'a été envoyé.",
    INVALID_RECEIPT_QUERY: "Requête refusée par Core (identifiants invalides).",
    STORE_CHANGED: "La base n'a plus l'identité affichée : se reconnecter pour resynchroniser. Aucun renvoi.",
    RECEIPT_MISSION_MISMATCH: "Cette clé existe mais pour une autre mission : aucune conclusion automatique.",
    RECEIPT_UNAVAILABLE: "Reçu illisible ou incohérent dans la base : l'incertitude reste entière.",
    INVALID_BINDING: "Contrôle de liaison inconnu annoncé par Core : reçu non affiché, aucune conclusion."
  };

  // G048: what Core checked between the receipt and its journal event. Never a signature,
  // never evidence that an action ran or stopped; an absent field is not EVENT_HASH.
  var BINDINGS = {
    EVENT_HASH: "Liaison au journal vérifiée par Core à cette lecture (empreinte du reçu dans l'événement). "
      + "Ce n'est ni une signature ni une preuve d'exécution : une réécriture cohérente de la base resterait invisible.",
    LEGACY_FIELDS: "Contrôle limité (ancien format, sans empreinte) : seuls certains champs sont recoupés avec le journal. "
      + "Pour une annulation, le statut de mission, la révision et l'indicateur enregistrés ne sont pas couverts."
  };
  var BINDING_UNSPECIFIED = "Non précisé par ce serveur Core (version antérieure) : aucun contrôle de liaison annoncé.";
  function bindingText(binding) {
    return Object.prototype.hasOwnProperty.call(BINDINGS, binding) ? BINDINGS[binding] : BINDING_UNSPECIFIED;
  }

  // The receipt is a dated record. It is shown next to the current capture, never merged into it.
  function renderReceipt(doc, s) {
    var section = byId(doc, "receipt");
    var sel = s.list.selection;
    section.hidden = !sel;
    byId(doc, "receipt-lookup").disabled = s.phase !== "connected" || s.resyncRequired || !sel;
    var out = byId(doc, "receipt-result");
    clear(out);
    var rec = s.receipt;
    if (!sel || !rec) return;
    if (rec.status === "PENDING") { out.appendChild(el(doc, "p", "empty", "Consultation en cours…")); return; }
    if (rec.status === "ERROR" || rec.status === "INVALID_QUERY") {
      out.appendChild(el(doc, "p", "receipt-error", RECEIPT_ERRORS[rec.code] || ("Réponse non exploitable : " + rec.code + ". Aucune conclusion.")));
      return;
    }
    if (rec.status === "NOT_FOUND") {
      out.appendChild(el(doc, "p", "receipt-missing", "Aucun reçu pour la clé « " + rec.query.command_key + " » dans cette base, à cette lecture ("
        + fmt(rec.receivedAt) + "). Cela ne prouve pas que la commande n'est jamais partie : ne pas la renvoyer sur cette seule base."));
      return;
    }
    var r = rec.receipt;
    var kind = C.RECEIPT_KINDS[r.protocol];
    out.appendChild(el(doc, "p", "receipt-found", "Enregistrement historique trouvé — "
      + (kind === "decision" ? "décision « " + r.decision + " »" : "demande d'annulation")
      + ". Ce n'est pas l'état actuel et ce n'est pas une preuve d'effet."));
    var dl = el(doc, "dl", "fields");
    row(doc, dl, "Enregistré le", fmt(r.recorded_at));
    row(doc, dl, "Statut du reçu", r.status);
    if (kind === "decision") row(doc, dl, "Accord à l'enregistrement", r.approval_status_at_recording);
    else {
      row(doc, dl, "Annulation", r.cancel_outcome);
      row(doc, dl, "Mission à l'enregistrement", r.mission_status_at_recording);
    }
    row(doc, dl, "Révision à l'enregistrement", r.mission_revision);
    row(doc, dl, "Événement", "séquence " + r.event_sequence);
    row(doc, dl, "Contrôle d'intégrité", bindingText(rec.binding));
    var view = sel.sync && sel.sync.view;
    if (view) {
      var m = view.mission;
      var now = kind === "decision" ? (m.action_view ? m.action_view.decision.status : "aucune proposition") : m.status;
      row(doc, dl, "Capture actuelle", now + " (capture du " + fmt(view.observedAt) + ")");
    }
    out.appendChild(dl);
  }

  // G066: catalog metadata only. Nothing here opens, downloads, deletes or restores an archive.
  var ARCHIVE_CODES = {
    ARCHIVES_NOT_CONFIGURED: "Aucun dossier d'archives n'est configuré pour ce serveur Core (option --research-archives).",
    ARCHIVES_BUSY: "Une autre lecture des archives est en cours sur le serveur : réessayer plus tard. Rien n'est relancé automatiquement.",
    ARCHIVES_UNAVAILABLE: "Catalogue refusé ou illisible côté Core : aucune liste partielle n'est présentée comme actuelle.",
    INVALID_ARCHIVE_CURSOR: "Position de page refusée par Core : recharger les archives.",
    STORE_CHANGED: "La base Core a changé depuis la première page : recharger les archives.",
    CATALOG_CHANGED: "Le catalogue a changé depuis la première page : recharger les archives pour une liste cohérente.",
    STORE_MISMATCH: "Réponse d'une autre base Core que celle de la connexion : ignorée.",
    CATALOG_MISMATCH: "Page d'un autre catalogue que la première : ignorée, les deux ne sont jamais mélangées.",
    PAGE_GAP: "Page non contiguë à la précédente : ignorée.",
    AUTHORITY_CLAIMED: "Réponse annonçant une garantie ou un droit que Core ne donne pas : ignorée."
  };

  function archiveMessage(code) {
    return ARCHIVE_CODES[code] || ("Réponse non exploitable (" + code + ") : aucune conclusion.");
  }

  function dateMs(ms) {
    var d = new Date(ms);
    return isNaN(d.getTime()) ? String(ms) : d.toLocaleString("fr-FR");
  }

  function renderArchives(doc, s) {
    var a = s.archives;
    var online = s.phase === "connected" || s.phase === "busy";
    var loading = a.status === "loading";
    var load = byId(doc, "archives-load");
    load.disabled = !online || loading || !s.storeId || s.resyncRequired;
    load.textContent = a.catalog ? "Actualiser les archives" : "Charger les archives";
    byId(doc, "archives-more").disabled = !online || loading || a.stale || !a.hasMore;
    var sum = C.archiveSummary(a);
    var parts = [];
    if (s.phase === "disconnected") parts.push("");
    else if (loading) parts.push("Lecture du catalogue en cours…");
    else if (!a.catalog && a.status === "empty") parts.push("Catalogue non chargé : lecture sur demande uniquement.");
    if (a.catalog) {
      parts.push(sum.shown + " archive(s) affichée(s) sur " + sum.total + " ; " + sum.runs + " recherche(s) au total"
        + (sum.complete ? "." : " — liste incomplète, page suivante disponible."));
      parts.push("Catalogue lu par Core le " + fmt(a.catalog.observedAt) + ", reçu le " + fmt(a.catalog.receivedAt) + ".");
    }
    if (a.code) parts.push(archiveMessage(a.code));
    if (a.stale && online) parts.push("Liste figée : elle ne représente plus forcément le catalogue actuel.");
    else if (a.stale) parts.push("Liste périmée : connexion interrompue.");
    byId(doc, "archives-status").textContent = parts.filter(Boolean).join(" ");
    var body = byId(doc, "archives-body");
    clear(body);
    if (!a.items.length) {
      if (a.catalog && !a.stale) body.appendChild(el(doc, "p", "empty", "Aucune archive dans ce catalogue."));
      return;
    }
    var wrap = el(doc, "div", "table-wrap" + (a.stale ? " stale" : ""));
    // Small screens scroll this region horizontally: reachable and named for keyboard users.
    wrap.tabIndex = 0;
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", "Tableau des archives, défilement horizontal possible");
    var table = el(doc, "table", "archives-table");
    table.appendChild(el(doc, "caption", null, a.stale ? "Archives (liste figée)" : "Archives"));
    var head = el(doc, "tr");
    ["Archive", "Créée le", "Recherches", "Avec texte nettoyé", "Sans texte (historique)", "Liées à une mission"].forEach(function (h) {
      var th = el(doc, "th", null, h);
      th.scope = "col";
      head.appendChild(th);
    });
    var thead = el(doc, "thead");
    thead.appendChild(head);
    table.appendChild(thead);
    var tbody = el(doc, "tbody");
    a.items.forEach(function (it) {
      var tr = el(doc, "tr");
      var th = el(doc, "th", "archive-file", it.file);
      th.scope = "row";
      th.title = "Empreinte " + it.sha256;
      tr.appendChild(th);
      [dateMs(it.created_at_ms), it.count, it.queries_with_text, it.legacy_runs_without_text, it.linked_missions].forEach(function (v) {
        tr.appendChild(el(doc, "td", null, v));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    body.appendChild(wrap);
  }

  function render(doc, s) {
    renderConnection(doc, s);
    renderList(doc, s);
    renderDetails(doc, s);
    renderReceipt(doc, s);
    renderArchives(doc, s);
  }

  var api = { render: render, PHASES: PHASES, bindingText: bindingText, archiveMessage: archiveMessage };
  if (NODE) module.exports = api;
  else root.EidolonConnectedView = api;
})(typeof window !== "undefined" ? window : this);
