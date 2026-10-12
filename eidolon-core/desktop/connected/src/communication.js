/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : communication.js
 * Description : Micro, haut-parleur et caméra de la page : désactivés par défaut, voyant de capture, appui pour parler, anti-écho (G149)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Browser APIs are injected (deps), so every rule here is tested without a real device.
// deps.player(wavBase64) returns {done: Promise, stop()}; stop() must end playback at once AND resolve done.
// Rules (docs/COMMUNICATION.md §2): everything is OFF until the user switches it on; capture only while
// the user holds "talk" or asks one snapshot; the capture indicator is on for exactly that time; the
// transcript is returned to the page as editable text, never sent as a turn by itself; speaking stops
// when the user talks (anti-echo); no recording is kept; a missing device never blocks typed text.
(function (root) {
  "use strict";
  var KINDS = ["microphone", "camera", "speaker"];
  var DEVICE_KIND = { audioinput: "microphone", videoinput: "camera" };
  var LABELS = {
    unavailable: "indisponible", permission_denied: "refusé — à autoriser dans Windows et le navigateur",
    disabled: "désactivé", ready: "prêt", capturing: "capture en cours", processing: "traitement en cours",
    busy: "occupé par une autre application", stopped: "arrêté"
  };
  var NAMES = { microphone: "Micro", camera: "Caméra", speaker: "Voix d'Eidolon" };
  var VIDEO = { width: { max: 1280 }, height: { max: 720 }, frameRate: { max: 15 } };
  var MAX_TALK_MS = 30000;

  // Float samples at any rate -> 16 kHz mono 16-bit PCM WAV (the server contract), linear resampling.
  function encodeWav(samples, inputRate) {
    var ratio = inputRate / 16000, count = Math.floor(samples.length / ratio);
    var out = new Uint8Array(44 + count * 2), view = new DataView(out.buffer);
    function text(at, s) { for (var i = 0; i < s.length; i++) out[at + i] = s.charCodeAt(i); }
    text(0, "RIFF"); view.setUint32(4, 36 + count * 2, true); text(8, "WAVE"); text(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true);
    view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, count * 2, true);
    for (var i = 0; i < count; i++) {
      var pos = i * ratio, left = Math.floor(pos), frac = pos - left;
      var a = samples[left] || 0, b = samples[Math.min(left + 1, samples.length - 1)] || 0;
      var v = Math.max(-1, Math.min(1, a + (b - a) * frac));
      view.setInt16(44 + i * 2, v < 0 ? v * 32768 : v * 32767, true);
    }
    return out;
  }

  function errorState(err) {
    var name = err && err.name;
    if (name === "NotAllowedError" || name === "SecurityError") return "permission_denied";
    if (name === "NotFoundError" || name === "OverconstrainedError") return "unavailable";
    if (name === "NotReadableError" || name === "AbortError") return "busy";
    return "unavailable";
  }

  function stopTracks(stream) {
    if (stream && stream.getTracks) stream.getTracks().forEach(function (t) { t.stop(); });
  }

  function indicator(kind, device) {
    var label = NAMES[kind] + " : " + (LABELS[device.state] || device.state);
    if (device.reason) label += " (" + device.reason + ")";
    var tone = device.state === "capturing" ? "recording" : device.state === "processing" ? "busy"
      : device.state === "ready" ? "ok" : "off";
    return { text: label, tone: tone, recording: device.state === "capturing" };
  }

  function createCommunication(deps) {
    var max = deps.maxTalkMs || MAX_TALK_MS;
    var st = {};
    KINDS.forEach(function (k) { st[k] = { state: k === "speaker" ? "disabled" : "unavailable", devices: [], selected: null, reason: null }; });
    var listeners = [], talk = null, speakEpoch = 0, player = null, talkEpoch = 0;

    function emit() { listeners.forEach(function (fn) { fn(snapshotState()); }); }
    function set(kind, state, reason) { st[kind].state = state; st[kind].reason = reason || null; emit(); }
    function snapshotState() {
      var copy = {};
      KINDS.forEach(function (k) { copy[k] = { state: st[k].state, devices: st[k].devices.slice(), selected: st[k].selected, reason: st[k].reason, indicator: indicator(k, st[k]) }; });
      copy.capturing = st.microphone.state === "capturing" || st.camera.state === "capturing";
      return copy;
    }
    async function call(method, path, body, type) {
      var res = await deps.transport(method, path, body, deps.key(), type);
      if (res.status !== 200) {
        var code = (res.json && res.json.error) || ("HTTP_" + res.status);
        var e = new Error(code); e.code = code; throw e;
      }
      return res.json;
    }

    async function refresh() {
      var list = [];
      try { list = await deps.media.enumerateDevices(); } catch (e) { list = []; }
      ["microphone", "camera"].forEach(function (kind) {
        var found = list.filter(function (d) { return DEVICE_KIND[d.kind] === kind; }).map(function (d, i) {
          return { id: d.deviceId, label: d.label || (NAMES[kind] + " " + (i + 1)) };
        });
        var dev = st[kind];
        dev.devices = found;
        if (!found.some(function (d) { return d.id === dev.selected; })) dev.selected = found.length ? found[0].id : null;
        if (!found.length && dev.state !== "permission_denied") { dev.state = "unavailable"; dev.reason = null; }
        else if (found.length && dev.state === "unavailable") { dev.state = "disabled"; dev.reason = null; }
      });
      emit();
      return snapshotState();
    }

    async function enable(kind) {
      if (kind === "speaker") { set("speaker", "ready"); return snapshotState(); }
      var dev = st[kind];
      if (!dev.selected) { set(kind, "unavailable"); return snapshotState(); }
      var constraints = kind === "microphone" ? { audio: { deviceId: { exact: dev.selected } } }
        : { video: Object.assign({ deviceId: { exact: dev.selected } }, VIDEO) };
      try {
        stopTracks(await deps.media.getUserMedia(constraints));       // permission only: nothing kept open
        await refresh();
        set(kind, "ready");
      } catch (e) { set(kind, errorState(e)); }
      return snapshotState();
    }

    function disable(kind) {
      if (kind === "microphone") cancelTalk();
      if (kind === "speaker") stopSpeaking();
      set(kind, st[kind].devices.length || kind === "speaker" ? "disabled" : "unavailable");
      return snapshotState();
    }

    function select(kind, id) {
      if (!st[kind].devices.some(function (d) { return d.id === id; })) return false;
      st[kind].selected = id;
      if (st[kind].state === "ready") st[kind].state = "disabled";   // a new device needs its own permission
      emit();
      return true;
    }

    async function startTalk() {
      if (st.microphone.state !== "ready") return false;
      stopSpeaking();                                                 // anti-echo: never listen to ourselves
      var stream;
      try { stream = await deps.media.getUserMedia({ audio: { deviceId: { exact: st.microphone.selected }, channelCount: 1 } }); }
      catch (e) { set("microphone", errorState(e)); return false; }
      var epoch = ++talkEpoch;
      talk = { stream: stream, recorder: deps.recorder(stream), epoch: epoch };
      talk.timer = deps.setTimeout(function () { if (talk && talk.epoch === epoch) stopTalk(); }, max);
      set("microphone", "capturing");
      return true;
    }

    async function stopTalk() {
      if (!talk || st.microphone.state !== "capturing") return null;
      var t = talk; talk = null;
      deps.clearTimeout(t.timer);
      var audio;
      try { audio = await t.recorder.stop(); } finally { stopTracks(t.stream); }
      set("microphone", "processing");
      try {
        var result = await call("POST", "/v1/comm/stt", encodeWav(audio.samples, audio.rate), "audio/wav");
        if (t.epoch !== talkEpoch) return null;                       // cancelled meanwhile: late answer dropped
        set("microphone", "ready");
        return { text: result.text, empty: result.empty, unverified: true };   // to the input field, not sent
      } catch (e) {
        if (t.epoch === talkEpoch) set("microphone", "ready", e.code || "ERREUR");
        return null;
      }
    }

    function cancelTalk() {
      talkEpoch++;
      if (talk) { deps.clearTimeout(talk.timer); talk.recorder.cancel(); stopTracks(talk.stream); talk = null; }
      if (st.microphone.state === "processing") deps.transport("DELETE", "/v1/comm/stt", null, deps.key()).catch(function () {});
      if (st.microphone.state === "capturing" || st.microphone.state === "processing") set("microphone", "ready", "annulé");
    }

    async function speak(text) {
      if (st.speaker.state !== "ready" && st.speaker.state !== "processing") return false;
      if (st.microphone.state === "capturing") return false;          // anti-echo
      var epoch = ++speakEpoch, index = 0, chunks = 1;
      set("speaker", "processing");
      try {
        while (index < chunks && epoch === speakEpoch) {
          var part = await call("POST", "/v1/comm/tts", { text: text, index: index });
          if (epoch !== speakEpoch) break;
          chunks = part.chunks;
          player = deps.player(part.wav_base64);
          await player.done;
          index++;
        }
      } catch (e) {
        if (epoch === speakEpoch) { set("speaker", "ready", e.code || "ERREUR"); return false; }
      }
      if (epoch === speakEpoch) set("speaker", "ready");
      return epoch === speakEpoch;
    }

    function stopSpeaking() {
      var wasSpeaking = st.speaker.state === "processing";
      speakEpoch++;
      if (player) { player.stop(); player = null; }
      if (wasSpeaking) {
        deps.transport("DELETE", "/v1/comm/tts", null, deps.key()).catch(function () {});
        set("speaker", "ready", "arrêté");
      }
    }

    async function snapshot(purpose) {
      if (st.camera.state !== "ready") return null;
      var stream;
      try { stream = await deps.media.getUserMedia({ video: Object.assign({ deviceId: { exact: st.camera.selected } }, VIDEO) }); }
      catch (e) { set("camera", errorState(e)); return null; }
      set("camera", "capturing");
      var image;
      try { image = await deps.grabFrame(stream); } finally { stopTracks(stream); }   // one frame, camera off at once
      set("camera", "processing");
      try {
        var result = await call("POST", "/v1/comm/vision/describe?purpose=" + (purpose === "scene" ? "scene" : "presence"), image, "image/jpeg");
        set("camera", "ready");
        return result;
      } catch (e) { set("camera", "ready", e.code || "ERREUR"); return null; }
    }

    if (deps.media && deps.media.onDeviceChange) deps.media.onDeviceChange(function () { refresh(); });
    return { refresh: refresh, enable: enable, disable: disable, select: select, startTalk: startTalk,
      stopTalk: stopTalk, cancelTalk: cancelTalk, speak: speak, stopSpeaking: stopSpeaking, snapshot: snapshot,
      state: snapshotState, onChange: function (fn) { listeners.push(fn); } };
  }

  var api = { createCommunication: createCommunication, encodeWav: encodeWav, indicator: indicator,
    errorState: errorState, LABELS: LABELS, MAX_TALK_MS: MAX_TALK_MS };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonCommunication = api;
})(typeof window !== "undefined" ? window : this);
