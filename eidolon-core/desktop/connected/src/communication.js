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
        // G164: server-side vocabulary corrections are reported, never hidden.
        var corrections = Array.isArray(result.corrections) ? result.corrections.filter(function (c) {
          return c && typeof c.from === "string" && typeof c.to === "string";
        }).map(function (c) { return { from: c.from.slice(0, 40), to: c.to.slice(0, 40) }; }).slice(0, 16) : [];
        return { text: result.text, empty: result.empty, unverified: true, corrections: corrections };   // to the input field, not sent
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

  // ---- Real browser adapters (exercised by the Chromium recipe with fake devices) ----
  function browserDeps(win, key) {
    var nav = win.navigator && win.navigator.mediaDevices;
    var AudioCtx = win.AudioContext || win.webkitAudioContext;
    function bytes(b64) {
      var bin = win.atob(b64), out = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    }
    return {
      key: key,
      media: nav ? {
        enumerateDevices: function () { return nav.enumerateDevices(); },
        getUserMedia: function (c) { return nav.getUserMedia(c); },
        onDeviceChange: function (fn) { if (nav.addEventListener) nav.addEventListener("devicechange", fn); }
      } : { enumerateDevices: function () { return Promise.resolve([]); },
            getUserMedia: function () { var e = new Error("no media"); e.name = "NotFoundError"; return Promise.reject(e); } },
      // Microphone samples kept in memory only until "stop"; nothing is written anywhere.
      recorder: function (stream) {
        var ctx = new AudioCtx(), source = ctx.createMediaStreamSource(stream);
        var node = ctx.createScriptProcessor(4096, 1, 1), parts = [], length = 0, done = false;
        node.onaudioprocess = function (ev) {
          if (done) return;
          var chunk = new Float32Array(ev.inputBuffer.getChannelData(0)); parts.push(chunk); length += chunk.length;
        };
        source.connect(node); node.connect(ctx.destination);
        function finish() { done = true; try { source.disconnect(); node.disconnect(); } catch (e) { /* closed */ } return ctx.close(); }
        return {
          stop: function () {
            var all = new Float32Array(length), at = 0, rate = ctx.sampleRate;
            parts.forEach(function (p) { all.set(p, at); at += p.length; });
            parts = [];
            return finish().then(function () { return { samples: all, rate: rate }; });
          },
          cancel: function () { parts = []; finish(); }
        };
      },
      // One frame, scaled within 1280x720, encoded as JPEG in memory.
      grabFrame: function (stream) {
        var video = win.document.createElement("video");
        video.muted = true; video.playsInline = true; video.srcObject = stream;
        return video.play().then(function () {
          return new Promise(function (resolve) { if (video.videoWidth) resolve(); else video.onloadeddata = resolve; });
        }).then(function () {
          var scale = Math.min(1, 1280 / video.videoWidth, 720 / video.videoHeight);
          var canvas = win.document.createElement("canvas");
          canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
          canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
          video.srcObject = null;
          return new Promise(function (resolve) { canvas.toBlob(resolve, "image/jpeg", 0.85); });
        }).then(function (blob) { return blob.arrayBuffer(); }).then(function (buf) { return new Uint8Array(buf); });
      },
      // Web Audio from memory: no data:/blob: URL, so the page CSP stays unchanged. stop() resolves done.
      player: function (b64) {
        var ctx = new AudioCtx(), source = null, finish;
        var done = new Promise(function (resolve) { finish = resolve; });
        ctx.decodeAudioData(bytes(b64).buffer).then(function (buffer) {
          source = ctx.createBufferSource(); source.buffer = buffer; source.connect(ctx.destination);
          source.onended = function () { ctx.close(); finish(); };
          source.start();
        }, function () { ctx.close(); finish(); });
        return { done: done, stop: function () { try { if (source) source.stop(); } catch (e) { /* ended */ } ctx.close(); finish(); } };
      },
      transport: function (method, path, body, token, type) {
        var headers = { "Authorization": "Bearer " + token }, init = { method: method, headers: headers, cache: "no-store",
          credentials: "omit", redirect: "error", referrerPolicy: "no-referrer" };
        if (body instanceof Uint8Array) { headers["Content-Type"] = type || "application/octet-stream"; init.body = body; }
        else if (body !== null && body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
        return win.fetch(path, init).then(function (res) {
          return res.text().then(function (text) {
            var json = null;
            try { json = JSON.parse(text); } catch (e) { json = null; }
            return { status: res.status, json: json };
          });
        });
      },
      setTimeout: function (fn, ms) { return win.setTimeout(fn, ms); },
      clearTimeout: function (id) { win.clearTimeout(id); }
    };
  }

  // ---- Binding to the "Voix et caméra" block of index.html ----
  function mount(doc, comm, hooks) {
    function $(id) { return doc.getElementById(id); }
    var spoken = 0;
    function fill(select, dev) {
      var keep = select.value;
      while (select.firstChild) select.removeChild(select.firstChild);
      dev.devices.forEach(function (d) {
        var o = doc.createElement("option"); o.value = d.id; o.textContent = d.label; select.appendChild(o);
      });
      select.value = dev.selected || keep || "";
      select.disabled = !dev.devices.length;
    }
    function render(s) {
      [["mic", "microphone"], ["speaker", "speaker"], ["camera", "camera"]].forEach(function (pair) {
        var dev = s[pair[1]], line = $("comm-" + pair[0] + "-state");
        line.textContent = dev.indicator.text;
        line.className = "comm-indicator " + dev.indicator.tone + (dev.indicator.recording ? " recording" : "");
        var box = $("comm-" + pair[0] + "-on");
        box.checked = ["ready", "capturing", "processing"].indexOf(dev.state) !== -1;
        box.disabled = dev.state === "unavailable" && pair[1] !== "speaker";
      });
      fill($("comm-mic-select"), s.microphone);
      fill($("comm-camera-select"), s.camera);
      var talking = s.microphone.state === "capturing";
      $("comm-talk").disabled = !(s.microphone.state === "ready" || talking);
      $("comm-talk").setAttribute("aria-pressed", talking ? "true" : "false");
      $("comm-talk").textContent = talking ? "Terminer" : "Parler";
      $("comm-talk-cancel").hidden = !(talking || s.microphone.state === "processing");
      $("comm-voice-stop").hidden = s.speaker.state !== "processing";
      $("comm-presence").disabled = $("comm-scene").disabled = s.camera.state !== "ready";
    }
    comm.onChange(render);
    function toggle(id, kind) {
      $(id).addEventListener("change", function (ev) {
        if (ev.target.checked) {
          if (kind === "speaker") spoken = doc.querySelectorAll("#conv-log .conv-reply").length;   // never read history
          comm.enable(kind);
        } else comm.disable(kind);
      });
    }
    toggle("comm-mic-on", "microphone"); toggle("comm-speaker-on", "speaker"); toggle("comm-camera-on", "camera");
    $("comm-mic-select").addEventListener("change", function (ev) { comm.select("microphone", ev.target.value); });
    $("comm-camera-select").addEventListener("change", function (ev) { comm.select("camera", ev.target.value); });
    $("comm-talk").addEventListener("click", function () {
      if (comm.state().microphone.state === "capturing") {
        comm.stopTalk().then(function (r) {
          if (!r) return;
          $("comm-note").textContent = r.empty ? "Rien n'a été entendu." : "Transcription placée dans le champ : relisez-la, puis envoyez."
            + (r.corrections && r.corrections.length ? " Corrigé : " + r.corrections.map(function (c) { return "« " + c.from + " » → « " + c.to + " »"; }).join(", ") + "." : "");
          if (!r.empty) { var area = $("conv-text"); area.value = (area.value ? area.value + " " : "") + r.text; area.focus(); }
        });
      } else comm.startTalk();
    });
    $("comm-talk-cancel").addEventListener("click", function () { comm.cancelTalk(); });
    $("comm-voice-stop").addEventListener("click", function () { comm.stopSpeaking(); });
    function look(purpose) {
      comm.snapshot(purpose).then(function (r) {
        if (!r) return;
        $("comm-note").textContent = (r.present ? (r.people_count > 1 ? r.people_count + " personnes visibles. " : "Une personne visible. ")
          : "Personne n'est visible. ") + (purpose === "scene" ? r.description : "") + " (observation non vérifiée)";
      });
    }
    $("comm-presence").addEventListener("click", function () { look("presence"); });
    $("comm-scene").addEventListener("click", function () { look("scene"); });
    // Read each NEW reply aloud when the voice is on (the text of Core's reply, as shown).
    var log = $("conv-log");
    if (log && hooks && hooks.observe) hooks.observe(log, function () {
      var replies = doc.querySelectorAll("#conv-log .conv-reply");
      if (replies.length <= spoken) { spoken = Math.min(spoken, replies.length); return; }
      var last = replies[replies.length - 1];
      spoken = replies.length;
      var text = last.querySelector(".conv-text, .conv-note");
      if (text && text.textContent.trim()) comm.speak(text.textContent.trim().slice(0, 2000));
    });
    render(comm.state());
    comm.refresh();
    return { render: render };
  }

  var api = { createCommunication: createCommunication, browserDeps: browserDeps, mount: mount, encodeWav: encodeWav, indicator: indicator,
    errorState: errorState, LABELS: LABELS, MAX_TALK_MS: MAX_TALK_MS };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonCommunication = api;
})(typeof window !== "undefined" ? window : this);
