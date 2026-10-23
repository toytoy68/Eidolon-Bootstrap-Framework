/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : duplex-voice.js
 * Description : Contrôleur d'interruption vocale (barge-in), sans audio ni réseau — G296
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
/* Clean-room design (Claude, G296). Not bundled in app.js yet: lot V2 wires it.
 *
 * The microphone stays open while Eidolon speaks. Each 20-100 ms frame carries a
 * level (RMS) and, when a local VAD runs, a speech probability. During playback,
 * a barge-in needs BOTH sustained speech and a level above the echo PEAK learnt
 * from the playback itself (residual echo after the browser's echo cancellation).
 * On barge-in the playback is stopped in the same call, pending speech is dropped,
 * and the utterance starts with the frames heard before the decision (pre-roll),
 * so the first syllables are not lost. Every decision carries a generation number:
 * a late callback from a stopped turn is ignored. No audio leaves this module.
 */
(function (root) {
  "use strict";
  var DEFAULTS = {
    bargeInMs: 240,        // sustained speech needed to interrupt
    graceMs: 300,          // ignore the first ms of playback (speaker ramp, AEC convergence)
    prerollMs: 600,        // frames kept before the decision and handed to the utterance
    minRms: 0.02,          // absolute floor for speech during playback
    echoMargin: 1.5,       // speech must exceed this multiple of the learnt echo peak
    echoDecay: 0.98,       // per rejected frame: the echo peak slowly follows a quieter answer
    vadThreshold: 0.5,     // used when frames carry a VAD probability
    echoLearnMs: 200       // first ms after the grace: echo peak learnt, no interruption
  };

  function create(deps, options) {
    var o = {}, k;
    for (k in DEFAULTS) o[k] = DEFAULTS[k];
    for (k in (options || {})) if (Object.prototype.hasOwnProperty.call(DEFAULTS, k)) o[k] = options[k];
    if (!deps || typeof deps.stopPlayback !== "function" || typeof deps.beginUtterance !== "function")
      throw new TypeError("stopPlayback and beginUtterance are required");
    var state = "idle", generation = 0, playStart = 0, voiced = 0, onset = null;
    var echo = { ms: 0, floor: 0 }, preroll = [], prerollMs = 0;
    var stats = { bargeIns: 0, rejectedEcho: 0, falseBargeIns: 0, latencies: [] };

    function speechLike(frame) {
      if (typeof frame.vad === "number") return frame.vad >= o.vadThreshold;
      return frame.rms >= o.minRms;
    }
    function keep(frame) {
      preroll.push(frame); prerollMs += frame.ms;
      while (preroll.length > 1 && prerollMs - preroll[0].ms >= o.prerollMs) prerollMs -= preroll.shift().ms;
    }
    function reset() { voiced = 0; onset = null; preroll = []; prerollMs = 0; }

    function speaking(at) {        // Eidolon starts playing an answer
      generation++; state = "speaking"; playStart = at; echo = { ms: 0, floor: 0 }; reset();
      return generation;
    }
    function finished(token) {     // playback ended by itself
      if (token !== generation || state !== "speaking") return false;
      state = "idle"; reset(); return true;
    }
    function frame(f) {
      if (!f || typeof f.rms !== "number" || !(f.rms >= 0) || !(f.ms > 0) || typeof f.at !== "number")
        throw new TypeError("frame {at, ms, rms[, vad]} required");
      if (state !== "speaking") return null;
      keep(f);
      if (f.at - playStart < o.graceMs) return null;
      if (echo.ms < o.echoLearnMs) {
        // The residual echo of Eidolon's own voice is speech to a VAD: learn its level from
        // every frame of this short window, whatever the VAD says, and never interrupt in it.
        echo.ms += f.ms; echo.floor = Math.max(echo.floor, f.rms);
        return null;
      }
      var loudEnough = f.rms >= o.minRms && f.rms >= echo.floor * o.echoMargin;
      if (speechLike(f) && loudEnough) {
        if (onset === null) onset = f.at;
        voiced += f.ms;
        if (voiced >= o.bargeInMs) {
          var token = generation;
          state = "listening";
          deps.stopPlayback(token);                      // same call: no extra frame of speech
          var latency = f.at + f.ms - onset;
          stats.bargeIns++; stats.latencies.push(latency);
          var handed = preroll.slice(), started = onset; reset();
          deps.beginUtterance({ generation: token, preroll: handed, onsetAt: started });
          return { event: "barge-in", generation: token, latencyMs: latency };
        }
        return null;
      }
      if (speechLike(f) && !loudEnough) stats.rejectedEcho++;
      if (!speechLike(f) || !loudEnough) {
        echo.floor = Math.max(echo.floor * o.echoDecay, f.rms);
        voiced = 0; onset = null;
      }
      return null;
    }
    function outcome(token, transcript) {   // called with the STT result of an interrupting utterance
      if (token !== generation || state !== "listening") return false;
      if (typeof transcript !== "string" || !transcript.trim()) stats.falseBargeIns++;
      state = "idle"; return true;
    }
    function stop() { generation++; state = "idle"; reset(); }
    return {
      speaking: speaking, finished: finished, frame: frame, outcome: outcome, stop: stop,
      state: function () { return state; },
      stats: function () {
        var l = stats.latencies.slice().sort(function (a, b) { return a - b; });
        return { bargeIns: stats.bargeIns, rejectedEcho: stats.rejectedEcho, falseBargeIns: stats.falseBargeIns,
                 latencyMedianMs: l.length ? l[Math.floor((l.length - 1) / 2)] : null,
                 latencyMaxMs: l.length ? l[l.length - 1] : null, echoFloor: echo.floor };
      }
    };
  }
  var api = { create: create, DEFAULTS: DEFAULTS };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonDuplexVoice = api;
})(typeof window !== "undefined" ? window : this);
