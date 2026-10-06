/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : probe.cjs
 * Description : Reproduction indépendante des écarts G012 à cc9a64b
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const assert = require("node:assert/strict");
const S = require("../../../../desktop/prototype/sync-state.js");
const F = require("../../../../desktop/prototype/fixtures/client-sync-fixtures.js");
const actual = require("./core-unsupported.json");
const rejection = S.validateEnvelope(actual);
assert.equal(actual.snapshot.mission.objective_kind, null);
assert.equal(rejection, "INVALID_MISSION");
let state = S.receive(S.createState(), F.original.initial, {epoch: 0});
state = S.receive(state, F.original.reset_example, {epoch: 0});
const before = state.view.asOf;
state = S.receive(state, F.original.pages[0], {epoch: 0});
assert.ok(state.reset);
assert.ok(state.view.asOf > before);
const review = {...F.derived.action_review.envelope.snapshot.mission, cancel_requested: true};
assert.equal(review.status, "REVIEW_REQUIRED");
const label = S.missionLabel(review);
assert.equal(label, "Annulation demandée — pas encore confirmée");
process.stdout.write(JSON.stringify({
  realCoreUnsupported: {objective: actual.snapshot.mission.objective_kind,
    status: actual.snapshot.mission.status, rejection},
  pendingReset: {before, after: state.view.asOf, resetStillPending: !!state.reset},
  cancelledReview: {status: review.status, label}
}, null, 2) + "\n");
