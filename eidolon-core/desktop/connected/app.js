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

  function missionLabel(mission) {
    if (!mission) return "Aucune capture";
    var av = mission.action_view;
    if (mission.status === "REVIEW_REQUIRED") return "Revue requise — effet à vérifier"; // stays primary, even with a cancel request
    if (mission.cancel_requested && !/^(CANCELLED|SUCCEEDED|FAILED|ABANDONED)$/.test(mission.status)) return "Annulation demandée — issue non confirmée";
    switch (mission.status) {
      case "NEW": return "Nouvelle";
      case "RUNNING": return "En cours (capture ; ne prouve pas qu'un processus vit encore)";
      case "BLOCKED":
        if (av && av.decision.status === "PENDING" && av.applicability.code === "AWAITING_DECISION") return "À décider";
        if (mission.outcome_status === "CLARIFICATION") return "Bloquée — précision demandée";
        return "Bloquée — motif à consulter";
      case "REVIEW_REQUIRED": return "Revue requise — effet à vérifier";
      case "SUCCEEDED": return mission.outcome_status === "ACHIEVED" ? "Réussie — résultat daté" : "Terminée (issue " + mission.outcome_status + ")";
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
    nextRequest: nextRequest, missionLabel: missionLabel, cancelNote: cancelNote, summary: summary };
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
 */
(function (root) {
  "use strict";
  var NODE = typeof module === "object" && module.exports;
  var S = NODE ? require("../../prototype/sync-state.js") : root.EidolonSync;
  var L = NODE ? require("../../prototype/mission-list-state.js") : root.EidolonMissionList;

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
    if (env.status === "NOT_FOUND") return env.receipt === null ? null : "INVALID_RECEIPT";
    if (env.status !== "FOUND") return "UNKNOWN_STATUS";
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

  function createSession(options) {
    var transport = options.transport;
    var now = options.now || function () { return new Date().toISOString(); };
    var onChange = options.onChange || function () {};
    var token = null;
    var loops = { list: 0, selection: 0, receipt: 0 };

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

    function forgetReceipt() { loops.receipt += 1; state.receipt = null; }

    function wipe() {
      forgetReceipt();
      state.list = L.createState();
      state.storeId = null;
      state.lastSuccessAt = null;
    }

    function fail(phase, code, scope) {
      state.phase = phase;
      state.problem = { code: code, at: now(), scope: scope };
      setOnline(false);
    }

    // One request; returns { ok, json } or { ok:false } after recording the failure.
    async function call(method, path, body, scope) {
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
      if (status === 200) return { ok: true, json: json };
      var code = errorCode(json);
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
      if (state.phase !== "connected") return;
      state.list = L.relist(state.list);
      emit();
      await loadList();
      if (state.list.selection) await refreshSelection();
    }

    async function loadList() {
      var mine = ++loops.list;
      for (var i = 0; i < MAX_LIST_PAGES; i++) {
        if (mine !== loops.list || state.phase !== "connected") return;
        var req = L.nextPageRequest(state.list);
        if (!req) return;
        var body = req.cursor ? { cursor: req.cursor, limit: PAGE_LIMIT } : { limit: PAGE_LIMIT };
        var r = await call("POST", "/v1/missions", body, "list");
        if (r.stale) return;
        var meta = { kind: "list", epoch: req.epoch, cursor: req.cursor, receivedAt: now(), source: "serveur" };
        if (r.ok) {
          state.list = L.receivePage(state.list, r.json, meta);
          if (state.list.storeId && state.list.storeId !== state.storeId) {
            // The list answered for another store than /v1/health: never shown together.
            wipe(); fail("refused", "STORE_IDENTITY_CHANGED", "list");
            emit();
            return;
          }
          state.lastSuccessAt = meta.receivedAt;
        } else if (r.code) {
          state.list = L.receiveError(state.list, r.code, meta);
        }
        emit();
        if (!r.ok) return;
      }
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
        if (mine !== loops.selection || state.phase !== "connected") return false;
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
          state.list = L.receiveSelection(state.list, r.json, meta);
          state.lastSuccessAt = meta.receivedAt;
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
      if (state.phase !== "connected" || state.resyncRequired || !sel || !state.storeId) return false;
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
          state.receipt = { query: q, status: r.json.status, receipt: clone(r.json.receipt), code: null, receivedAt: at };
          state.lastSuccessAt = at;
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

    return { connect: connect, disconnect: disconnect, relist: relist, selectMission: selectMission,
      refreshSelection: refreshSelection, acceptReset: acceptReset, lookupReceipt: lookupReceipt,
      state: snapshot, hasToken: hasToken };
  }

  var api = { PROTOCOL: PROTOCOL, TOKEN: TOKEN, KEY: KEY, RECEIPT_KINDS: RECEIPT_KINDS, createSession: createSession,
    validateHealth: validateHealth, validateReceiptAnswer: validateReceiptAnswer,
    errorCode: errorCode, missionLabel: S.missionLabel, cancelNote: S.cancelNote, listSummary: L.summary,
    shownItems: L.shownItems, syncSummary: S.summary };
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

  var RECEIPT_ERRORS = {
    INVALID_QUERY: "Identifiant client ou clé invalide : 1 à 80 caractères A-Z, a-z, 0-9, « _ », « . », « - », commençant par une lettre ou un chiffre. Rien n'a été envoyé.",
    INVALID_RECEIPT_QUERY: "Requête refusée par Core (identifiants invalides).",
    STORE_CHANGED: "La base n'a plus l'identité affichée : se reconnecter pour resynchroniser. Aucun renvoi.",
    RECEIPT_MISSION_MISMATCH: "Cette clé existe mais pour une autre mission : aucune conclusion automatique.",
    RECEIPT_UNAVAILABLE: "Reçu illisible ou incohérent dans la base : l'incertitude reste entière."
  };

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
    var view = sel.sync && sel.sync.view;
    if (view) {
      var m = view.mission;
      var now = kind === "decision" ? (m.action_view ? m.action_view.decision.status : "aucune proposition") : m.status;
      row(doc, dl, "Capture actuelle", now + " (capture du " + fmt(view.observedAt) + ")");
    }
    out.appendChild(dl);
  }

  function render(doc, s) {
    renderConnection(doc, s);
    renderList(doc, s);
    renderDetails(doc, s);
    renderReceipt(doc, s);
  }

  var api = { render: render, PHASES: PHASES };
  if (NODE) module.exports = api;
  else root.EidolonConnectedView = api;
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

  function start() {
    var autoTimer = null;
    var session = C.createSession({ transport: transport, onChange: function (s) {
      V.render(document, s);
      if (s.phase !== "connected" || !s.list.selection) stopAuto();
    } });

    function stopAuto() {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
      document.getElementById("auto").checked = false;
    }

    document.getElementById("connect-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var input = document.getElementById("token");
      var value = input.value.trim();
      input.value = "";                    // the DOM never keeps the token
      session.connect(value);
    });
    document.getElementById("disconnect").addEventListener("click", function () { stopAuto(); session.disconnect(); });
    document.getElementById("relist").addEventListener("click", function () { session.relist(); });
    document.getElementById("refresh").addEventListener("click", function () { session.refreshSelection(); });
    document.getElementById("accept-reset").addEventListener("click", function () { session.acceptReset(); });
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
