/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : build-list-fixtures.js
 * Description : Construit les fixtures mission-list/1 du prototype (C-TASK-G018)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:  node desktop/prototype/fixtures/build-list-fixtures.js
// Reads Codex's mission-list trace (C-008e, unchanged, with its SHA-256) and writes
// mission-list-fixtures.js, a classic script usable from file://.
// - observed : the Core trace, verbatim. Badge "observé".
// - derived  : every other case, each with what was built or changed. Badge "dérivé".
//   No derived case is presented as a Core output.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const REL = "docs/validation/2026-10-06/codex-mission-list/demo.json";
const SOURCE = path.resolve(__dirname, "../../..", REL);
const SYNC_FIXTURES = path.join(__dirname, "client-sync-fixtures.js");
const OUT = path.join(__dirname, "mission-list-fixtures.js");
const raw = fs.readFileSync(SOURCE);
const trace = JSON.parse(raw);
const copy = (v) => JSON.parse(JSON.stringify(v));
const hex = (label) => crypto.createHash("sha256").update("derived:" + label).digest("hex");
const mid = (label) => "m-" + hex(label).slice(0, 32);

// The client-sync fixtures (G012/G016) give observed or derived projections to reuse.
const syncSandbox = {};
new Function("window", fs.readFileSync(SYNC_FIXTURES, "utf8"))(syncSandbox);
const SF = syncSandbox.EidolonSyncFixtures;

const derived = {};
function derive(name, why, value) { derived[name] = { derived: true, why, value }; }

function page(storeId, generation, items, hasMore) {
  const env = { protocol: "eidolon-mission-list/1", snapshot_only: true, authorizes_execution: false, store_id: storeId,
    status: "PAGE", observed_at: "2026-10-06T09:00:00.000000+00:00", generation: copy(generation),
    items, has_more: hasMore, next_cursor: null };
  if (hasMore) env.next_cursor = { version: 1, store_id: storeId, generation: copy(generation), after_id: items[items.length - 1].mission.id };
  return env;
}

// Empty store: Core's generation for zero events (sequence 0, anchor null).
const emptyStore = "s-" + hex("empty-store").slice(0, 32);
derive("empty_store", "Page construite selon mission_list.py pour une base sans mission : génération 0, ancre null, aucun item.",
  page(emptyStore, { sequence: 0, event_count: 0, mission_count: 0, anchor_sha256: null }, [], false));

// One page mixing statuses that must not be confused (ids sorted as Core sorts them).
const variedStore = "s-" + hex("varied-store").slice(0, 32);
const unsupported = copy(SF.observed.core_unsupported.envelope.snapshot.mission);
const review = copy(SF.derived.review_with_cancel.envelope.snapshot.mission);
const running = copy(SF.derived.cancel_requested_same_revision.envelope.snapshot.mission);
const done = Object.assign(copy(SF.original.pages[SF.original.pages.length - 1].snapshot.mission), {});
const variedItems = [
  ["objective-null", unsupported, 3, "projection Core observée (G016, objective_kind=null), id changé"],
  ["review-cancel", review, 9, "projection dérivée review_with_cancel (G016), id changé"],
  ["running-cancel", running, 12, "projection dérivée cancel_requested_same_revision (G012), id changé"],
  ["finished", done, 15, "dernière projection de la trace client-sync C-008a, id changé"]
].map(([label, mission, asOf, origin]) => ({ label, origin, item: { as_of_sequence: asOf, mission: Object.assign(copy(mission), { id: mid(label) }) } }))
  .sort((a, b) => (a.item.mission.id < b.item.mission.id ? -1 : 1));
derive("varied_page", "Une page complète de 4 missions : " + variedItems.map((v) => v.origin).join(" ; ") + ".",
  page(variedStore, { sequence: 16, event_count: 16, mission_count: 4, anchor_sha256: hex("varied-anchor") }, variedItems.map((v) => v.item), false));

// 250 missions in 3 pages: the inventory stops at 200 and says so.
const bigStore = "s-" + hex("big-store").slice(0, 32);
const bigGen = { sequence: 500, event_count: 500, mission_count: 250, anchor_sha256: hex("big-anchor") };
const proto = copy(trace.fresh_pages[1].items[0].mission);
const bigIds = Array.from({ length: 250 }, (_, i) => mid("big-" + i)).sort();
const bigPages = [0, 100, 200].map((start) => {
  const items = bigIds.slice(start, start + 100).map((id, i) => ({ as_of_sequence: 2 * (start + i) + 1, mission: Object.assign(copy(proto), { id }) }));
  return page(bigStore, bigGen, items, start + 100 < 250);
});
derive("big_inventory", "250 missions synthétiques sur 3 pages (100, 100, 50), copies de la projection observée m-6083… avec des id dérivés.", bigPages);

// Rejections.
const obs = trace.fresh_pages;
const authority = copy(obs[0]); authority.authorizes_execution = true;
derive("authority_claimed", "fresh_pages[0] avec authorizes_execution=true : doit être rejeté.", authority);
const unsafe = copy(obs[0]); unsafe.items[0].as_of_sequence = 9007199254740992;
derive("unsafe_integer", "fresh_pages[0] avec as_of_sequence = 2^53 : doit être rejeté.", unsafe);
const mixed = copy(obs[1]);
mixed.generation = Object.assign(copy(mixed.generation), { sequence: 5, event_count: 5, anchor_sha256: hex("mixed") });
mixed.next_cursor.generation = copy(mixed.generation);
derive("mixed_generation", "fresh_pages[1] d'une autre génération (5) que la page 1 (4) : jamais fusionnée.", mixed);
const hostile = copy(obs[0]); hostile.items[0].mission.objective_kind = "<img src=x onerror=alert(1)>";
derive("hostile_text", "fresh_pages[0] avec un objective_kind contenant du HTML : affiché comme texte.", hostile);

// Selection: Core has no client-sync capture for these ids in the traces, so each snapshot is
// DERIVED from the observed list projection (same store, id, revision, status), never measured.
const selection = {};
obs.concat([derived.varied_page.value]).forEach((p) => p.items.forEach((it) => {
  const m = it.mission;
  selection[m.id] = { protocol: "eidolon-client-sync/1", snapshot_only: true, authorizes_execution: false, store_id: p.store_id,
    mission_id: m.id, status: "SNAPSHOT", events: [], has_more: false,
    cursor: { version: 1, store_id: p.store_id, mission_id: m.id, sequence: it.as_of_sequence, event_count: it.as_of_sequence, anchor_sha256: hex("sel-" + m.id) },
    snapshot: { as_of_sequence: it.as_of_sequence, event_count: it.as_of_sequence, observed_at: "2026-10-06T08:19:29.000000+00:00", mission: copy(m) } };
}));
derive("selection_snapshots", "Enveloppes client-sync/1 SNAPSHOT construites depuis les projections de la liste (pages observées et page dérivée varied_page ; même store, id, statut) ; ancre et heure dérivées.", selection);
const otherStore = copy(selection[obs[0].items[0].mission.id]);
otherStore.store_id = "s-" + hex("other-store").slice(0, 32); otherStore.cursor.store_id = otherStore.store_id;
derive("selection_other_store", "Capture de sélection venant d'un autre store_id que la liste : refusée.", otherStore);

const out = {
  observed: { trace: { source: REL, sha256: crypto.createHash("sha256").update(raw).digest("hex"),
    note: "Trace Core C-008e recopiée sans changement (MissionList.page, base synthétique, aucun réseau).",
    initial_page: trace.initial_page, fresh_pages: trace.fresh_pages, changed_between_pages: trace.changed_between_pages } },
  derived
};
const header = "/* ==========================================================\n"
  + " * Projet      : Eidolon Core\n * Organisation: Eidolon Core Technologies (ECT)\n"
  + " * Fichier     : mission-list-fixtures.js\n"
  + " * Description : Fixtures mission-list/1 générées par build-list-fixtures.js (C-TASK-G018)\n"
  + " * Standard    : Eidolon Presentation Standard v1\n"
  + " * ========================================================== */\n"
  + "// GENERATED — do not edit. observed = Core trace verbatim; derived = labelled constructions.\n";
fs.writeFileSync(OUT, header + "(function (root) {\n  \"use strict\";\n  var F = " + JSON.stringify(out, null, 1)
  + ";\n  if (typeof module === \"object\" && module.exports) module.exports = F;\n  else root.EidolonListFixtures = F;\n})(typeof window !== \"undefined\" ? window : this);\n");
console.log("wrote", path.relative(process.cwd(), OUT), "observed sha256", out.observed.trace.sha256, "derived", Object.keys(derived).length);
