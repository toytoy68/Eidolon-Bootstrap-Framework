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
