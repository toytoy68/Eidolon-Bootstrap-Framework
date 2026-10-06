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
