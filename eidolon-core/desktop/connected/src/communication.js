/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : communication.js
 * Description : Micro, haut-parleur et caméra de la page : désactivés par défaut, voyant de capture, appui pour parler, anti-écho (G149)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Browser APIs are injected (deps), so every rule here is tested without a real device.
// deps.player(wavBase64) returns {done: Promise, stop()}; stop() must end playback at once AND resolve done.
// Manual mode rules (automatic mode is explicitly started separately): everything is OFF until the user switches it on; capture only while
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
    var cameraEpoch = 0, cameraStream = null, permissionEpoch = {microphone:0, camera:0};
    var sttKey = null, ttsKey = null, automaticDone = null, resetListeners = [];
    var manualDevice = { microphone:false, camera:false };

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
        var lost = !found.some(function (d) { return d.id === dev.selected; });
        // G165: the microphone unplugged while talking: capture dropped at once, nothing transcribed.
        if (lost && dev.selected !== null && kind === "microphone" && dev.state === "capturing") { cancelTalk(); dev.state = "disabled"; dev.reason = "débranché"; }
        if (kind === "camera" && !manualDevice.camera) {
          var pixy = found.find(function (d) { return /pixy/i.test(d.label); });
          if (pixy) { dev.selected = pixy.id; lost = false; }
        }
        if (lost) dev.selected = found.length ? (found.find(function (d) { return d.id === "default"; }) || found[0]).id : null;
        if (!found.length && dev.state !== "permission_denied") { dev.state = "unavailable"; dev.reason = null; }
        else if (found.length && dev.state === "unavailable") { dev.state = "disabled"; dev.reason = null; }
      });
      emit();
      return snapshotState();
    }

    async function enable(kind) {
      if (kind === "speaker") { set("speaker", "ready"); return snapshotState(); }
      var dev = st[kind];
      var permission = ++permissionEpoch[kind];
      // A browser may hide devices and identifiers until the first explicit permission request.
      var selection = dev.selected ? { deviceId: { exact: dev.selected } } : {};
      var constraints = kind === "microphone" ? { audio: dev.selected ? selection : true }
        : { video: Object.assign({}, selection, VIDEO) };
      try {
        var stream;
        try { stream = await deps.media.getUserMedia(constraints); }
        catch (error) {
          if (permission !== permissionEpoch[kind]) return snapshotState();
          // A remembered/just-enumerated device can disappear before capture. Try OS default once.
          if (!dev.selected || !["NotFoundError", "OverconstrainedError"].includes(error.name)) throw error;
          stream = await deps.media.getUserMedia(kind === "microphone" ? {audio:true} : {video:VIDEO});
          if (permission === permissionEpoch[kind]) dev.selected = null;
        }
        stopTracks(stream); // permission/discovery only: nothing kept open
        if (permission !== permissionEpoch[kind]) return snapshotState();
        await refresh();
        if (permission !== permissionEpoch[kind]) return snapshotState();
        set(kind, dev.selected ? "ready" : "unavailable");
      } catch (e) { if (permission === permissionEpoch[kind]) set(kind, errorState(e)); }
      return snapshotState();
    }

    function disable(kind) {
      if (kind !== "speaker") permissionEpoch[kind]++;
      if (kind === "microphone") cancelTalk();
      if (kind === "speaker") stopSpeaking();
      if (kind === "camera") { cameraEpoch++; stopTracks(cameraStream); cameraStream = null; }
      set(kind, st[kind].devices.length || kind === "speaker" ? "disabled" : "unavailable");
      return snapshotState();
    }

    function select(kind, id) {
      if (!st[kind].devices.some(function (d) { return d.id === id; })) return false;
      disable(kind);
      st[kind].selected = id; manualDevice[kind] = true;
      if (st[kind].state === "ready") st[kind].state = "disabled";   // a new device needs its own permission
      emit();
      return true;
    }

    async function startTalk(options) {
      options = options || {};
      if (st.microphone.state !== "ready") return false;
      stopSpeaking();                                                 // anti-echo: never listen to ourselves
      var stream, epoch = ++talkEpoch;
      try { stream = await deps.media.getUserMedia({ audio: { deviceId: { exact: st.microphone.selected }, channelCount: 1 } }); }
      catch (e) { if (epoch === talkEpoch) set("microphone", errorState(e)); return false; }
      if (epoch !== talkEpoch) { stopTracks(stream); return false; }
      try { talk = { stream: stream, recorder: deps.recorder(stream, options.onSamples), epoch: epoch }; }
      catch (error) { stopTracks(stream); set("microphone", "unavailable"); throw error; }
      // G165: a track that ends by itself (device unplugged, taken by the system) stops the capture.
      (stream.getTracks ? stream.getTracks() : []).forEach(function (track) {
        if (track.addEventListener) track.addEventListener("ended", function () {
          if (talk && talk.epoch === epoch) { cancelTalk(); set("microphone", "disabled", "débranché"); refresh(); }
        });
      });
      talk.timer = deps.setTimeout(function () { if (talk && talk.epoch === epoch) { if (options.onLimit) options.onLimit(); else stopTalk(); } }, max);
      set("microphone", "capturing");
      return true;
    }

    async function stopTalk() {
      if (!talk || st.microphone.state !== "capturing") return null;
      var t = talk; talk = null;
      deps.clearTimeout(t.timer);
      var audio;
      stopTracks(t.stream);
      try { audio = await t.recorder.stop(); }
      catch (error) {
        if (t.epoch === talkEpoch) set("microphone", "ready", "ERREUR");
        return null;
      } finally { stopTracks(t.stream); }
      if (t.epoch !== talkEpoch) { if (audio && audio.samples) audio.samples.fill(0); return null; }
      set("microphone", "processing");
      try {
        sttKey = deps.key();
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
      if (automaticDone) { var done = automaticDone; automaticDone = null; done(null); }
      talkEpoch++;
      if (talk) {
        var cancelled = talk; talk = null;
        deps.clearTimeout(cancelled.timer);
        try { Promise.resolve(cancelled.recorder.cancel()).catch(function () {}); }
        catch (error) { /* Device release must survive recorder cleanup failure. */ }
        finally { stopTracks(cancelled.stream); }
      }
      if (st.microphone.state === "processing" && sttKey) deps.transport("DELETE", "/v1/comm/stt", null, sttKey).catch(function () {});
      sttKey = null;
      if (st.microphone.state === "capturing" || st.microphone.state === "processing") set("microphone", "ready", "annulé");
    }

    function listenAutomatic() {
      return new Promise(function (resolve, reject) {
        if (automaticDone || st.microphone.state !== "ready") { reject(new Error("Micro indisponible")); return; }
        var finished = false;
        automaticDone = resolve;
        function finish(discard) {
          if (finished) return;
          finished = true;
          if (discard) { automaticDone = null; cancelTalk(); resolve({empty: true, text: ""}); return; }
          stopTalk().then(function (result) {
            if (automaticDone === resolve) { automaticDone = null; resolve(result); }
          }, function (error) {
            if (automaticDone === resolve) { automaticDone = null; reject(error); }
          });
        }
        var gate = (deps.createGate || root.EidolonAutoVoice.createGate)();
        startTalk({ onSamples: function (samples, rate) {
          if (finished) return;
          var end = gate.feed(samples, rate);
          if (end) finish(end === "silence");
        }, onLimit: function () { finish(true); } }).then(function (started) {
          if (!started && automaticDone === resolve) { automaticDone = null; reject(new Error("Micro indisponible")); }
        }).catch(function (error) {
          cancelTalk(); reject(error);
        });
      });
    }

    async function speak(text) {
      if (st.speaker.state !== "ready" && st.speaker.state !== "processing") return false;
      if (st.microphone.state === "capturing") return false;          // anti-echo
      var epoch = ++speakEpoch, index = 0, chunks = 1;
      ttsKey = deps.key();
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
        if (ttsKey) deps.transport("DELETE", "/v1/comm/tts", null, ttsKey).catch(function () {});
        ttsKey = null;
        set("speaker", "ready", "arrêté");
      }
    }

    async function snapshot(purpose) {
      if (st.camera.state !== "ready") return null;
      var stream, epoch = ++cameraEpoch;
      try { stream = await deps.media.getUserMedia({ video: Object.assign({ deviceId: { exact: st.camera.selected } }, VIDEO) }); }
      catch (e) { if (epoch === cameraEpoch) set("camera", errorState(e)); return null; }
      if (epoch !== cameraEpoch) { stopTracks(stream); return null; }
      cameraStream = stream;
      set("camera", "capturing");
      var image;
      try { image = await deps.grabFrame(stream); }
      catch (e) { if (epoch === cameraEpoch) set("camera", "ready", "ERREUR"); return null; }
      finally { stopTracks(stream); if (cameraStream === stream) cameraStream = null; }
      if (epoch !== cameraEpoch) { if (image && image.fill) image.fill(0); return null; }
      set("camera", "processing");
      try {
        var result = await call("POST", "/v1/comm/vision/describe?purpose=" + (purpose === "scene" ? "scene" : "presence"), image, "image/jpeg");
        if (epoch !== cameraEpoch) return null;
        set("camera", "ready");
        return result;
      } catch (e) { if (epoch === cameraEpoch) set("camera", "ready", e.code || "ERREUR"); return null; }
    }

    if (deps.media && deps.media.onDeviceChange) deps.media.onDeviceChange(function () { refresh(); });
    return { refresh: refresh, enable: enable, disable: disable, select: select, startTalk: startTalk,
      reset: function () { resetListeners.forEach(function (fn) { fn(); }); KINDS.forEach(disable); },
      onReset: function (fn) { resetListeners.push(fn); }, listenAutomatic: listenAutomatic,
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
      recorder: function (stream, onSamples) {
        var ctx = new AudioCtx(), source = ctx.createMediaStreamSource(stream);
        if (ctx.state === "suspended") ctx.resume().catch(function () {});
        var node = ctx.createScriptProcessor(4096, 1, 1), parts = [], length = 0, done = false;
        node.onaudioprocess = function (ev) {
          if (done) return;
          var chunk = new Float32Array(ev.inputBuffer.getChannelData(0)); parts.push(chunk); length += chunk.length;
          if (onSamples) onSamples(chunk, ctx.sampleRate);
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
          cancel: function () { parts = []; return finish(); }
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
        var ctx = new AudioCtx(), source = null, finish, fail, stopped = false;
        var done = new Promise(function (resolve, reject) { finish = resolve; fail = reject; });
        Promise.resolve(ctx.resume()).then(function () { return ctx.decodeAudioData(bytes(b64).buffer); }).then(function (buffer) {
          if (stopped) return;
          source = ctx.createBufferSource(); source.buffer = buffer; source.connect(ctx.destination);
          source.onended = function () { ctx.close(); finish(); };
          source.start();
        }, function () { ctx.close(); fail(new Error("Lecture audio indisponible")); });
        return { done: done, stop: function () { stopped = true; try { if (source) source.stop(); } catch (e) { /* ended */ } ctx.close(); finish(); } };
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
    var spoken = 0, voicePending = 0, activeConversation = null;
    var auto = root.EidolonAutoVoice && hooks && hooks.voiceSend ? root.EidolonAutoVoice.create({
      prepare: async function () {
        var state = await comm.enable("microphone");
        if (state.microphone.state !== "ready") throw new Error("Autorisez le micro avant de démarrer.");
        await comm.enable("speaker");
        spoken = doc.querySelectorAll("#conv-log .conv-reply").length;
      },
      listen: function () { return comm.listenAutomatic(); },
      cancel: function () { comm.cancelTalk(); comm.stopSpeaking(); },
      speak: function (text) { return comm.speak(text); },
      send: async function (text) {
        voicePending++;
        try { return await hooks.voiceSend(text); }
        finally { voicePending--; }
      },
      change: function (state, note) {
        $("voice-auto-state").textContent = note;
        $("voice-auto-start").hidden = state !== "off";
        $("voice-auto-stop").hidden = state === "off";
      }
    }) : null;
    if (auto) {
      $("voice-auto-start").addEventListener("click", function () { auto.start(); });
      $("voice-auto-stop").addEventListener("click", function () { auto.stop(); });
      comm.onReset(function () { auto.stop(); });
    }

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
        // Keep the user's permission gesture reachable even before enumeration exposes a device.
        box.disabled = false;
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
        if (auto) auto.stop();
        if (ev.target.checked) {
          if (kind === "speaker") spoken = doc.querySelectorAll("#conv-log .conv-reply").length;   // never read history
          comm.enable(kind);
        } else comm.disable(kind);
      });
    }
    toggle("comm-mic-on", "microphone"); toggle("comm-speaker-on", "speaker"); toggle("comm-camera-on", "camera");
    $("comm-mic-select").addEventListener("change", function (ev) { if (auto) auto.stop(); comm.select("microphone", ev.target.value); });
    $("comm-camera-select").addEventListener("change", function (ev) { comm.select("camera", ev.target.value); });
    $("comm-talk").addEventListener("click", function () {
      if (auto && auto.active()) { auto.stop(); return; }
      if (comm.state().microphone.state === "capturing") {
        comm.stopTalk().then(function (r) {
          if (!r) return;
          $("comm-note").textContent = r.empty ? "Rien n'a été entendu." : "Transcription placée dans le champ : relisez-la, puis envoyez."
            + (r.corrections && r.corrections.length ? " Corrigé : " + r.corrections.map(function (c) { return "« " + c.from + " » → « " + c.to + " »"; }).join(", ") + "." : "");
          if (!r.empty) { var area = $("conv-text"); area.value = (area.value ? area.value + " " : "") + r.text; area.focus(); }
        });
      } else comm.startTalk();
    });
    $("comm-talk-cancel").addEventListener("click", function () { if (auto) auto.stop(); comm.cancelTalk(); });
    $("comm-voice-stop").addEventListener("click", function () { if (auto) auto.stop(); comm.stopSpeaking(); });
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
      if (voicePending || (auto && auto.active())) return;
      var text = last.querySelector(".conv-text, .conv-note");
      if (text && text.textContent.trim()) comm.speak(text.textContent.trim().slice(0, 2000));
    });
    render(comm.state());
    comm.refresh();
    return { render: render, conversationChanged: function (id) {
      if (id === activeConversation) return;
      activeConversation = id;
      if (!id || !auto || !hooks.autoStart) return;
      // No auto-retry after Stop, device refusal or an uncertain send. One start per conversation.
      Promise.resolve().then(function () {
        if (activeConversation !== id) return;
        comm.enable("camera"); // permission/discovery only; tracks immediately released
        auto.start();          // voice failure does not block typed conversation
      });
    } };
  }

  var api = { createCommunication: createCommunication, browserDeps: browserDeps, mount: mount, encodeWav: encodeWav, indicator: indicator,
    errorState: errorState, LABELS: LABELS, MAX_TALK_MS: MAX_TALK_MS };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonCommunication = api;
})(typeof window !== "undefined" ? window : this);
