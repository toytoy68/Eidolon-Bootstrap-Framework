/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : resident-voice.js
 * Description : Cycle de vie du réveil local et des sessions vocales à la demande
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  // Adapter contract: waitWake() owns ONLY local detection; it must release
  // its microphone before settling, including cancellation. runSession() owns
  // the conversation microphone and releases it before settling. No adapter
  // may persist ambient audio or replay a message after an ambiguous failure.
  // This controller does not implement an acoustic detector or install one.
  function create(deps) {
    ["waitWake", "runSession", "connected", "change"].forEach(function (name) {
      if (!deps || typeof deps[name] !== "function") throw new TypeError(name + " required");
    });
    var wanted = false, worker = null, controller = null, state = "off", consent = false;
    var qualified = deps.qualified === true;
    function change(next, code) { state = next; deps.change({ state: next, code: code || null }); }
    async function loop(signal) {
      while (wanted && !signal.aborted) {
        change("standby");
        var detected = await deps.waitWake(signal);
        if (signal.aborted || !wanted) return;
        if (detected !== true) throw new Error("DETECTOR_ENDED");
        if (!deps.connected()) {
          // Stop until an explicit restart/connection event; do not buffer
          // speech for later transmission or retry the previous detection.
          wanted = false; change("offline", "SERVER_UNAVAILABLE"); return;
        }
        change("conversation");
        await deps.runSession(signal);
        // Completion returns to local detection, never to server transcription
        // of ambient speech. A rejected session is never retried automatically.
      }
    }
    function launch() {
      if (worker || !wanted) return;
      controller = new AbortController();
      var own = controller;
      worker = Promise.resolve().then(function () {
        if (!wanted || own.signal.aborted) return;
        return loop(own.signal);
      }).catch(function () {
        if (!own.signal.aborted) { wanted = false; change("error", "VOICE_INTERRUPTED"); }
      }).finally(function () {
        worker = null; controller = null;
        if (wanted) launch();
        else if (state === "stopping") change("off");
      });
    }
    function stop() {
      wanted = false;
      if (worker) { change("stopping"); controller.abort(); }
      else change("off");
    }
    return {
      consent: function (value) { consent = value === true; if (!consent) stop(); },
      start: function () {
        if (!consent) { change(worker ? "stopping" : "off", "MIC_CONSENT_REQUIRED"); return false; }
        if (!qualified) { change("unavailable", "DETECTOR_NOT_QUALIFIED"); return false; }
        wanted = true; launch(); return true;
      },
      stop: stop,
      state: function () { return state; },
      settled: function () { return worker || Promise.resolve(); }
    };
  }
  var api = { create: create };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonResidentVoice = api;
})(typeof window !== "undefined" ? window : this);
