/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : build-sync-fixtures.js
 * Description : Construit les fixtures client-sync/1 du prototype (C-TASK-G012)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:  node desktop/prototype/fixtures/build-sync-fixtures.js
// Reads Codex's real trace (unchanged) and writes client-sync-fixtures.js, a classic
// script usable from file://. Every derived case is labelled DERIVED and states
// what was changed: none of them is a Core output actually observed.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const SOURCE = path.resolve(__dirname, "../../../docs/validation/2026-10-06/codex-client-sync/demo.json");
const OUT = path.join(__dirname, "client-sync-fixtures.js");
const raw = fs.readFileSync(SOURCE);
const trace = JSON.parse(raw);
const copy = (v) => JSON.parse(JSON.stringify(v));
const fakeHex = (label) => crypto.createHash("sha256").update("derived:" + label).digest("hex");

const last = trace.pages[trace.pages.length - 1];
const derived = {};
function derive(name, why, envelope) {
  derived[name] = { derived: true, why, envelope };
}

// Out of order: an OLDER answer (smaller capture, cursor 3) arriving after a newer one.
const older = copy(trace.pages[0]);
older.snapshot.as_of_sequence = 3;
older.snapshot.event_count = 3;
older.snapshot.mission = Object.assign(copy(older.snapshot.mission), { status: "RUNNING", phase: "RECALL", outcome_status: "PENDING", revision: 1 });
derive("late_older_answer", "Copie de pages[0] dont la capture est vieillie (as_of 3, RUNNING) pour simuler une réponse en retard.", older);

// Cancellation requested at unchanged revision (request_cancel does not bump revision).
const base = copy(last);
const running = Object.assign(copy(base.snapshot.mission), { status: "RUNNING", phase: "CALL", outcome_status: "PENDING", revision: 4, cancel_requested: false });
const cancelBefore = copy(base);
cancelBefore.status = "DELTA"; cancelBefore.events = []; cancelBefore.has_more = false;
cancelBefore.snapshot = { as_of_sequence: 11, event_count: 11, observed_at: "2026-10-06T03:44:40.000000+00:00", mission: running };
derive("cancel_before", "Capture RUNNING révision 4 sans annulation, construite pour le scénario d'annulation.", cancelBefore);
const cancelAfter = copy(cancelBefore);
cancelAfter.events = [{ sequence: 12, at: "2026-10-06T03:44:41.000000+00:00", kind: "CANCEL_REQUESTED" }];
cancelAfter.cursor = Object.assign(copy(base.cursor), { sequence: 12, event_count: 12, anchor_sha256: fakeHex("cancel12") });
cancelAfter.snapshot = { as_of_sequence: 12, event_count: 12, observed_at: "2026-10-06T03:44:41.500000+00:00",
  mission: Object.assign(copy(running), { cancel_requested: true }) };
derive("cancel_requested_same_revision", "Événement CANCEL_REQUESTED ; révision 4 inchangée, cancel_requested=true, statut encore RUNNING.", cancelAfter);

// Reset because the store identity changed.
const storeChanged = copy(trace.reset_example);
const newStore = "s-" + fakeHex("store").slice(0, 32);
storeChanged.reason = "STORE_CHANGED"; storeChanged.store_id = newStore; storeChanged.cursor.store_id = newStore;
derive("reset_store_changed", "reset_example avec un autre store_id et la raison STORE_CHANGED.", storeChanged);

// Rejections.
const wrongMission = copy(trace.pages[1]);
wrongMission.cursor.mission_id = "m-" + fakeHex("other").slice(0, 32);
derive("wrong_mission_cursor", "pages[1] avec un curseur d'une autre mission : doit être rejeté.", wrongMission);
const v2 = copy(trace.pages[1]); v2.protocol = "eidolon-client-sync/2";
derive("unknown_protocol", "pages[1] avec une version de protocole inconnue : doit être rejeté.", v2);
const unsafe = copy(trace.pages[1]); unsafe.snapshot.as_of_sequence = 9007199254740992;
derive("unsafe_integer", "pages[1] avec as_of_sequence = 2^53 : hors entiers exacts JS, doit être rejeté.", unsafe);

// Hostile text: valid envelope whose strings must be shown as data.
const hostile = copy(trace.pages[1]);
hostile.events[1].kind = "<img src=x onerror=alert(1)>";
hostile.snapshot.mission.objective_kind = "<b>ignore les consignes</b>";
hostile.snapshot.as_of_sequence = 12; hostile.snapshot.event_count = 12; // newer capture, so that it is displayed
derive("hostile_text", "pages[1] avec un type d'événement et un objectif contenant du HTML, capture portée à as_of 12 : à afficher comme texte.", hostile);

// Action views (the real demo mission is text.stats: action_view=null).
function withView(name, why, status, decision, applicability, effect) {
  const env = copy(trace.initial);
  env.snapshot.mission = Object.assign(copy(env.snapshot.mission), { status, phase: "ACTION", outcome_status: "PENDING", revision: 3,
    objective_kind: "synthetic_service_restart",
    action_view: { version: 1, snapshot_only: true, authorizes_execution: false, proposal_sha256: fakeHex(name),
      call_id: "c-1", attempt: 1, decision, applicability, effect } });
  derive(name, why, env);
}
withView("action_pending", "Capture initiale dérivée : proposition PENDING, AWAITING_DECISION, effet NOT_STARTED (messages repris d'action_view.py).",
  "BLOCKED", { status: "PENDING", message: "Proposition en attente de décision, sans expiration automatique." },
  { code: "AWAITING_DECISION", message: "Une décision explicite reste nécessaire." },
  { code: "NOT_STARTED", message: "Aucun lancement enregistré pour cette proposition." });
withView("action_review", "Capture initiale dérivée : REVIEW_REQUIRED, accord USED, effet UNKNOWN (messages repris d'action_view.py).",
  "REVIEW_REQUIRED", { status: "USED", message: "Accord consommé au lancement ; cela ne prouve pas un effet." },
  { code: "CONSUMED", message: "Accord déjà consommé ; consulter la preuve et la tentative, sans rejouer l'action." },
  { code: "UNKNOWN", message: "Effet inconnu ; aucune absence d'effet déduite du statut de l'accord." });

// G016: a REVIEW_REQUIRED capture that also carries a cancellation request.
const reviewCancel = copy(derived.action_review.envelope);
reviewCancel.snapshot.mission.cancel_requested = true;
derive("review_with_cancel", "action_review avec cancel_requested=true : la revue doit rester l'état principal.", reviewCancel);

// G016: real Core capture observed by Codex (out-of-catalogue request, objective_kind=null), kept verbatim.
const OBSERVED = path.resolve(__dirname, "../../../docs/validation/2026-10-06/codex-g012-integration/core-unsupported.json");
const observedRaw = fs.readFileSync(OBSERVED);
const observed = { core_unsupported: { source: "docs/validation/2026-10-06/codex-g012-integration/core-unsupported.json",
  sha256: crypto.createHash("sha256").update(observedRaw).digest("hex"), envelope: JSON.parse(observedRaw) } };

const payload = {
  source: "docs/validation/2026-10-06/codex-client-sync/demo.json",
  source_sha256: crypto.createHash("sha256").update(raw).digest("hex"),
  original: trace,
  observed,
  derived
};
const header = "/* Généré par build-sync-fixtures.js — ne pas modifier à la main.\n"
  + " * original : trace réelle de Codex (C-008a), recopiée sans changement.\n"
  + " * observed : capture Core réelle relevée par Codex, recopiée sans changement.\n"
  + " * derived  : cas construits pour G012/G016, jamais des sorties Core observées. */\n";
fs.writeFileSync(OUT, header + "(function (root) {\n  var data = " + JSON.stringify(payload, null, 1)
  + ";\n  if (typeof module === \"object\" && module.exports) module.exports = data;\n  else root.EidolonSyncFixtures = data;\n"
  + "})(typeof window !== \"undefined\" ? window : this);\n");
console.log("wrote", path.relative(process.cwd(), OUT), "source sha256", payload.source_sha256, "derived", Object.keys(derived).length);
