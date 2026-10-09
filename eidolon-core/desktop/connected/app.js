/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : app.js
 * Description : FICHIER GÉNÉRÉ par build.js — ne pas modifier à la main (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/* ---- ../prototype/sync-state.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : sync-state.js
 * Description : Consommateur pur du protocole eidolon-client-sync/1 (C-TASK-G012)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Pure functions over local JSON envelopes. No fetch, timer, storage or OS call:
 * the caller (a future transport, or the prototype bench) hands each response
 * here together with what IT asked for. Nothing in this file can decide, run or
 * cancel anything: the protocol says authorizes_execution=false and so do we.
 *
 * Two progressions are kept apart (docs/CLIENT-SYNC.md):
 *   - view   : the latest mission capture, ordered by snapshot.as_of_sequence;
 *   - cursor : the last event reference delivered, which may lag behind the view.
 * Event references are history, never patches applied to the view.
 */
(function (root) {
  "use strict";

  var PROTOCOL = "eidolon-client-sync/1";
  var STATUSES = { SNAPSHOT: true, DELTA: true, RESET_REQUIRED: true };
  var RESET_REASONS = { STORE_CHANGED: true, CURSOR_AHEAD: true, ANCHOR_CHANGED: true, HISTORY_CHANGED: true };
  var CURSOR_FIELDS = ["anchor_sha256", "event_count", "mission_id", "sequence", "store_id", "version"];
  var MAX_REFS = 200;          // bounded RAM: older references are dropped and counted
  var MAX_REJECTIONS = 20;

  function clone(v) { return JSON.parse(JSON.stringify(v)); }
  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function safeInt(v, min) { return Number.isSafeInteger(v) && v >= (min === undefined ? 0 : min); }
  function text(v, max) { return typeof v === "string" && v.length <= max; }

  function createState() {
    return {
      protocol: PROTOCOL,
      storeId: null, missionId: null,
      epoch: 0,               // bumped by every explicit reload; older in-flight answers are ignored
      view: null,             // { asOf, observedAt, eventCount, mission, receivedAt }
      cursor: null,           // last delivered cursor (exact object from Core)
      hasMore: false,
      refs: [],               // [{ sequence, at, kind }] ascending, at most MAX_REFS
      droppedRefs: 0,
      reset: null,            // { reason, snapshot, cursor, receivedAt } awaiting an explicit reload
      connection: "online",
      lastContactAt: null,    // local reception time of the last accepted envelope
      lastError: null,        // last Core error code (INVALID_CURSOR, ...), never a capture
      stats: { duplicateRefs: 0, staleViews: 0, staleAnswers: 0, gapAnswers: 0, frozenAnswers: 0, supersededResets: 0, rejected: [], coreErrors: [] }
    };
  }

  // ---- validation (structure only; it never repairs a value) --------------------------------

  function validateCursor(cursor, storeId, missionId) {
    if (!isObject(cursor)) return "INVALID_CURSOR";
    var keys = Object.keys(cursor).sort();
    if (keys.join() !== CURSOR_FIELDS.join()) return "INVALID_CURSOR";
    if (cursor.version !== 1) return "UNSUPPORTED_CURSOR_VERSION";
    if (!safeInt(cursor.sequence, 1) || !safeInt(cursor.event_count, 1) || cursor.event_count > cursor.sequence) return "UNSAFE_OR_INVALID_INTEGER";
    if (!/^[0-9a-f]{64}$/.test(cursor.anchor_sha256)) return "INVALID_CURSOR";
    if (cursor.store_id !== storeId) return "CURSOR_STORE_MISMATCH";
    if (cursor.mission_id !== missionId) return "CURSOR_MISSION_MISMATCH";
    return null;
  }

  function validateActionView(av) {
    if (av === null) return null; // e.g. text.stats: no proposal, no decision to show
    if (!isObject(av) || av.authorizes_execution !== false || av.snapshot_only !== true) return "INVALID_ACTION_VIEW";
    var parts = ["decision", "applicability", "effect"];
    for (var i = 0; i < parts.length; i++) {
      var p = av[parts[i]];
      if (!isObject(p) || !text(p[parts[i] === "decision" ? "status" : "code"], 64) || !text(p.message, 500)) return "INVALID_ACTION_VIEW";
    }
    return null;
  }

  // Mission projection shared by client-sync/1 and mission-list/1 (same Core project_mission).
  function validateMission(m) {
    if (!isObject(m) || !text(m.id, 80) || !m.id || !safeInt(m.revision, 0) || !text(m.status, 40) || !text(m.phase, 40)
        || typeof m.cancel_requested !== "boolean" || !(m.objective_kind === null || text(m.objective_kind, 80)) // null: no catalogue objective (G016)
        || !text(m.outcome_status, 40)
        || !isObject(m.progress) || !safeInt(m.progress.completed, 0)
        || !(m.progress.total === null || safeInt(m.progress.total, 0))) return "INVALID_MISSION";
    return validateActionView(m.action_view);
  }

  function validateEnvelope(env) {
    if (!isObject(env)) return "NOT_AN_OBJECT";
    if (env.protocol !== PROTOCOL) return "UNSUPPORTED_PROTOCOL";
    if (env.snapshot_only !== true || env.authorizes_execution !== false) return "AUTHORITY_CLAIMED";
    if (!STATUSES[env.status]) return "UNKNOWN_STATUS";
    if (!/^s-[0-9a-f]{32}$/.test(env.store_id) || !text(env.mission_id, 80) || !env.mission_id) return "INVALID_IDENTITY";
    if (env.status === "RESET_REQUIRED" && !RESET_REASONS[env.reason]) return "UNKNOWN_RESET_REASON";
    var snap = env.snapshot;
    if (isObject(snap) && [snap.as_of_sequence, snap.event_count, isObject(snap.mission) ? snap.mission.revision : 0]
        .some(function (v) { return typeof v === "number" && Number.isInteger(v) && !Number.isSafeInteger(v); })) return "UNSAFE_OR_INVALID_INTEGER";
    if (!isObject(snap) || !safeInt(snap.as_of_sequence, 1) || !safeInt(snap.event_count, 1) || !text(snap.observed_at, 64)) return "INVALID_SNAPSHOT";
    var m = snap.mission;
    var bad = validateMission(m);
    if (bad) return bad;
    if (m.id !== env.mission_id) return "INVALID_MISSION";
    var cur = validateCursor(env.cursor, env.store_id, env.mission_id);
    if (cur) return cur;
    if (env.cursor.sequence > snap.as_of_sequence) return "CURSOR_AFTER_SNAPSHOT";
    if (typeof env.has_more !== "boolean" || !Array.isArray(env.events) || env.events.length > 100) return "INVALID_EVENTS";
    var previous = 0;
    for (var i = 0; i < env.events.length; i++) {
      var e = env.events[i];
      if (!isObject(e) || !safeInt(e.sequence, 1) || e.sequence <= previous || !text(e.kind, 64) || !e.kind || !text(e.at, 64)) return "INVALID_EVENTS";
      previous = e.sequence;
    }
    if (env.status === "DELTA" && env.events.length && env.cursor.sequence !== previous) return "CURSOR_NOT_LAST_EVENT";
    if (env.status !== "DELTA" && env.events.length) return "INVALID_EVENTS";
    return null;
  }

  function reject(state, code, receivedAt) {
    state.stats.rejected.push({ code: code, at: receivedAt || null });
    if (state.stats.rejected.length > MAX_REJECTIONS) state.stats.rejected.shift();
    return state;
  }

  // ---- receiving ------------------------------------------------------------------------------

  /*
   * receive(state, envelope, request) -> new state.
   * request = { kind: "snapshot" | "poll", epoch, cursorSequence, receivedAt }
   * describes what the caller asked; Core's envelope does not echo it.
   */
  function receive(state, env, request) {
    var s = clone(state);
    request = request || {};
    var code = validateEnvelope(env);
    if (code) return reject(s, code, request.receivedAt);
    if (s.missionId && (env.mission_id !== s.missionId)) return reject(s, "MISSION_MISMATCH", request.receivedAt);
    if (request.epoch !== s.epoch) { s.stats.staleAnswers += 1; return s; } // asked before a reload
    if (s.connection !== "online") { s.stats.staleAnswers += 1; return s; } // nothing applied while offline

    if (env.status === "RESET_REQUIRED") {
      // Never applied silently: the user reloads explicitly. Polling stops meanwhile.
      // A later reset replaces the pending one (newest reason and capture); still not applied.
      if (s.reset) s.stats.supersededResets += 1;
      s.reset = { reason: env.reason, snapshot: clone(env.snapshot), cursor: clone(env.cursor), receivedAt: request.receivedAt || null };
      s.lastContactAt = request.receivedAt || s.lastContactAt;
      s.lastError = null;
      return s;
    }
    if (s.reset) { s.stats.frozenAnswers += 1; return s; } // G016: view and cursor frozen until the explicit reload
    if (s.storeId && env.store_id !== s.storeId) return reject(s, "STORE_CHANGED_WITHOUT_RESET", request.receivedAt);

    if (env.status === "SNAPSHOT") {
      if (s.cursor) {
        // A plain snapshot while a cursor exists only refreshes the view; it never moves the cursor.
        takeView(s, env.snapshot, request.receivedAt);
      } else {
        s.storeId = env.store_id; s.missionId = env.mission_id;
        s.cursor = clone(env.cursor);
        takeView(s, env.snapshot, request.receivedAt);
      }
    } else { // DELTA
      if (!s.cursor) return reject(s, "DELTA_WITHOUT_CURSOR", request.receivedAt);
      // Sequences may jump (other missions), but event_count may not: a page whose first
      // event is not right after our cursor would leave a hole. Its capture is still a
      // capture; its references and cursor are not taken.
      var startCount = env.cursor.event_count - env.events.length;
      if (env.events.length && startCount > s.cursor.event_count) {
        s.stats.gapAnswers += 1;
        takeView(s, env.snapshot, request.receivedAt);
        s.lastContactAt = request.receivedAt || s.lastContactAt;
        return s;
      }
      env.events.forEach(function (e) { addRef(s, e); });
      if (env.cursor.sequence > s.cursor.sequence) {
        s.cursor = clone(env.cursor);
        s.hasMore = env.has_more;
      } else if (env.cursor.sequence === s.cursor.sequence && env.cursor.anchor_sha256 === s.cursor.anchor_sha256) {
        s.hasMore = env.has_more; // nothing new after our cursor
      } else {
        s.stats.staleAnswers += 1; // an older answer never moves the cursor back
      }
      takeView(s, env.snapshot, request.receivedAt);
    }
    s.lastContactAt = request.receivedAt || s.lastContactAt;
    s.lastError = null;
    return s;
  }

  function takeView(s, snap, receivedAt) {
    if (s.view && snap.as_of_sequence <= s.view.asOf) { s.stats.staleViews += 1; return; }
    s.view = { asOf: snap.as_of_sequence, observedAt: snap.observed_at, eventCount: snap.event_count,
      mission: clone(snap.mission), receivedAt: receivedAt || null };
  }

  function addRef(s, e) {
    var last = s.refs.length ? s.refs[s.refs.length - 1].sequence : 0;
    if (e.sequence <= s.cursor.sequence || e.sequence <= last) { s.stats.duplicateRefs += 1; return; }
    s.refs.push({ sequence: e.sequence, at: e.at, kind: e.kind });
    if (s.refs.length > MAX_REFS) { s.refs.shift(); s.droppedRefs += 1; }
  }

  // A Core error (INVALID_CURSOR, CURSOR_MISSION_MISMATCH, ...) is recorded; no capture is claimed.
  function receiveError(state, errorCode, request) {
    var s = clone(state);
    if ((request || {}).epoch !== s.epoch) { s.stats.staleAnswers += 1; return s; }
    s.lastError = text(errorCode, 64) ? errorCode : "UNKNOWN_ERROR";
    s.stats.coreErrors.push({ code: s.lastError, at: (request || {}).receivedAt || null });
    if (s.stats.coreErrors.length > MAX_REJECTIONS) s.stats.coreErrors.shift();
    return s;
  }

  // ---- explicit user actions and connectivity --------------------------------------------------

  function acceptReset(state) {
    var s = clone(state);
    if (!s.reset) return s;
    s.storeId = s.reset.cursor.store_id;
    s.cursor = clone(s.reset.cursor);
    s.view = { asOf: s.reset.snapshot.as_of_sequence, observedAt: s.reset.snapshot.observed_at,
      eventCount: s.reset.snapshot.event_count, mission: clone(s.reset.snapshot.mission), receivedAt: s.reset.receivedAt };
    s.refs = []; s.droppedRefs = 0; s.hasMore = false;
    s.reset = null;
    s.epoch += 1;
    return s;
  }

  function setConnection(state, connection) {
    var s = clone(state);
    s.connection = connection === "online" ? "online" : "offline";
    return s;
  }

  // What the transport may ask next. Never a command: only reads.
  function nextRequest(state) {
    if (state.connection !== "online" || state.reset) return null;
    if (!state.cursor) return { kind: "snapshot", epoch: state.epoch, cursorSequence: null };
    return { kind: "poll", epoch: state.epoch, cursorSequence: state.cursor.sequence, cursor: clone(state.cursor) };
  }

  // ---- presentation (labels only; Core values stay the source) --------------------------------

  // G060: readable names for catalogue objectives; an unknown kind stays shown as received.
  var RESEARCH = "research_retrieval.synthetic";
  var OBJECTIVES = { "research_retrieval.synthetic": "Recherche synthétique (pages fixes)" };
  function objectiveLabel(kind) {
    if (kind === null) return "hors catalogue";
    return Object.prototype.hasOwnProperty.call(OBJECTIVES, kind) ? OBJECTIVES[kind] : kind;
  }

  // What the projection says about a research mission: retrieval of fixed synthetic pages,
  // never the truth of their content. The query and the pages are NOT in the projection.
  function researchNote(mission) {
    if (!mission || mission.objective_kind !== RESEARCH) return null;
    switch (mission.outcome_status) {
      case "ACHIEVED": return "Récupération synthétique complète : les pages fixes demandées ont été lues et vérifiées. Ce n'est pas une information confirmée.";
      case "PARTIAL": return "Récupération partielle : moins de pages que demandé. Preuves conservées dans Core ; objectif non atteint.";
      case "NOT_ACHIEVED": return "Aucune page vérifiée : pas de preuve de récupération à cette capture.";
      default: return "Issue " + mission.outcome_status + " : non interprétée par ce client.";
    }
  }

  function missionLabel(mission) {
    if (!mission) return "Aucune capture";
    var av = mission.action_view;
    var research = mission.objective_kind === RESEARCH;
    if (mission.status === "REVIEW_REQUIRED") return "Revue requise — effet à vérifier"; // stays primary, even with a cancel request
    if (mission.cancel_requested && !/^(CANCELLED|SUCCEEDED|FAILED|ABANDONED)$/.test(mission.status)) return "Annulation demandée — issue non confirmée";
    switch (mission.status) {
      case "NEW": return "Nouvelle";
      case "RUNNING": return "En cours (capture ; ne prouve pas qu'un processus vit encore)";
      case "BLOCKED":
        if (av && av.decision.status === "PENDING" && av.applicability.code === "AWAITING_DECISION") return "À décider";
        if (mission.outcome_status === "CLARIFICATION") return "Bloquée — précision demandée";
        if (research && mission.outcome_status === "PARTIAL") return "Bloquée — récupération partielle";
        if (research && mission.outcome_status === "NOT_ACHIEVED") return "Bloquée — aucune page vérifiée";
        return "Bloquée — motif à consulter";
      case "REVIEW_REQUIRED": return "Revue requise — effet à vérifier";
      case "SUCCEEDED":
        if (research && mission.outcome_status === "ACHIEVED") return "Réussie — pages synthétiques récupérées";
        return mission.outcome_status === "ACHIEVED" ? "Réussie — résultat daté" : "Terminée (issue " + mission.outcome_status + ")";
      case "FAILED": return "Échouée";
      case "CANCELLED": return "Annulée";
      case "ABANDONED": return "Abandonnée";
      default: return "État " + mission.status;
    }
  }

  // Secondary line, shown next to the main label; never a promise of a future outcome.
  function cancelNote(mission) {
    if (!mission || !mission.cancel_requested) return null;
    if (/^(CANCELLED|SUCCEEDED|FAILED|ABANDONED)$/.test(mission.status)) return "Annulation demandée avant la fin ; issue capturée : " + mission.status;
    return "Annulation demandée : enregistrée, issue non garantie";
  }

  function summary(state) {
    return {
      hasView: Boolean(state.view),
      label: missionLabel(state.view && state.view.mission),
      viewAsOf: state.view ? state.view.asOf : null,
      cursorSequence: state.cursor ? state.cursor.sequence : null,
      catchingUp: Boolean(state.view && state.cursor && state.cursor.sequence < state.view.asOf),
      resetPending: Boolean(state.reset),
      refs: state.refs.length
    };
  }

  var api = { PROTOCOL: PROTOCOL, MAX_REFS: MAX_REFS, createState: createState, validateEnvelope: validateEnvelope, validateMission: validateMission,
    receive: receive, receiveError: receiveError, acceptReset: acceptReset, setConnection: setConnection,
    nextRequest: nextRequest, missionLabel: missionLabel, cancelNote: cancelNote, summary: summary,
    objectiveLabel: objectiveLabel, researchNote: researchNote };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonSync = api;
})(typeof window !== "undefined" ? window : this);

/* ---- ../prototype/mission-list-state.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : mission-list-state.js
 * Description : Consommateur pur du protocole eidolon-mission-list/1 (C-TASK-G018)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Pure functions over local JSON pages (docs/MISSION-LIST.md). No fetch, timer,
 * storage or OS call. The caller hands each answer with what IT asked for.
 *
 * - One inventory = pages of ONE generation of ONE store. A page of another
 *   generation is never merged; RESET_REQUIRED keeps the old inventory, marked
 *   stale, and nothing more is asked until the user explicitly lists again.
 * - The list cursor (next_cursor) is only ever sent back unchanged to the list.
 *   It is never turned into a client-sync/1 event cursor.
 * - Selecting a mission only asks for a client-sync/1 snapshot of that id
 *   (sync-state.js). An answer for an older selection never replaces the shown one.
 * Nothing here can decide, run or cancel: authorizes_execution=false everywhere.
 */
(function (root) {
  "use strict";
  var S = (typeof module === "object" && module.exports) ? require("./sync-state.js") : root.EidolonSync;

  var PROTOCOL = "eidolon-mission-list/1";
  var MAX_ITEMS = 200;          // visible total bound; beyond it the inventory says it is truncated
  var MAX_PAGE_ITEMS = 100;     // Core's own page bound
  var MAX_REJECTIONS = 20;
  var GENERATION_FIELDS = ["anchor_sha256", "event_count", "mission_count", "sequence"];
  var CURSOR_FIELDS = ["after_id", "generation", "store_id", "version"];
  var RESET_REASONS = { STORE_CHANGED: true, STATE_CHANGED: true };
  var MISSION_ID = /^m-[0-9a-f]{32}$/, STORE_ID = /^s-[0-9a-f]{32}$/, HEX64 = /^[0-9a-f]{64}$/;

  function clone(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }
  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function safeInt(v, min) { return Number.isSafeInteger(v) && v >= (min === undefined ? 0 : min); }
  function text(v, max) { return typeof v === "string" && v.length <= max; }
  function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); } // fields are compared after key checks
  function sortedKeys(o) { return Object.keys(o).sort().join(); }

  function createState() {
    return {
      protocol: PROTOCOL,
      epoch: 0,                 // bumped by every explicit relisting; older in-flight answers are ignored
      connection: "online",
      storeId: null, generation: null,
      items: [],                // [{ asOf, mission, source }] ascending by id, one generation only
      complete: false,          // has_more=false received for this generation
      truncated: false,         // MAX_ITEMS reached before the end: never claimed complete
      nextCursor: null,         // exact list cursor from Core, sent back unchanged
      pages: 0,
      stale: null,              // { reason, receivedAt } after RESET_REQUIRED: items are an OLD inventory
      received: 0,              // items received for this generation, including those beyond MAX_ITEMS
      halted: null,             // { code, receivedAt }: counts contradicted the announced total (G021)
      previous: null,           // { items, reason } kept, marked stale, while a new listing is assembled
      lastContactAt: null, lastError: null,
      selection: null,          // { missionId, token, sync, source }
      selectionToken: 0,
      stats: { staleAnswers: 0, repeatedPages: 0, staleSelections: 0, frozenAnswers: 0, rejected: [], coreErrors: [] }
    };
  }

  // ---- validation (structure only; it never repairs a value) --------------------------------

  function validateGeneration(g) {
    if (!isObject(g) || sortedKeys(g) !== GENERATION_FIELDS.join()) return "INVALID_GENERATION";
    if (!safeInt(g.sequence) || !safeInt(g.event_count) || !safeInt(g.mission_count)) return "UNSAFE_OR_INVALID_INTEGER";
    if (g.event_count > g.sequence || g.mission_count > g.event_count) return "INVALID_GENERATION";
    if (g.sequence === 0 ? g.anchor_sha256 !== null : !HEX64.test(g.anchor_sha256)) return "INVALID_GENERATION";
    return null;
  }

  function validateListCursor(c, storeId, generation) {
    if (!isObject(c) || sortedKeys(c) !== CURSOR_FIELDS.join()) return "INVALID_LIST_CURSOR";
    if (c.version !== 1 || !MISSION_ID.test(c.after_id) || c.store_id !== storeId) return "INVALID_LIST_CURSOR";
    if (validateGeneration(c.generation) || !same(c.generation, generation)) return "INVALID_LIST_CURSOR";
    return null;
  }

  function validatePage(env) {
    if (!isObject(env)) return "NOT_AN_OBJECT";
    if (env.protocol !== PROTOCOL) return "UNSUPPORTED_PROTOCOL";
    if (env.snapshot_only !== true || env.authorizes_execution !== false) return "AUTHORITY_CLAIMED";
    if (env.status !== "PAGE" && env.status !== "RESET_REQUIRED") return "UNKNOWN_STATUS";
    if (!STORE_ID.test(env.store_id) || !text(env.observed_at, 64)) return "INVALID_IDENTITY";
    var g = validateGeneration(env.generation);
    if (g) return g;
    if (typeof env.has_more !== "boolean" || !Array.isArray(env.items) || env.items.length > MAX_PAGE_ITEMS) return "INVALID_ITEMS";
    if (env.status === "RESET_REQUIRED") {
      if (!RESET_REASONS[env.reason]) return "UNKNOWN_RESET_REASON";
      if (env.items.length || env.has_more || env.next_cursor !== null) return "INVALID_RESET";
      return null;
    }
    if ("reason" in env) return "INVALID_ITEMS";
    var previous = "";
    for (var i = 0; i < env.items.length; i++) {
      var it = env.items[i];
      if (!isObject(it) || sortedKeys(it) !== "as_of_sequence,mission") return "INVALID_ITEMS";
      if (Number.isInteger(it.as_of_sequence) && !Number.isSafeInteger(it.as_of_sequence)) return "UNSAFE_OR_INVALID_INTEGER";
      if (!safeInt(it.as_of_sequence, 1) || it.as_of_sequence > env.generation.sequence) return "INVALID_ITEMS";
      var bad = S.validateMission(it.mission);
      if (bad) return bad;
      if (!MISSION_ID.test(it.mission.id) || it.mission.id <= previous) return "ITEMS_NOT_ORDERED";
      previous = it.mission.id;
    }
    if (env.has_more) {
      if (!env.items.length) return "INVALID_ITEMS";
      var c = validateListCursor(env.next_cursor, env.store_id, env.generation);
      if (c) return c;
      if (env.next_cursor.after_id !== previous) return "INVALID_LIST_CURSOR";
    } else if (env.next_cursor !== null) return "INVALID_LIST_CURSOR";
    return null;
  }

  function reject(state, code, at) {
    state.stats.rejected.push({ code: code, at: at || null });
    if (state.stats.rejected.length > MAX_REJECTIONS) state.stats.rejected.shift();
    return state;
  }

  // ---- requests --------------------------------------------------------------------------------

  // The only list request: the first page (cursor null) or the exact next_cursor. Never a command.
  function nextPageRequest(state) {
    if (state.connection !== "online" || state.stale || state.halted || state.complete || state.truncated) return null;
    if (state.pages > 0 && !state.nextCursor) return null;
    return { kind: "list", epoch: state.epoch, cursor: clone(state.nextCursor) };
  }

  // ---- receiving pages -------------------------------------------------------------------------

  /*
   * receivePage(state, page, request) -> new state.
   * request = { kind: "list", epoch, cursor (what was sent), receivedAt, source }
   * source is a provenance label for display ("observé" / "dérivé : ..."), never interpreted.
   */
  function receivePage(state, env, request) {
    var s = clone(state);
    request = request || {};
    var at = request.receivedAt;
    var code = validatePage(env);
    if (code) return reject(s, code, at);
    if (request.epoch !== s.epoch) { s.stats.staleAnswers += 1; return s; }          // asked before a relisting
    if (s.connection !== "online") { s.stats.staleAnswers += 1; return s; }          // nothing applied offline
    if (s.stale || s.halted) { s.stats.frozenAnswers += 1; return s; }               // waiting for an explicit relisting
    if (s.complete || s.truncated) { s.stats.repeatedPages += 1; return s; }
    // Only the answer to the request we are waiting for: a repeated or late page changes nothing.
    if (!same(request.cursor === undefined ? null : request.cursor, s.nextCursor) || (s.pages > 0 && !s.nextCursor)) {
      s.stats.repeatedPages += 1; return s;
    }
    if (env.status === "RESET_REQUIRED") {
      s.stale = { reason: env.reason, receivedAt: at || null };
      s.nextCursor = null;
      s.lastContactAt = at || s.lastContactAt; s.lastError = null;
      return s;
    }
    if (s.pages > 0 && (env.store_id !== s.storeId || !same(env.generation, s.generation))) {
      // Core answers RESET_REQUIRED in that case; a mixed page is refused, never merged.
      return reject(s, "GENERATION_MIXED", at);
    }
    var last = s.items.length ? s.items[s.items.length - 1].mission.id : "";
    if (env.items.length && env.items[0].mission.id <= last) return reject(s, "ITEMS_OVERLAP", at);
    // G021: the announced total (generation.mission_count) binds the whole listing. Checked
    // BEFORE anything is taken: an early end, an overflow or an impossible has_more is refused
    // and stops the listing (explicit relisting needed); nothing is ever declared complete by it.
    var total = env.generation.mission_count, after = s.received + env.items.length;
    var countError = after > total ? "COUNT_EXCEEDED"
      : !env.has_more && after < total ? "LIST_ENDED_EARLY"
      : env.has_more && after >= total ? "HAS_MORE_INCONSISTENT" : null;
    if (countError) {
      s.halted = { code: countError, receivedAt: at || null, announced: total, received: s.received };
      s.nextCursor = null;
      return reject(s, countError, at);
    }
    s.storeId = env.store_id; s.generation = clone(env.generation);
    for (var i = 0; i < env.items.length; i++) {
      if (s.items.length >= MAX_ITEMS) { s.truncated = true; break; }
      s.items.push({ asOf: env.items[i].as_of_sequence, mission: clone(env.items[i].mission),
        source: text(request.source, 80) ? request.source : null });
    }
    s.pages += 1;
    s.received = after;
    s.nextCursor = s.truncated ? null : clone(env.next_cursor);
    s.complete = !s.truncated && !env.has_more;
    if (s.complete) s.previous = null; // the new generation is fully read: the old one is no longer shown
    s.lastContactAt = at || s.lastContactAt; s.lastError = null;
    return s;
  }

  function receiveError(state, errorCode, request) {
    var s = clone(state);
    if ((request || {}).epoch !== s.epoch) { s.stats.staleAnswers += 1; return s; }
    s.lastError = text(errorCode, 64) ? errorCode : "UNKNOWN_ERROR";
    s.stats.coreErrors.push({ code: s.lastError, at: (request || {}).receivedAt || null });
    if (s.stats.coreErrors.length > MAX_REJECTIONS) s.stats.coreErrors.shift();
    return s;
  }

  // ---- explicit user actions and connectivity --------------------------------------------------

  // Explicit "list again": the old inventory stays visible as stale until the new one is complete.
  function relist(state) {
    var s = clone(state);
    if (s.items.length) s.previous = { items: s.items, reason: s.stale ? s.stale.reason : s.halted ? s.halted.code : "RELISTED" };
    s.epoch += 1;
    s.storeId = null; s.generation = null; s.items = []; s.complete = false; s.truncated = false;
    s.nextCursor = null; s.pages = 0; s.stale = null; s.received = 0; s.halted = null;
    return s;
  }

  function setConnection(state, connection) {
    var s = clone(state);
    s.connection = connection === "online" ? "online" : "offline";
    return s;
  }

  // ---- selection: one client-sync/1 snapshot of that id, nothing else ---------------------------

  function shownItems(state) {
    return state.items.length ? state.items : (state.previous ? state.previous.items : []);
  }

  function select(state, missionId) {
    var s = clone(state);
    var listed = shownItems(s).some(function (it) { return it.mission.id === missionId; });
    if (!listed) return reject(s, "NOT_IN_INVENTORY", null);
    s.selectionToken += 1;
    s.selection = { missionId: missionId, token: s.selectionToken, sync: S.createState() };
    return s;
  }

  // Never a list cursor, never an event cursor taken from the list: a plain snapshot request.
  function selectionRequest(state) {
    if (!state.selection || state.connection !== "online") return null;
    var r = S.nextRequest(state.selection.sync);
    if (!r) return null;
    return { kind: "mission-snapshot", missionId: state.selection.missionId, token: state.selection.token,
      epoch: r.epoch, syncKind: r.kind, cursor: r.cursor ? clone(r.cursor) : null };
  }

  function receiveSelection(state, env, request) {
    var s = clone(state);
    request = request || {};
    if (!s.selection || request.token !== s.selection.token) { s.stats.staleSelections += 1; return s; }
    if (s.connection !== "online") { s.stats.staleAnswers += 1; return s; }
    if (!isObject(env) || env.mission_id !== s.selection.missionId) return reject(s, "SELECTION_MISMATCH", request.receivedAt);
    if (s.storeId && env.store_id !== s.storeId) return reject(s, "SELECTION_STORE_MISMATCH", request.receivedAt);
    s.selection.sync = S.receive(s.selection.sync, env,
      { kind: request.syncKind || "snapshot", epoch: request.epoch, cursorSequence: null, receivedAt: request.receivedAt });
    s.selection.source = text(request.source, 80) ? request.source : null;
    return s;
  }

  // ---- presentation ----------------------------------------------------------------------------

  function summary(state) {
    var shown = shownItems(state);
    var announced = state.generation ? state.generation.mission_count : null;
    var status;
    if (state.stale) status = "Inventaire périmé (" + state.stale.reason + ") : nouvelle lecture explicite nécessaire";
    else if (state.halted) status = "Liste incomplète : réponse incohérente (" + state.halted.code + "), " + state.items.length
      + " reçues sur " + state.halted.announced + " annoncées ; nouvelle lecture explicite nécessaire";
    else if (!state.pages && state.previous) status = "Ancien inventaire périmé affiché ; nouvelle lecture en cours";
    else if (!state.pages) status = "Aucune page reçue";
    else if (state.truncated) status = "Liste tronquée : " + state.items.length + " affichées sur " + announced + " annoncées";
    else if (state.complete) status = state.items.length ? "Capture entièrement lue (" + state.items.length + ")" : "Aucune mission dans cette capture";
    else status = "Lecture partielle : " + state.items.length + " sur " + announced + " annoncées";
    return { status: status, shown: shown.length, announced: announced, complete: state.complete, truncated: state.truncated,
      stale: Boolean(state.stale) || (!state.pages && Boolean(state.previous)), halted: Boolean(state.halted), pages: state.pages };
  }

  var api = { PROTOCOL: PROTOCOL, MAX_ITEMS: MAX_ITEMS, createState: createState, validatePage: validatePage,
    nextPageRequest: nextPageRequest, receivePage: receivePage, receiveError: receiveError, relist: relist,
    setConnection: setConnection, select: select, selectionRequest: selectionRequest,
    receiveSelection: receiveSelection, shownItems: shownItems, summary: summary };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonMissionList = api;
})(typeof window !== "undefined" ? window : this);

/* ---- src/archives.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : archives.js
 * Description : État pur du catalogue paginé des archives de recherche, contrat C-030 (C-TASK-G066)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Consumer of POST /v1/research-archives (docs/HTTP-RESEARCH-ARCHIVES.md). Pure functions only:
 * the session owns the transport. Rules:
 *   - one generation per explicit load: a later load makes every older answer stale;
 *   - pages are appended only when store_id, catalog_sha256, chain_head and counts are those of
 *     the first page AND the first index follows the last one shown: two catalogs never mix;
 *   - RESET_REQUIRED, a refusal or an error keeps the shown list, marked stale, until an
 *     explicit reload; nothing is retried automatically;
 *   - only metadata is kept: no export, query text, path, mission or guard identifier.
 * Coherence was checked by Core; authenticity and commit in the live journal were not.
 */
(function (root) {
  "use strict";
  var NODE = typeof module === "object" && module.exports;

  var PROTOCOL = "eidolon-research-archive-page/1";
  var LIMIT = 50;                              // default page size; the contract allows 1–100
  var MAX_LIMIT = 100;
  var MAX_ITEMS = 1000;                        // C-028 bound on archives: never more kept
  var STORE_ID = /^s-[0-9a-f]{32}$/;
  var SHA = /^[0-9a-f]{64}$/;
  var FILE = /^research-archive-([0-9]{6})\.json$/;
  var FLAGS = { snapshot_only: true, consistency_verified: true, authenticity_verified: false,
    live_journal_checked: false, committed_status_known: false, authorizes_execution: false, request_sent: false };
  var FIELDS = ["protocol", "status", "store_id", "catalog_sha256", "chain_head", "archive_count", "run_count",
    "observed_at", "items", "has_more", "next_cursor"].concat(Object.keys(FLAGS));
  var ITEM_FIELDS = ["file", "index", "sha256", "created_at_ms", "count", "queries_with_text",
    "legacy_runs_without_text", "linked_missions"];
  var CURSOR_FIELDS = ["version", "store_id", "catalog_sha256", "after_index"];
  var RESET_REASONS = ["STORE_CHANGED", "CATALOG_CHANGED"];
  // Archive-specific refusals: they concern this panel only, never the connection state.
  var LOCAL_CODES = ["ARCHIVES_NOT_CONFIGURED", "ARCHIVES_BUSY", "ARCHIVES_UNAVAILABLE", "INVALID_ARCHIVE_CURSOR",
    "INVALID_PAGE_LIMIT", "UNKNOWN_FIELD", "RESPONSE_TOO_LARGE"];

  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function count(v) { return Number.isSafeInteger(v) && v >= 0; }
  function sameKeys(o, keys) {
    var own = Object.keys(o);
    return own.length === keys.length && keys.every(function (k) { return Object.prototype.hasOwnProperty.call(o, k); });
  }
  function clone(v) { return v === undefined || v === null ? v : JSON.parse(JSON.stringify(v)); }

  function create() {
    return { generation: 0, pending: null, status: "empty", catalog: null, items: [], hasMore: false,
      nextCursor: null, stale: false, staleReason: null, code: null, lastAt: null,
      stats: { rejected: 0, staleAnswers: 0 } };
  }

  // Returns an error code, or null when the page may be shown. ctx: { storeId, after, catalog }.
  function validatePage(p, ctx) {
    if (!isObject(p) || p.protocol !== PROTOCOL) return "UNSUPPORTED_PROTOCOL";
    var reset = p.status === "RESET_REQUIRED";
    if (!sameKeys(p, reset ? FIELDS.concat(["reason"]) : FIELDS)) return "INVALID_ARCHIVE_PAGE";
    if (Object.keys(FLAGS).some(function (k) { return p[k] !== FLAGS[k]; })) return "AUTHORITY_CLAIMED";
    if (typeof p.store_id !== "string" || !STORE_ID.test(p.store_id)) return "INVALID_ARCHIVE_PAGE";
    if (p.store_id !== ctx.storeId) return "STORE_MISMATCH";
    if (typeof p.catalog_sha256 !== "string" || !SHA.test(p.catalog_sha256)
        || typeof p.chain_head !== "string" || !SHA.test(p.chain_head)
        || !count(p.archive_count) || p.archive_count > MAX_ITEMS || !count(p.run_count)
        || typeof p.observed_at !== "string" || p.observed_at.length < 1 || p.observed_at.length > 64
        || !Array.isArray(p.items) || typeof p.has_more !== "boolean") return "INVALID_ARCHIVE_PAGE";
    if (reset) {
      return RESET_REASONS.indexOf(p.reason) >= 0 && p.items.length === 0 && p.has_more === false
        && p.next_cursor === null ? null : "INVALID_ARCHIVE_PAGE";
    }
    if (p.status !== "PAGE") return "UNKNOWN_STATUS";
    if (ctx.catalog && (p.catalog_sha256 !== ctx.catalog.catalogSha || p.chain_head !== ctx.catalog.chainHead
        || p.archive_count !== ctx.catalog.archiveCount || p.run_count !== ctx.catalog.runCount)) return "CATALOG_MISMATCH";
    if (p.items.length > (ctx.limit || MAX_LIMIT)) return "INVALID_ARCHIVE_PAGE";
    var expected = ctx.after + 1;
    for (var i = 0; i < p.items.length; i++) {
      var it = p.items[i];
      if (!isObject(it) || !sameKeys(it, ITEM_FIELDS)) return "INVALID_ARCHIVE_PAGE";
      var m = typeof it.file === "string" ? FILE.exec(it.file) : null;
      if (!m || it.index !== Number(m[1]) || typeof it.sha256 !== "string" || !SHA.test(it.sha256)
          || ITEM_FIELDS.slice(3).some(function (k) { return !count(it[k]); })
          || it.count < 1 || it.queries_with_text + it.legacy_runs_without_text !== it.count
          || it.linked_missions > it.count) return "INVALID_ARCHIVE_PAGE";
      if (it.index !== expected + i) return "PAGE_GAP";
    }
    var end = ctx.after + p.items.length;
    if (end > p.archive_count) return "INVALID_ARCHIVE_PAGE";
    if (p.has_more !== (end < p.archive_count)) return "INVALID_ARCHIVE_PAGE";
    if (!p.has_more) return p.next_cursor === null ? null : "INVALID_ARCHIVE_PAGE";
    var c = p.next_cursor;
    if (p.items.length === 0 || !isObject(c) || !sameKeys(c, CURSOR_FIELDS) || c.version !== 1
        || c.store_id !== p.store_id || c.catalog_sha256 !== p.catalog_sha256 || c.after_index !== end) return "INVALID_ARCHIVE_PAGE";
    return null;
  }

  // kind "first": explicit (re)load, new generation. kind "more": next page of the shown generation.
  function request(st, kind, limit) {
    var size = Number.isSafeInteger(limit) && limit >= 1 && limit <= MAX_LIMIT ? limit : LIMIT;
    var s = clone(st);
    if (kind === "first") {
      s.generation += 1;
      s.pending = { generation: s.generation, kind: "first", after: 0 };
      s.status = "loading";
      return { state: s, req: { generation: s.generation, kind: "first", after: 0, limit: size, body: { limit: size } } };
    }
    if (kind !== "more" || s.pending || s.stale || !s.catalog || !s.hasMore || !s.nextCursor
        || s.items.length >= MAX_ITEMS) return { state: st, req: null };
    var after = s.nextCursor.after_index;
    s.pending = { generation: s.generation, kind: "more", after: after };
    s.status = "loading";
    return { state: s, req: { generation: s.generation, kind: "more", after: after, limit: size,
      body: { limit: size, cursor: clone(s.nextCursor) } } };
  }

  function current(st, req) {
    return req && st.pending && st.pending.generation === req.generation && st.pending.kind === req.kind
      && st.pending.after === req.after && st.generation === req.generation;
  }

  function staleShown(s, reason, code) {
    s.stale = s.items.length > 0 || s.catalog !== null;
    s.staleReason = s.stale ? reason : null;
    s.code = code;
  }

  function receive(st, req, page, storeId, receivedAt) {
    if (!current(st, req)) { var t = clone(st); t.stats.staleAnswers += 1; return t; }
    var s = clone(st);
    s.pending = null;
    var bad = validatePage(page, { storeId: storeId, after: req.after, limit: req.limit,
      catalog: req.kind === "more" ? s.catalog : null });
    if (bad) {
      s.stats.rejected += 1;
      s.status = "error";
      staleShown(s, "REJECTED", bad);
      return s;
    }
    if (page.status === "RESET_REQUIRED") {
      // Keep the previous generation, frozen; the user reloads explicitly.
      s.status = "reset";
      s.hasMore = false;
      s.nextCursor = null;
      staleShown(s, page.reason, page.reason);
      return s;
    }
    var meta = { storeId: page.store_id, catalogSha: page.catalog_sha256, chainHead: page.chain_head,
      archiveCount: page.archive_count, runCount: page.run_count, observedAt: page.observed_at, receivedAt: receivedAt };
    var items = page.items.map(function (it) {
      var o = {};
      ITEM_FIELDS.forEach(function (k) { o[k] = it[k]; });
      return o;
    });
    if (req.kind === "first") { s.catalog = meta; s.items = items; }
    else { s.items = s.items.concat(items); s.catalog.receivedAt = receivedAt; }
    s.hasMore = page.has_more;
    s.nextCursor = clone(page.next_cursor);
    s.status = "loaded";
    s.stale = false;
    s.staleReason = null;
    s.code = null;
    s.lastAt = receivedAt;
    return s;
  }

  function receiveError(st, req, code, receivedAt) {
    if (!current(st, req)) { var t = clone(st); t.stats.staleAnswers += 1; return t; }
    var s = clone(st);
    s.pending = null;
    s.status = "error";
    s.lastAt = receivedAt;
    staleShown(s, "ERROR", code);
    return s;
  }

  // Connection lost or refused: what is shown stops being current; nothing is discarded.
  function markStale(st, reason) {
    if (st.stale || (!st.items.length && !st.catalog && !st.pending)) return st;
    var s = clone(st);
    s.pending = null;
    if (s.status === "loading") s.status = "error";
    staleShown(s, reason, s.code || reason);
    return s;
  }

  function summary(st) {
    var c = st.catalog;
    return { shown: st.items.length, total: c ? c.archiveCount : null, runs: c ? c.runCount : null,
      complete: Boolean(c) && !st.hasMore && st.items.length === c.archiveCount,
      current: Boolean(c) && !st.stale && st.status === "loaded" };
  }

  var api = { PROTOCOL: PROTOCOL, LIMIT: LIMIT, MAX_LIMIT: MAX_LIMIT, MAX_ITEMS: MAX_ITEMS, LOCAL_CODES: LOCAL_CODES, FLAGS: FLAGS,
    create: create, validatePage: validatePage, request: request, receive: receive, receiveError: receiveError,
    markStale: markStale, summary: summary };
  if (NODE) module.exports = api;
  else root.EidolonArchives = api;
})(typeof window !== "undefined" ? window : this);

/* ---- src/session.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : session.js
 * Description : Session de consultation connectée à l'API eidolon-http-read/1 (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Read-only session over docs/HTTP-READ-API.md. The transport is injected:
 *   transport(method, path, body, token) -> Promise<{ status, json }>, rejects on network failure.
 * Paths are same-origin "/v1/..." only. The token lives in this closure, never in storage.
 * The pure consumers of the prototype (sync-state.js, mission-list-state.js) keep their
 * rules: one generation per list, exact cursors, explicit reset, older selections ignored.
 * Three guards against mixing answers:
 *   - connEpoch: bumped on connect, disconnect and authentication loss;
 *   - list epoch and selection token: owned by mission-list-state.js;
 *   - store_id: a reconnection to another store wipes everything shown.
 * There is no command here: no approve, run or cancel; authorizes_execution stays false.
 * G036: a historical command receipt (docs/HTTP-RECEIPTS.md) can be looked up for the
 * selected mission. It is kept apart from the snapshot and never changes it.
 * G066: the research archive catalog (docs/HTTP-RESEARCH-ARCHIVES.md) is read on explicit
 * request only, in its own state (archives.js). Its refusals never change the connection
 * phase; a new connection or store starts from an empty catalog view.
 */
(function (root) {
  "use strict";
  var NODE = typeof module === "object" && module.exports;
  var S = NODE ? require("../../prototype/sync-state.js") : root.EidolonSync;
  var L = NODE ? require("../../prototype/mission-list-state.js") : root.EidolonMissionList;
  var A = NODE ? require("./archives.js") : root.EidolonArchives;

  var PROTOCOL = "eidolon-http-read/1";
  var TOKEN = /^[A-Za-z0-9_-]{32,128}$/;
  var MISSION_ID = /^m-[0-9a-f]{32}$/;
  var STORE_ID = /^s-[0-9a-f]{32}$/;
  var PAGE_LIMIT = 100;
  var MAX_LIST_PAGES = 3;       // 200 items at most are kept (MAX_ITEMS): never an endless loop
  var MAX_POLLS = 5;            // has_more drained at most 5 pages per explicit refresh
  var RECEIPT_PROTOCOL = "eidolon-http-receipt/1";
  var KEY = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/;   // client_id and command_key, as the CLI
  var RECEIPT_KINDS = { "eidolon-command-receipt/1": "decision", "eidolon-cancel-receipt/1": "cancel" };
  // G048: how Core bound a FOUND receipt to its journal event (C-012). Absent = older server, unspecified.
  var RECEIPT_BINDINGS = ["EVENT_HASH", "LEGACY_FIELDS"];

  function clone(v) { return v === undefined || v === null ? v : JSON.parse(JSON.stringify(v)); }
  function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }

  function validateHealth(h) {
    return isObject(h) && h.protocol === PROTOCOL && h.mode === "read_only"
      && h.authorizes_execution === false && typeof h.store_id === "string" && STORE_ID.test(h.store_id);
  }

  function errorCode(json) {
    if (isObject(json) && json.protocol === PROTOCOL && json.authorizes_execution === false
        && typeof json.error === "string" && /^[A-Z_]{1,64}$/.test(json.error)) return json.error;
    return null;
  }

  function shortText(v) { return typeof v === "string" && v.length > 0 && v.length <= 64; }
  function safeInt(v) { return Number.isSafeInteger(v) && v >= 0; }

  // Structure only; never repaired. Every identifier must echo the question asked.
  function validateReceiptAnswer(env, q) {
    if (!isObject(env) || env.protocol !== RECEIPT_PROTOCOL) return "UNSUPPORTED_PROTOCOL";
    if (env.execution_evidence !== false || env.effect_absence_evidence !== false
        || env.authorizes_resend !== false || env.authorizes_execution !== false) return "AUTHORITY_CLAIMED";
    if (["store_id", "client_id", "command_key", "mission_id"].some(function (k) { return env[k] !== q[k]; })) return "QUERY_MISMATCH";
    if (env.status === "NOT_FOUND") return env.receipt === null && !("receipt_binding" in env) ? null : "INVALID_RECEIPT";
    if (env.status !== "FOUND") return "UNKNOWN_STATUS";
    if ("receipt_binding" in env && RECEIPT_BINDINGS.indexOf(env.receipt_binding) < 0) return "INVALID_BINDING";
    var r = env.receipt;
    if (!isObject(r) || !RECEIPT_KINDS[r.protocol]) return "INVALID_RECEIPT";
    if (["store_id", "client_id", "command_key", "mission_id"].some(function (k) { return r[k] !== q[k]; })) return "QUERY_MISMATCH";
    if (r.execution_evidence !== false || ("authorizes_execution" in r && r.authorizes_execution !== false)) return "AUTHORITY_CLAIMED";
    if (!shortText(r.status) || !shortText(r.recorded_at) || !safeInt(r.event_sequence) || !safeInt(r.mission_revision)) return "INVALID_RECEIPT";
    if (RECEIPT_KINDS[r.protocol] === "decision"
        && (["approve", "reject", "revoke"].indexOf(r.decision) < 0 || !shortText(r.approval_status_at_recording))) return "INVALID_RECEIPT";
    if (RECEIPT_KINDS[r.protocol] === "cancel"
        && (!shortText(r.cancel_outcome) || !shortText(r.mission_status_at_recording))) return "INVALID_RECEIPT";
    return null;
  }

  // G043: what an answer did to a consumer state. Only an accepted answer is a fresh read.
  function counters(list) {
    var sel = list.selection, sync = sel && sel.sync;
    return { rejected: list.stats.rejected.length, stale: list.stats.staleAnswers + list.stats.repeatedPages
        + list.stats.frozenAnswers + list.stats.staleSelections,
      syncRejected: sync ? sync.stats.rejected.length : 0,
      syncStale: sync ? sync.stats.staleAnswers + sync.stats.frozenAnswers + sync.stats.staleViews : 0 };
  }
  function lastRejection(list) {
    var sync = list.selection && list.selection.sync;
    var all = list.stats.rejected.concat(sync ? sync.stats.rejected : []);
    return all.length ? all[all.length - 1].code : "REJECTED";
  }
  function outcome(before, list) {
    var after = counters(list);
    if (after.rejected > before.rejected || after.syncRejected > before.syncRejected) return "rejected";
    if (after.stale > before.stale || after.syncStale > before.syncStale) return "stale";
    return "accepted";
  }

  // The shown capture is current only when connected (not busy), without a pending reset or a refusal since.
  function viewIsCurrent(st) {
    var sel = st.list.selection;
    return Boolean(st.phase === "connected" && sel && sel.sync.view && !sel.sync.reset && !sel.sync.lastError);
  }

  function createSession(options) {
    var transport = options.transport;
    var now = options.now || function () { return new Date().toISOString(); };
    var onChange = options.onChange || function () {};
    var archiveLimit = options.archiveLimit;   // G066: page size (tests, small screens); default 50
    var token = null;
    var loops = { list: 0, selection: 0, receipt: 0, archives: 0 };

    var state = {
      phase: "disconnected",   // disconnected | connecting | connected | offline | unavailable | unauthorized | refused
      connEpoch: 0,
      storeId: null,
      list: L.createState(),
      lastSuccessAt: null,     // local time of the last accepted answer
      problem: null,           // { code, at, scope } last failure shown to the user
      notice: null,            // one-line explanation of an identity wipe
      receipt: null,           // { query, status, receipt, code, receivedAt }: historical, never the current state
      resyncRequired: false,   // STORE_CHANGED answered: reconnect before any other receipt lookup
      archives: A.create(),    // G066: catalog metadata pages, separate from missions
      stats: { staleConnection: 0, staleSelection: 0, invalidResponses: 0, staleReceipt: 0 }
    };

    function emit() { onChange(snapshot()); }
    function snapshot() { return clone(state); }
    function hasToken() { return token !== null; }

    function setOnline(online) {
      var mode = online ? "online" : "offline";
      state.list = L.setConnection(state.list, mode);
      if (state.list.selection) state.list.selection.sync = S.setConnection(state.list.selection.sync, mode);
    }

    // Explicit reads are allowed when connected, and after a BUSY answer (the user retries).
    function canRead() { return state.phase === "connected" || state.phase === "busy"; }

    function forgetReceipt() { loops.receipt += 1; state.receipt = null; }

    function forgetArchives() { loops.archives += 1; state.archives = A.create(); }

    function wipe() {
      forgetReceipt();
      forgetArchives();
      state.list = L.createState();
      state.storeId = null;
      state.lastSuccessAt = null;
    }

    function fail(phase, code, scope) {
      state.phase = phase;
      state.problem = { code: code, at: now(), scope: scope };
      setOnline(false);
      state.archives = A.markStale(state.archives, "CONNECTION_" + phase.toUpperCase());
    }

    // One request; returns { ok, json } or { ok:false } after recording the failure.
    // local: error codes that concern the caller's panel only (G066), never the connection phase.
    async function call(method, path, body, scope, local) {
      var epoch = state.connEpoch;
      var answer;
      try {
        answer = await transport(method, path, body, token);
      } catch (err) {
        if (epoch !== state.connEpoch) { state.stats.staleConnection += 1; return { stale: true }; }
        fail("offline", "NETWORK_UNREACHABLE", scope);
        return { ok: false };
      }
      if (epoch !== state.connEpoch) { state.stats.staleConnection += 1; return { stale: true }; }
      var status = answer && answer.status, json = answer ? answer.json : null;
      var code = errorCode(json);
      if (status === 200) {
        if (state.phase === "busy") state.phase = "connected";   // the server serves again
        return { ok: true, json: json };
      }
      if (local && code && local.indexOf(code) >= 0) {
        state.problem = { code: code, at: now(), scope: scope };
        return { ok: false, code: code, status: status };
      }
      if (status === 503 && (code === "BUSY" || code === "STATE_BUSY")) {
        // G043: explicit saturation (C-010b); G125: a writer holds the Core database. Neither is an
        // outage: stay online, nothing retried automatically, shown data stop being current.
        state.phase = "busy";
        state.problem = { code: code, at: now(), scope: scope };
        return { ok: false, code: code, status: status };
      }
      if (status === 401) {
        token = null; state.connEpoch += 1;  // every answer still in flight is now foreign
        fail("unauthorized", code || "UNAUTHORIZED", scope);
        return { ok: false };
      }
      if (status === 403) { fail("refused", code || "FORBIDDEN", scope); return { ok: false }; }
      if ((status === 503 && code !== "RECEIPT_UNAVAILABLE") || status === 408) {
        fail("unavailable", code || "STATE_UNAVAILABLE", scope);
        return { ok: false };
      }
      if (!code) state.stats.invalidResponses += 1;
      state.problem = { code: code || "INVALID_RESPONSE", at: now(), scope: scope };
      return { ok: false, code: code || "INVALID_RESPONSE", status: status };
    }

    async function connect(newToken) {
      if (typeof newToken !== "string" || !TOKEN.test(newToken)) {
        state.problem = { code: "TOKEN_FORMAT", at: now(), scope: "connection" };
        emit();
        return false;
      }
      token = newToken;
      state.connEpoch += 1;
      state.phase = "connecting";
      state.notice = null;
      state.resyncRequired = false;
      forgetArchives();                    // G066: never mix two sessions' catalog pages
      emit();
      var r = await call("GET", "/v1/health", undefined, "connection");
      if (r.stale) return false;
      if (!r.ok) {
        if (state.phase === "connecting") fail("refused", r.code || "INVALID_RESPONSE", "connection");
        emit();
        return false;
      }
      if (!validateHealth(r.json)) {
        state.stats.invalidResponses += 1;
        fail("refused", "INVALID_HEALTH", "connection");
        emit();
        return false;
      }
      if (state.storeId && state.storeId !== r.json.store_id) {
        wipe();
        state.notice = "Autre base Core que la précédente : l'affichage précédent a été effacé.";
      }
      state.storeId = r.json.store_id;
      state.phase = "connected";
      state.problem = null;
      state.lastSuccessAt = now();
      setOnline(true);
      emit();
      await relist();
      return true;
    }

    function disconnect() {
      token = null;
      state.connEpoch += 1;
      wipe();
      state.phase = "disconnected";
      state.problem = null;
      state.notice = null;
      emit();
    }

    async function relist() {
      if (!canRead()) return;
      state.list = L.relist(state.list);
      emit();
      // G043: a list that was not read (BUSY, refusal, error) does not trigger a selection refresh
      // that would hide the failure behind a fresh-looking detail.
      if (await loadList() && state.list.selection) await refreshSelection();
    }

    async function loadList() {
      var mine = ++loops.list;
      for (var i = 0; i < MAX_LIST_PAGES; i++) {
        if (mine !== loops.list || !canRead()) return false;
        var req = L.nextPageRequest(state.list);
        if (!req) return true;              // nothing more to read: listing done
        var body = req.cursor ? { cursor: req.cursor, limit: PAGE_LIMIT } : { limit: PAGE_LIMIT };
        var r = await call("POST", "/v1/missions", body, "list");
        if (r.stale) return false;
        var meta = { kind: "list", epoch: req.epoch, cursor: req.cursor, receivedAt: now(), source: "serveur" };
        if (r.ok) {
          var beforeList = counters(state.list);
          state.list = L.receivePage(state.list, r.json, meta);
          var result = outcome(beforeList, state.list);
          if (result !== "accepted") {
            if (result === "rejected") state.problem = { code: lastRejection(state.list), at: meta.receivedAt, scope: "list" };
            emit();
            return false;
          }
          if (state.list.storeId && state.list.storeId !== state.storeId) {
            // The list answered for another store than /v1/health: never shown together.
            wipe(); fail("refused", "STORE_IDENTITY_CHANGED", "list");
            emit();
            return false;
          }
          state.lastSuccessAt = meta.receivedAt;
          if (state.list.items.length >= L.MAX_ITEMS && state.list.nextCursor) {
            // G038: the display bound is reached; a further page would be read then discarded.
            state.list = clone(state.list);
            state.list.truncated = true;
            state.list.nextCursor = null;
          }
        } else if (r.code) {
          state.list = L.receiveError(state.list, r.code, meta);
        }
        emit();
        if (!r.ok) return false;
      }
      return true;
    }

    function selectMission(id) {
      if (typeof id !== "string" || !MISSION_ID.test(id)) return Promise.resolve(false);
      forgetReceipt();
      state.list = L.select(state.list, id);
      emit();
      return refreshSelection();
    }

    async function refreshSelection() {
      var mine = ++loops.selection;
      for (var i = 0; i < MAX_POLLS; i++) {
        if (mine !== loops.selection || !canRead()) return false;
        var req = L.selectionRequest(state.list);
        if (!req || !MISSION_ID.test(req.missionId)) return false;
        var path = "/v1/missions/" + req.missionId;
        var r = req.syncKind === "poll"
          ? await call("POST", path + "/poll", { cursor: req.cursor, limit: PAGE_LIMIT }, "selection")
          : await call("GET", path, undefined, "selection");
        if (r.stale) return false;
        var sel = state.list.selection;
        if (!sel || sel.token !== req.token) { state.stats.staleSelection += 1; emit(); return false; }
        var meta = { token: req.token, epoch: req.epoch, syncKind: req.syncKind, receivedAt: now(), source: "serveur" };
        if (r.ok) {
          var beforeSel = counters(state.list);
          state.list = L.receiveSelection(state.list, r.json, meta);
          var res = outcome(beforeSel, state.list);
          if (res === "accepted") state.lastSuccessAt = meta.receivedAt;
          else if (res === "rejected") state.problem = { code: lastRejection(state.list), at: meta.receivedAt, scope: "selection" };
        } else if (r.code) {
          state.list = clone(state.list);
          state.list.selection.sync = S.receiveError(state.list.selection.sync, r.code, meta);
        }
        emit();
        var sync = state.list.selection && state.list.selection.sync;
        // A snapshot is one request; a poll drains has_more within MAX_POLLS, never beyond.
        if (!r.ok) return false;
        if (req.syncKind !== "poll" || !sync || sync.reset || !sync.hasMore) return true;
      }
      return true;
    }

    function acceptReset() {
      if (!state.list.selection || !state.list.selection.sync.reset) return Promise.resolve(false);
      state.list = clone(state.list);
      state.list.selection.sync = S.acceptReset(state.list.selection.sync);
      emit();
      return refreshSelection();
    }

    // Historical receipt of ONE command key for the selected mission. Read-only: FOUND is a
    // record, NOT_FOUND keeps the uncertainty, neither changes the snapshot or allows a resend.
    async function lookupReceipt(clientId, commandKey) {
      var sel = state.list.selection;
      if (!canRead() || state.resyncRequired || !sel || !state.storeId) return false;
      if (typeof clientId !== "string" || typeof commandKey !== "string" || !KEY.test(clientId) || !KEY.test(commandKey)) {
        state.receipt = { query: null, status: "INVALID_QUERY", receipt: null, code: "INVALID_QUERY", receivedAt: now() };
        emit();
        return false;
      }
      var mine = ++loops.receipt, selToken = sel.token;
      var q = { store_id: state.storeId, client_id: clientId, command_key: commandKey, mission_id: sel.missionId };
      state.receipt = { query: q, status: "PENDING", receipt: null, code: null, receivedAt: null };
      emit();
      var r = await call("POST", "/v1/command-receipt", q, "receipt");
      if (r.stale) return false;
      if (mine !== loops.receipt || !state.list.selection || state.list.selection.token !== selToken) {
        state.stats.staleReceipt += 1; emit(); return false;     // asked for another selection or key
      }
      var at = now();
      if (r.ok) {
        var bad = validateReceiptAnswer(r.json, q);
        if (bad) {
          state.stats.invalidResponses += 1;
          state.receipt = { query: q, status: "ERROR", receipt: null, code: bad, receivedAt: at };
        } else {
          // G043: a historical receipt is dated by its own receivedAt; it does not make the
          // current capture (or the connection's last accepted read) look fresher.
          // G048: binding null = not stated by Core (older server), never EVENT_HASH by default.
          state.receipt = { query: q, status: r.json.status, receipt: clone(r.json.receipt), code: null, receivedAt: at,
            binding: r.json.status === "FOUND" && "receipt_binding" in r.json ? r.json.receipt_binding : null };
        }
      } else {
        state.receipt = { query: q, status: "ERROR", receipt: null, code: r.code || (state.problem && state.problem.code) || "UNKNOWN_ERROR", receivedAt: at };
        if (r.code === "STORE_CHANGED") {
          state.resyncRequired = true;
          state.notice = "La base Core n'a plus l'identité affichée : se reconnecter pour resynchroniser. Rien n'a été renvoyé.";
        }
      }
      emit();
      return r.ok;
    }

    // G066: one explicit page request; "first" (re)loads a new generation, "more" continues it.
    async function loadArchives(kind) {
      if (!canRead() || !state.storeId || state.resyncRequired) return false;
      var r = A.request(state.archives, kind === "more" ? "more" : "first", archiveLimit);
      if (!r.req) return false;
      var mine = ++loops.archives, storeId = state.storeId;
      state.archives = r.state;
      emit();
      var res = await call("POST", "/v1/research-archives", r.req.body, "archives", A.LOCAL_CODES);
      if (res.stale || mine !== loops.archives) return false;
      var at = now();
      if (res.ok) {
        state.archives = A.receive(state.archives, r.req, res.json, storeId, at);
        if (state.archives.status !== "loaded" && state.archives.status !== "reset") state.stats.invalidResponses += 1;
      } else {
        state.archives = A.receiveError(state.archives, r.req, res.code || (state.problem && state.problem.code) || "UNKNOWN_ERROR", at);
      }
      emit();
      return state.archives.status === "loaded";
    }

    return { connect: connect, disconnect: disconnect, relist: relist, selectMission: selectMission,
      refreshSelection: refreshSelection, acceptReset: acceptReset, lookupReceipt: lookupReceipt,
      loadArchives: function () { return loadArchives("first"); }, moreArchives: function () { return loadArchives("more"); },
      state: snapshot, hasToken: hasToken };
  }

  var api = { PROTOCOL: PROTOCOL, TOKEN: TOKEN, KEY: KEY, RECEIPT_KINDS: RECEIPT_KINDS, createSession: createSession,
    validateHealth: validateHealth, validateReceiptAnswer: validateReceiptAnswer, RECEIPT_BINDINGS: RECEIPT_BINDINGS, viewIsCurrent: viewIsCurrent,
    errorCode: errorCode, missionLabel: S.missionLabel, cancelNote: S.cancelNote,
    objectiveLabel: S.objectiveLabel, researchNote: S.researchNote, listSummary: L.summary,
    shownItems: L.shownItems, syncSummary: S.summary, archiveSummary: A.summary };
  if (NODE) module.exports = api;
  else root.EidolonConnected = api;
})(typeof window !== "undefined" ? window : this);

/* ---- src/view.js ---- */
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

  // G125: the database is locked by a writer for a moment; not a failure of the base itself.
  var STORAGE_BUSY = "Base Core occupée par une écriture (STATE_BUSY) : la lecture n'a pas eu lieu. " +
    "L'affichage date de la dernière lecture acceptée ; réessayer dans quelques secondes avec « Actualiser ».";

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
    status.textContent = s.phase === "busy" && s.problem && s.problem.code === "STATE_BUSY" ? STORAGE_BUSY
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
      ? "Capture non actualisée : serveur occupé, la dernière demande n'a pas été traitée."
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

/* ---- src/media-agents.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : media-agents.js
 * Description : Espaces Image/Vidéo et brouillons locaux, sans transport
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  var TYPES = { "image/png": ".png", "image/jpeg": ".jpg,.jpeg", "image/webp": ".webp",
    "video/mp4": ".mp4", "video/webm": ".webm" };
  function allowed(agent, mode) {
    return Object.keys(TYPES).filter(function (t) {
      return agent === "image" ? t.indexOf("image/") === 0 :
        mode === "create" || t.indexOf("video/") === 0;
    });
  }
  function prepareDraft(agent, mode, prompt, file, format, duration) {
    if (["image", "video"].indexOf(agent) < 0 || ["create", "edit", "analyze"].indexOf(mode) < 0)
      throw new Error("Choisissez un agent et une opération valides.");
    if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 4000)
      throw new Error("Décrivez votre demande (1 à 4 000 caractères).");
    if (mode !== "create" && !file) throw new Error("Choisissez le fichier à modifier ou à analyser.");
    var source = null;
    if (file) {
      if (allowed(agent, mode).indexOf(file.type) < 0)
        throw new Error("Ce format de fichier n’est pas accepté pour cette opération.");
      var limit = file.type.indexOf("image/") === 0 ? 20 * 1024 * 1024 : 200 * 1024 * 1024;
      if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > limit)
        throw new Error("Fichier vide ou trop volumineux (image : 20 Mio ; vidéo : 200 Mio).");
      if (typeof file.name !== "string" || !file.name || file.name.length > 255 || /[\x00-\x1f\x7f]/.test(file.name))
        throw new Error("Le nom du fichier n’est pas accepté.");
      source = { name: file.name, type: file.type, size: file.size };
    }
    if (mode !== "analyze" && ["square", "landscape", "portrait"].indexOf(format) < 0)
      throw new Error("Choisissez un format de sortie.");
    if (mode !== "analyze" && agent === "video" && [5, 10, 15].indexOf(duration) < 0)
      throw new Error("Choisissez une durée proposée.");
    return { schema: "media-draft/1", agent: agent, operation: mode, request: prompt.trim(),
      source: source, output: mode === "analyze" ? null : { format: format,
        duration_seconds: agent === "video" ? duration : null },
      state: "LOCAL_DRAFT", submitted: false };
  }
  function mount(doc) {
    if (!doc.getElementById("media-agents")) return { clear: function () {} };
    var agents = ["image", "video"];
    function el(id) { return doc.getElementById(id); }
    function close() {
      agents.forEach(function (a) { el(a + "-workspace").hidden = true; el("open-" + a).setAttribute("aria-expanded", "false"); });
    }
    function invalidate(a) { el(a + "-draft").hidden = true; el(a + "-summary").textContent = "";
      el(a + "-request").textContent = ""; el(a + "-file-summary").textContent = "";
      el(a + "-status").textContent = ""; }
    function modeChanged(a) {
      var mode = el(a + "-mode").value;
      el(a + "-settings").hidden = mode === "analyze";
      el(a + "-source").accept = allowed(a, mode).map(function (t) { return t + "," + TYPES[t]; }).join(",");
      el(a + "-source-label").textContent = mode === "create" ? "Fichier de référence (facultatif)" : "Fichier à " + (mode === "edit" ? "modifier" : "analyser") + " (obligatoire)";
      el(a + "-prompt-label").textContent = mode === "create" ? "Décrivez votre idée" : mode === "edit" ? "Que souhaitez-vous modifier ?" : "Que souhaitez-vous comprendre ?";
      el(a + "-prompt").placeholder = mode === "analyze" ? "Décrire la scène, lire un texte, relever les éléments importants…" : "Sujet, ambiance, détails importants…";
      el(a + "-file-help").textContent = a === "image" ? "PNG, JPEG ou WebP · 20 Mio maximum." :
        mode === "create" ? "Référence PNG, JPEG, WebP (20 Mio), MP4 ou WebM (200 Mio)." : "MP4 ou WebM · 200 Mio maximum.";
      invalidate(a);
    }
    function clear(a) { el(a + "-form").reset(); modeChanged(a); }
    agents.forEach(function (a) {
      var open = el("open-" + a); open.disabled = false;
      open.addEventListener("click", function () { close(); el(a + "-workspace").hidden = false;
        open.setAttribute("aria-expanded", "true"); el(a + "-title").focus(); });
      el(a + "-back").addEventListener("click", function () { close(); open.focus(); });
      el(a + "-clear").addEventListener("click", function () { clear(a); el(a + "-prompt").focus(); });
      el(a + "-form").addEventListener("input", function () { invalidate(a); });
      el(a + "-form").addEventListener("change", function () { invalidate(a); });
      el(a + "-mode").addEventListener("change", function () { modeChanged(a); });
      el(a + "-form").addEventListener("submit", function (event) {
        event.preventDefault(); invalidate(a);
        try {
          var d = prepareDraft(a, el(a + "-mode").value, el(a + "-prompt").value,
            el(a + "-source").files[0] || null, el(a + "-format").value,
            a === "video" ? Number(el(a + "-duration").value) : null);
          el(a + "-summary").textContent = (a === "image" ? "Image" : "Vidéo") + " · " +
            ({ create: "Créer", edit: "Modifier", analyze: "Analyser" })[d.operation] +
            (d.output ? " · " + ({ square: "Carré", landscape: "Paysage", portrait: "Portrait" })[d.output.format] +
              (a === "video" ? " · " + d.output.duration_seconds + " secondes souhaitées" : "") : "");
          el(a + "-request").textContent = d.request;
          el(a + "-file-summary").textContent = d.source ? "Fichier choisi : " + d.source.name + " — contenu non lu." : "Sans fichier de référence.";
          el(a + "-draft").hidden = false;
          el(a + "-status").textContent = "Brouillon préparé. Aucune mission envoyée ; le moteur reste à raccorder.";
        } catch (err) { el(a + "-status").textContent = err.message; }
      });
      modeChanged(a);
    });
    return { clear: function () { agents.forEach(clear); close(); } };
  }
  var api = { prepareDraft: prepareDraft, mount: mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonMediaAgents = api;
})(typeof window !== "undefined" ? window : this);

/* ---- src/conversation.js ---- */
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
    DIGEST_MISMATCH: "La proposition affichée ne correspond pas à celle figée par Core : rien n'a été envoyé.",
    RECEIPT_MISMATCH: "La réponse reçue ne nomme pas cette mission : état incertain, vérifiez." };
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

  function stageOf(status) { return Object.prototype.hasOwnProperty.call(STAGES, status) ? STAGES[status] : null; }

  function createConversation(options) {
    var transport = options.transport, onChange = options.onChange || function () {};
    var token = null, epoch = 0;
    var state = { phase: "closed", error: null, conversationId: null, identity: null, items: [],
      proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, cancels: [], media: null };

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
      state = { phase: "opening", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, cancels: [], media: null };
      emit();
      var r = await call("open", { client_key: randomKey("page") });
      if (r.stale) return false;
      if (!r.ok) { token = null; state.phase = "closed"; state.error = r.code; emit(); return false; }
      state.phase = "open";
      state.conversationId = r.json.conversation_id;
      state.identity = { clientId: r.json.client_id, actor: r.json.actor, storeId: r.json.store_id };
      state.recent = [];
      restoreCancels();
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
      state.cancel = null; state.media = null;            // pending cancellations (state.cancels) are kept
      state.recent = state.recent.filter(function (c) { return c.conversation_id !== conversationId; });
      state.resumed = true;
      emit();
      return true;
    }

    function close() {
      epoch += 1; token = null;
      state = { phase: "closed", error: null, conversationId: null, identity: null, items: [], proposal: null, proposalSha: null, submission: null, recent: [], cancel: null, cancels: [], media: null };
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

    // ---- G100/G124: targeted cancellation (proposal → human confirmation → request, never a confirmed stop)
    // One record PER MISSION, kept with its own key, conversation and proposal: a late answer updates
    // the record it belongs to, never the mission selected meanwhile (G124-R1). Unfinished records are
    // saved in the page's session storage (no secret: ids, key and digest) to be CHECKED after a reload.
    var storage = options.storage || null;
    function storageKey() {
      return state.identity ? "eidolon-cancel:" + state.identity.storeId + ":" + state.identity.clientId : null;
    }
    function persistCancels() {
      var k = storageKey();
      if (!storage || !k) return;
      var keep = state.cancels.filter(function (r) { return r.key && FINAL_STAGES.indexOf(r.stage) < 0; })
        .map(function (r) { return { missionId: r.missionId, conversationId: r.conversationId, key: r.key, sha: r.sha,
          proposal: r.proposal, status: r.status === "sent" ? "uncertain" : r.status, stage: r.stage }; });
      try { if (keep.length) storage.setItem(k, JSON.stringify(keep)); else storage.removeItem(k); } catch (e) { /* no storage */ }
    }
    function restoreCancels() {
      var k = storageKey(), raw = null;
      if (!storage || !k) return;
      try { raw = JSON.parse(storage.getItem(k) || "[]"); } catch (e) { raw = []; }
      (Array.isArray(raw) ? raw : []).forEach(function (r) {
        if (!r || !MISSION.test(r.missionId) || !/^c-[0-9a-f]{32}$/.test(r.conversationId) || typeof r.key !== "string") return;
        state.cancels.push({ missionId: r.missionId, conversationId: r.conversationId, key: r.key, sha: r.sha,
          proposal: r.proposal, status: "restored", stage: r.stage || null, missionStatus: null, receipt: null,
          error: null, code: null, candidates: [] });
      });
    }
    function recordFor(missionId) {
      return state.cancels.filter(function (r) { return r.missionId === missionId; })[0] || null;
    }

    async function cancelPropose(missionId) {
      if (state.phase !== "open") return false;
      var body = { conversation_id: state.conversationId };
      if (missionId !== undefined && missionId !== null) {
        if (!MISSION.test(missionId)) return false;
        body.mission_id = missionId;
        var known = recordFor(missionId);
        if (known && known.key && known.conversationId !== state.conversationId) {
          state.cancel = known; emit(); return true;      // a restored request: check it, never re-propose here
        }
      }
      var mine = epoch;
      state.cancel = { status: "loading", missionId: missionId || null, conversationId: state.conversationId,
        proposal: null, sha: null, missionStatus: null, candidates: [], code: null, key: null, receipt: null,
        stage: null, error: null };
      emit();
      var r = await call("cancel_proposal", body);
      if (r.stale) return false;
      var c = state.cancel;
      if (!r.ok) { c.status = "error"; c.error = r.code; emit(); return false; }
      if (r.json.kind === "PROPOSAL") {
        var local = await digest(r.json.proposal);
        if (mine !== epoch) return false;
        var id = r.json.proposal.mission_id;
        if (local !== r.json.proposal_sha256 || !MISSION.test(id) || (missionId && id !== missionId)) {
          c.status = "error"; c.error = "DIGEST_MISMATCH"; emit(); return false;
        }
        var existing = recordFor(id);
        if (existing && existing.key) {
          existing.missionStatus = r.json.mission_status; state.cancel = existing;   // keep its key and state
        } else {
          if (existing) state.cancels.splice(state.cancels.indexOf(existing), 1);
          c.status = "review"; c.missionId = id; c.proposal = r.json.proposal; c.sha = local;
          c.missionStatus = r.json.mission_status;
          state.cancels.push(c);
        }
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
      var rec = state.cancel;
      if (state.phase !== "open" || !rec || !rec.proposal || (rec.status !== "review" && rec.status !== "not_recorded")) return false;
      if (typeof reason !== "string" || !reason.trim() || reason.length > 4000) return false;
      if (!rec.key) rec.key = randomKey("cancel");        // the same key on a resend: Core replays, never doubles
      rec.status = "sent"; rec.error = null; persistCancels(); emit();
      var r = await call("cancel", { command_key: rec.key, conversation_id: rec.conversationId,
        mission_id: rec.missionId, proposal_sha256: rec.sha, reason: reason.trim() });
      if (r.stale) return false;
      // The answer belongs to THIS record, whatever is selected now (G124-R1).
      if (r.ok && r.json.mission_id === rec.missionId) {
        rec.status = "recorded"; rec.receipt = r.json; rec.stage = r.json.stage; rec.missionStatus = r.json.mission_status;
      } else if (r.ok) {
        rec.status = "uncertain"; rec.error = "RECEIPT_MISMATCH";
      } else { rec.status = r.network || r.status >= 500 ? "uncertain" : "refused"; rec.error = r.code; }
      persistCancels(); emit();
      return r.ok;
    }

    async function cancelCheck(missionId) {
      var rec = missionId ? recordFor(missionId) : state.cancel;
      if (state.phase !== "open" || !rec || !rec.key || !rec.missionId) return false;
      var r = await call("cancel_receipt", { command_key: rec.key, conversation_id: rec.conversationId,
        mission_id: rec.missionId });
      if (r.stale) return false;
      if (!r.ok) { rec.error = r.code; emit(); return false; }
      rec.missionStatus = r.json.mission_status;
      if (r.json.status === "FOUND") { rec.status = "recorded"; rec.receipt = r.json.receipt; rec.stage = r.json.stage; rec.error = null; }
      else { rec.status = rec.proposal ? "not_recorded" : "unavailable"; rec.stage = null; }   // nothing recorded
      persistCancels(); emit();
      return true;
    }

    function cancelSelect(missionId) {
      var rec = recordFor(missionId);
      if (!rec) return false;
      state.cancel = rec; emit(); return true;
    }

    // ---- G101: media results linked to this conversation, read fresh from the server
    async function loadMedia() {
      if (state.phase !== "open") return false;
      var previous = state.media && state.media.results ? state.media.results : [];
      state.media = { status: "loading", results: previous, error: null };
      emit();
      var r = await call("media_results", { conversation_id: state.conversationId });
      if (r.stale) return false;
      state.media = r.ok && Array.isArray(r.json.results)
        ? { status: "ready", results: r.json.results, tickets: Array.isArray(r.json.tickets) ? r.json.tickets : [], error: null }
        : { status: "error", results: [], error: r.code || "INVALID_RESPONSE" };
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
      cancelPropose: cancelPropose, cancelSubmit: cancelSubmit, cancelCheck: cancelCheck, cancelSelect: cancelSelect,
      loadMedia: loadMedia,
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
    LEGACY_UNVERIFIABLE: "Historique ancien : seul l'état est connu, aucun fichier n'est affiché.",
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

  // G122: a media proposal, shown from Core's frozen fields only (the prompt is the normalized one).
  var AGENTS = { image: "Image", video: "Vidéo" };
  var OPERATIONS = { create: "création", edit: "retouche", analyze: "analyse" };
  function isMedia(p) { return !!p && p.protocol === "eidolon-media-proposal/1"; }
  function mediaRequestText(p) {
    return (AGENTS[p.agent] || p.agent) + " — " + (OPERATIONS[p.operation] || p.operation) + " : « " + p.prompt + " »";
  }
  function mediaMetaText(p) {
    var parts = ["Version " + p.version];
    if (p.artifact) parts.push("fichier joint " + p.artifact.artifact_id);
    if (p.format) parts.push("format " + p.format);
    if (p.duration_seconds) parts.push(p.duration_seconds + " s");
    return parts.join(" · ") + " · rien n'est lancé : après votre accord, l'opérateur lance le travail.";
  }
  // Ticket of Codex's queue (media-ticket/1). No state here is an achieved objective.
  var TICKET_STATES = {
    ACCEPTED: "Demande enregistrée — en attente du lancement par l'opérateur.",
    ATTEMPTED: "Tentative enregistrée — le moteur peut encore travailler ; effet à vérifier.",
    RETURNED: "Le moteur a répondu — résultat non vérifié.",
    REVIEW_REQUIRED: "Revue nécessaire — aucun nouvel essai automatique." };
  function ticketText(receipt) {
    return (TICKET_STATES[receipt.state] || "État reçu : " + receipt.state) +
      (receipt.failure_code ? " (" + receipt.failure_code + ")" : "");
  }
  function ticketView(submission) {
    if (!submission || !submission.receipt) return null;
    var r = submission.receipt;
    if (typeof r.ticket_id !== "string") return { stage: null, text: "Soumission : " + r.status };
    return { stage: r.state === "REVIEW_REQUIRED" ? "unknown_effect" : null, missionId: null,
      text: "Ticket " + r.ticket_id + " — " + ticketText(r) };
  }
  var OBSERVATIONS = {
    NOT_STARTED: "Pas encore lancé.",
    RECORDED_UNVERIFIED: "Résultat enregistré, non vérifié.",
    JOB_UNAVAILABLE_OR_CHANGED: "Journal du travail absent ou modifié : effet inconnu, rien n'est relancé.",
    COLLECTION_UNAVAILABLE_OR_CHANGED: "Collecte absente ou modifiée : effet inconnu, rien n'est relancé." };

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
    var previousReply = null;
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
      var media = isMedia(p);
      doc.getElementById("conv-proposal-request").textContent = media ? mediaRequestText(p) : p.request;
      doc.getElementById("conv-proposal-meta").textContent = media ? mediaMetaText(p) : "Version " + p.version +
        " · cible " + p.target_id + " · rien n'est lancé tant que vous ne validez pas.";
      doc.getElementById("conv-submit").textContent = media ? "Valider la demande" : "Valider et créer la mission";
      var s = st.submission;
      var sstate = doc.getElementById("conv-submission-state");
      sstate.textContent = !s ? LABELS.draft : s.status === "sent" ? "Validation envoyée…" :
        s.status === "uncertain" ? LABELS.uncertain + (s.error ? " (" + s.error + ")" : "") :
        s.status === "refused" ? (SUBMIT_ERRORS[s.error] || "Validation refusée (" + s.error + ").") : "Validation enregistrée.";
      doc.getElementById("conv-check").hidden = !(s && s.status === "uncertain");
      var mv = media ? ticketView(s) : missionView(s, missionStatus);
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
    if (c.status === "loading") return "Préparation de la proposition d'arrêt…";
    if (c.status === "choose") return CANCEL_CODES.MISSION_AMBIGUOUS;
    if (c.status === "restored") return "Demande d'arrêt envoyée avant le rechargement de la page : vérifiez son état, rien n'est renvoyé.";
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
    doc.getElementById("conv-cancel-check").hidden = !(c && c.key && (c.status === "uncertain" ||
      c.status === "restored" || (c.status === "recorded" && FINAL_STAGES.indexOf(c.stage) < 0)));
    // G124: other requests still to follow (sent meanwhile, or restored after a reload). Never resent.
    var pending = doc.getElementById("conv-cancel-pending");
    pending.textContent = "";
    var others = closed ? [] : (st.cancels || []).filter(function (r) {
      return r.key && (!c || r.missionId !== c.missionId) && FINAL_STAGES.indexOf(r.stage) < 0;
    });
    pending.hidden = !others.length;
    others.forEach(function (r) {
      var li = doc.createElement("li"), b = el(doc, "button", "media-secondary",
        "Suivre la demande d'arrêt de " + r.missionId + " — " + cancelStatusText(r));
      b.type = "button"; b.dataset.cancelSelect = r.missionId;
      li.appendChild(b); pending.appendChild(li);
    });
  }

  function renderMedia(doc, st, closed) {
    var m = closed ? null : st.media;
    var line = doc.getElementById("conv-media-state"), list = doc.getElementById("conv-media-list");
    list.textContent = "";
    var tickets = m && m.tickets ? m.tickets : [];
    var count = m ? m.results.length + tickets.length : 0;
    line.textContent = !m ? "" : m.status === "loading" ? "Lecture des résultats…" :
      m.status === "error" ? "Résultats indisponibles (" + m.error + ")." :
      !count ? "Aucune demande ni résultat image ou vidéo pour cette conversation." :
      count + " demande(s) ou résultat(s) lu(s) maintenant sur le serveur.";
    if (!m) return;
    // G123: the queue's own tickets first (exact job id reserved before running), then operator links.
    tickets.forEach(function (t) {
      var box = el(doc, "div", "conv-media-result");
      box.appendChild(el(doc, "p", "conv-kind", "Demande " + t.receipt.ticket_id));
      box.appendChild(el(doc, "p", "conv-state", ticketText(t.receipt)));
      box.appendChild(el(doc, "p", "help", OBSERVATIONS[t.observation] || ("Observation : " + t.observation)));
      if (t.result) {
        var body = el(doc, "div");
        renderMediaResult(doc, body, t.result);
        box.appendChild(body);
      }
      list.appendChild(box);
    });
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
    var conv = createConversation({ transport: deps.transport, storage: deps.storage || null, onChange: function (st) { render(doc, st, deps.missionStatus(st)); } });
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
    doc.getElementById("conv-cancel-pending").addEventListener("click", function (event) {
      var b = event.target.closest("button[data-cancel-select]");
      if (b && conv.cancelSelect(b.dataset.cancelSelect)) doc.getElementById("conv-cancel-check").focus();
    });
    doc.getElementById("conv-media-load").addEventListener("click", function () { conv.loadMedia(); });
    doc.getElementById("conv-follow").addEventListener("click", function (event) {
      var id = event.currentTarget.dataset.missionId;
      if (MISSION.test(id)) deps.follow(id);
    });
    render(doc, conv.state(), null);
    return { conversation: conv, refresh: function () { var st = conv.state(); render(doc, st, deps.missionStatus(st)); },
      clear: function () { conv.close(); } };
  }

  var api = { createConversation: createConversation, NOTES: NOTES, contextNote: contextNote, modelLabel: modelLabel, mediaRequestText: mediaRequestText, ticketView: ticketView, CANCEL_STAGES: CANCEL_STAGES, CANCEL_CODES: CANCEL_CODES, cancelStatusText: cancelStatusText, mediaResultLines: mediaResultLines, renderMediaResult: renderMediaResult, canonical: canonical, digest: digest, stageOf: stageOf, missionView: missionView, LABELS: LABELS, mount: mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonConversation = api;
})(typeof window !== "undefined" ? window : this);

/* ---- src/main.js ---- */
/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : main.js
 * Description : Démarrage navigateur du client connecté : fetch même origine, sans stockage (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  if (typeof document === "undefined") return;
  var C = root.EidolonConnected, V = root.EidolonConnectedView;
  var TIMEOUT_MS = 10000, AUTO_MS = 10000;

  // Same-origin, relative "/v1/..." paths only; no credentials, cache or redirect followed.
  function transport(method, path, body, token) {
    if (typeof path !== "string" || path.indexOf("/v1/") !== 0) return Promise.reject(new Error("PATH_REFUSED"));
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);
    var headers = { "Authorization": "Bearer " + token };
    var init = { method: method, headers: headers, cache: "no-store", credentials: "omit",
      redirect: "error", referrerPolicy: "no-referrer", signal: controller.signal };
    if (body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    return fetch(path, init).then(function (res) {
      return res.text().then(function (text) {
        var json = null;
        try { json = JSON.parse(text); } catch (err) { json = null; }
        return { status: res.status, json: json };
      });
    }).finally(function () { clearTimeout(timer); });
  }

  // The logo is an optional asset: a server that does not serve it keeps the text name (G078).
  function showLogo() {
    var logo = document.getElementById("brand-logo");
    if (!logo || typeof logo.decode !== "function") return;
    logo.decode().then(function () {
      if (!logo.naturalWidth) return;
      logo.hidden = false;
      document.getElementById("brand-name").hidden = true;
    }, function () { /* not served: the text name stays */ });
  }

  function start() {
    var autoTimer = null;
    showLogo();
    var media = root.EidolonMediaAgents.mount(document);
    window.addEventListener("pagehide", function () { media.clear(); });
    var conversation = null;
    var session = C.createSession({ transport: transport, onChange: function (s) {
      V.render(document, s);
      if (s.phase !== "connected" || !s.list.selection) stopAuto();
      if (conversation) conversation.refresh();
    } });
    // G088: the conversation follows its mission through the read session (same capture, same rules).
    // G124: unfinished cancellation requests (ids, key, digest; no secret) survive a reload in this tab only.
    var cancelStorage = null;
    try { cancelStorage = window.sessionStorage; } catch (e) { cancelStorage = null; }
    conversation = root.EidolonConversation.mount(document, {
      transport: transport,
      storage: cancelStorage,
      missionStatus: function (st) {
        var id = st.submission && st.submission.receipt && st.submission.receipt.mission_id;
        var sel = session.state().list.selection;
        var view = sel && sel.missionId === id && sel.sync && sel.sync.view;
        return view && view.mission ? view.mission.status : null;
      },
      follow: function (id) {
        session.relist().then(function () { return session.selectMission(id); }).then(function () {
          document.getElementById("details").scrollIntoView({ block: "start" });
        });
      }
    });
    window.addEventListener("pagehide", function () { conversation.clear(); });

    function stopAuto() {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
      document.getElementById("auto").checked = false;
    }

    document.getElementById("connect-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var input = document.getElementById("token");
      var value = input.value.trim();
      input.value = "";                    // the DOM never keeps the token
      // G037: success moves the focus to the mission list; a refusal keeps it on the token field.
      session.connect(value).then(function (ok) {
        if (ok) document.getElementById("missions").focus();
        else input.focus();
      });
    });
    document.getElementById("disconnect").addEventListener("click", function () { stopAuto(); session.disconnect(); media.clear(); });
    document.getElementById("relist").addEventListener("click", function () { session.relist(); });
    document.getElementById("refresh").addEventListener("click", function () { session.refreshSelection(); });
    document.getElementById("accept-reset").addEventListener("click", function () { session.acceptReset(); });
    document.getElementById("archives-load").addEventListener("click", function () { session.loadArchives(); });
    document.getElementById("archives-more").addEventListener("click", function () { session.moreArchives(); });
    document.getElementById("mission-list").addEventListener("click", function (event) {
      var button = event.target.closest("button[data-mission-id]");
      if (button) session.selectMission(button.dataset.missionId);
    });
    document.getElementById("receipt-form").addEventListener("submit", function (event) {
      event.preventDefault();
      session.lookupReceipt(document.getElementById("receipt-client").value.trim(),
        document.getElementById("receipt-key").value.trim());
    });
    document.getElementById("auto").addEventListener("change", function (event) {
      if (!event.target.checked) { stopAuto(); return; }
      autoTimer = setInterval(function () { session.refreshSelection(); }, AUTO_MS);
    });
    V.render(document, session.state());
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})(typeof window !== "undefined" ? window : this);
