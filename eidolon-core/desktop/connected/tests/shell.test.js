/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : shell.test.js
 * Description : Œil d'activité et bouton DARME : faits seulement, caméra jamais confondue avec l'activité (G176)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../src/shell.js");

const comm = (mic, cam, speaker) => ({ microphone: { state: mic }, camera: { state: cam }, speaker: { state: speaker || "disabled" } });

test("eye: closed conversation, then ready, listening, thinking, speaking", () => {
  assert.equal(S.eyeState({ phase: "closed", comm: null }).text, "Conversation fermée · caméra indisponible");
  assert.equal(S.eyeState({ phase: "open", comm: comm("disabled", "disabled") }).text, "Eidolon disponible · caméra éteinte");
  assert.equal(S.eyeState({ phase: "open", comm: comm("capturing", "disabled") }).activity, "écoute");
  assert.equal(S.eyeState({ phase: "open", pending: true, comm: comm("ready", "ready") }).activity, "réfléchit");
  assert.equal(S.eyeState({ phase: "open", comm: comm("ready", "ready", "processing") }).activity, "parle");
});

test("eye: work in progress never looks like a capture; the camera state is the real one", () => {
  const thinking = S.eyeState({ phase: "open", pending: true, comm: comm("ready", "ready") });
  assert.deepEqual([thinking.busy, thinking.cameraActive, thinking.camera], [true, false, "éteinte"]);
  const analysing = S.eyeState({ phase: "open", comm: comm("ready", "processing") });
  assert.deepEqual([analysing.cameraActive, analysing.camera], [false, "image en analyse, caméra éteinte"]);
  const capturing = S.eyeState({ phase: "open", comm: comm("ready", "capturing") });
  assert.deepEqual([capturing.cameraActive, capturing.camera], [true, "active"]);
  for (const [state, word] of [["permission_denied", "refusée"], ["busy", "occupée ailleurs"], ["unavailable", "indisponible"]]) {
    assert.equal(S.eyeState({ phase: "open", comm: comm("ready", state) }).camera, word);
  }
});

function monitorState(machines, extra) {
  return Object.assign({ phase: "ok", error: null, data: { machines } }, extra || {});
}
const machine = (badge, state, alerts) => ({ state: state || "ok", darme: { badge, unacknowledged_alerts: alerts || 0 } });

test("DARME button: no colour without data, grey stays grey, the worst machine wins", () => {
  assert.deepEqual(S.darmeSummary({ phase: "off" }), { level: "off", text: "DARME · conversation fermée" });
  assert.equal(S.darmeSummary({ phase: "idle" }).text, "DARME · non lu");
  assert.equal(S.darmeSummary({ phase: "error", data: null }).level, "error");
  assert.deepEqual(S.darmeSummary(monitorState([machine("grey")])), { level: "grey", text: "DARME · gris" });
  assert.equal(S.darmeSummary(monitorState([machine("gold"), { state: "unavailable", darme: null }])).level, "unknown");
  assert.equal(S.darmeSummary(monitorState([machine("gold", "stale")])).text, "DARME · périmé");
});

test("DARME button: a real alert stays visible with its count; a stale red is not counted as current", () => {
  assert.deepEqual(S.darmeSummary(monitorState([machine("grey"), machine("red", "ok", 2)])), { level: "red", text: "DARME · 2 alerte(s)" });
  assert.equal(S.darmeSummary(monitorState([machine("red", "stale", 3)])).level, "stale");
  assert.match(S.darmeSummary(monitorState([machine("grey")], { error: "MONITOR_UNREACHABLE" })).text, /dernière lecture en échec/);
});

test("eye colour key follows the real activity only; the camera never changes it", () => {
  const key = (phase, c, pending) => S.eyeState({ phase, pending, comm: c }).key;
  assert.equal(key("closed", null), "closed");
  assert.equal(key("open", comm("ready", "ready")), "idle");
  assert.equal(key("open", comm("capturing", "ready")), "listening");
  assert.equal(key("open", comm("ready", "ready"), true), "thinking");
  assert.equal(key("open", comm("ready", "ready", "processing")), "speaking");
  assert.equal(key("open", comm("ready", "capturing")), "idle");     // red ring = camera, not an activity colour
});
