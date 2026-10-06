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
