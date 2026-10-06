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
    if (!isObject(m) || m.id !== env.mission_id || !safeInt(m.revision, 0) || !text(m.status, 40) || !text(m.phase, 40)
        || typeof m.cancel_requested !== "boolean" || !(m.objective_kind === null || text(m.objective_kind, 80)) // null: no catalogue objective (G016)
        || !text(m.outcome_status, 40)
        || !isObject(m.progress) || !safeInt(m.progress.completed, 0)
        || !(m.progress.total === null || safeInt(m.progress.total, 0))) return "INVALID_MISSION";
    var av = validateActionView(m.action_view);
    if (av) return av;
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

  var api = { PROTOCOL: PROTOCOL, MAX_REFS: MAX_REFS, createState: createState, validateEnvelope: validateEnvelope,
    receive: receive, receiveError: receiveError, acceptReset: acceptReset, setConnection: setConnection,
    nextRequest: nextRequest, missionLabel: missionLabel, cancelNote: cancelNote, summary: summary };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonSync = api;
})(typeof window !== "undefined" ? window : this);
