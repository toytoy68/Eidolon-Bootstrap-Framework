/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : communication.test.js
 * Description : Micro/caméra/voix de la page sur périphériques simulés : défaut éteint, refus, voyant, anti-écho (G149)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const M = require("../src/communication.js");

function fakeMedia(devices, opts) {
  opts = opts || {};
  const open = [], calls = [];
  let change = null;
  return {
    open, calls,
    enumerateDevices: async () => devices.slice(),
    getUserMedia: async (c) => {
      calls.push(c);
      if (opts.error) { const e = new Error("x"); e.name = opts.error; throw e; }
      const track = { stopped: false, stop() { this.stopped = true; }, ended: [],
        addEventListener(type, fn) { if (type === "ended") this.ended.push(fn); },
        end() { this.stopped = true; this.ended.forEach((fn) => fn()); } };
      open.push(track);
      return { getTracks: () => [track] };
    },
    onDeviceChange: (fn) => { change = fn; },
    fire: () => change && change(),
    live: () => open.filter((t) => !t.stopped).length
  };
}

function setup(over) {
  over = over || {};
  const media = over.media || fakeMedia([{ kind: "audioinput", deviceId: "mic1", label: "" },
    { kind: "videoinput", deviceId: "cam1", label: "Webcam" }]);
  const sent = [], timers = [];
  const transport = over.transport || (async (method, path, body) => {
    sent.push({ method, path, body });
    if (path === "/v1/comm/stt") return { status: 200, json: { text: "Diagnostique le NAS.", empty: false,
      corrections: [{ from: "toi-toi", to: "toytoy", count: 1 }, { from: 5, to: "x" }] } };
    if (path === "/v1/comm/tts") return { status: 200, json: { wav_base64: "UklGRg==", index: body.index, chunks: 2, last: body.index === 1 } };
    if (path.startsWith("/v1/comm/vision")) return { status: 200, json: { present: true, people_count: 1, identity: null } };
    return { status: 200, json: {} };
  });
  const players = [];
  const comm = M.createCommunication({
    createGate: require("../src/auto-voice.js").createGate,
    media, transport, key: () => "ecc_" + "A".repeat(43),
    recorder: over.recorder || (() => ({ stop: async () => ({ samples: new Float32Array(48000).fill(0.1), rate: 48000 }), cancel() { this.cancelled = true; } })),
    grabFrame: async () => new Uint8Array([0xff, 0xd8, 0xff, 0xd9]),
    player: (b64) => {
      let finish; const p = { b64, stopped: false, stop() { this.stopped = true; finish(); } };
      p.done = new Promise((r) => { finish = r; if (!over.slowPlayer) r(); });   // contract: stop() resolves done
      players.push(p); return p;
    },
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; }, clearTimeout: () => {},
    maxTalkMs: 30000
  });
  return { comm, media, sent, timers, players };
}

test("everything is off by default; devices found are disabled, not capturing", async () => {
  const { comm, media } = setup();
  const s = await comm.refresh();
  assert.equal(s.microphone.state, "disabled");
  assert.equal(s.camera.state, "disabled");
  assert.equal(s.speaker.state, "disabled");
  assert.equal(s.capturing, false);
  assert.equal(media.calls.length, 0);                               // no permission asked by itself
  assert.equal(s.microphone.devices[0].label, "Micro 1");             // no label before permission
});

test("no device: unavailable, and typed text is untouched", async () => {
  const { comm } = setup({ media: fakeMedia([]) });
  const s = await comm.refresh();
  assert.equal(s.microphone.state, "unavailable");
  assert.equal(s.camera.state, "unavailable");
  assert.equal(await comm.startTalk(), false);
  assert.equal(await comm.snapshot("presence"), null);
});

test("permission refused, busy webcam, device gone", async () => {
  for (const [name, state] of [["NotAllowedError", "permission_denied"], ["NotReadableError", "busy"], ["NotFoundError", "unavailable"]]) {
    const { comm } = setup({ media: fakeMedia([{ kind: "videoinput", deviceId: "cam1", label: "W" }], { error: name }) });
    await comm.refresh();
    const s = await comm.enable("camera");
    assert.equal(s.camera.state, state, name);
    assert.equal(s.camera.indicator.recording, false);
  }
  assert.match(M.LABELS.permission_denied, /autoriser dans Windows/);
});

test("enabling asks permission once and keeps nothing open", async () => {
  const { comm, media } = setup();
  await comm.refresh();
  const s = await comm.enable("microphone");
  assert.equal(s.microphone.state, "ready");
  assert.equal(media.live(), 0);
});

test("push to talk: indicator on only while capturing, transcript returned as text, not sent as a turn", async () => {
  const { comm, media, sent } = setup();
  await comm.refresh(); await comm.enable("microphone");
  assert.equal(await comm.startTalk(), true);
  assert.equal(comm.state().microphone.indicator.recording, true);
  assert.equal(comm.state().capturing, true);
  const result = await comm.stopTalk();
  assert.deepEqual(result, { text: "Diagnostique le NAS.", empty: false, unverified: true,
    corrections: [{ from: "toi-toi", to: "toytoy" }] });                // G164: reported, malformed ones dropped
  assert.equal(comm.state().microphone.state, "ready");
  assert.equal(comm.state().capturing, false);
  assert.equal(media.live(), 0);                                      // track stopped right after
  assert.deepEqual(sent.map((c) => c.path), ["/v1/comm/stt"]);        // never /v1/conversations/turn
  const wav = sent[0].body;
  assert.equal(String.fromCharCode(...wav.slice(0, 4)), "RIFF");
  assert.equal(new DataView(wav.buffer).getUint32(24, true), 16000);
});

test("talk stops by itself at the 30 s limit", async () => {
  const { comm, timers } = setup();
  await comm.refresh(); await comm.enable("microphone");
  await comm.startTalk();
  assert.equal(timers[0].ms, 30000);
  await timers[0].fn();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(comm.state().microphone.state, "ready");
});

test("cancel while capturing drops the audio and sends nothing", async () => {
  const { comm, sent, media } = setup();
  await comm.refresh(); await comm.enable("microphone");
  await comm.startTalk();
  comm.cancelTalk();
  assert.equal(comm.state().microphone.state, "ready");
  assert.equal(comm.state().microphone.reason, "annulé");
  assert.equal(media.live(), 0);
  assert.equal(await comm.stopTalk(), null);
  assert.equal(sent.length, 0);
});

test("double press does not start two captures", async () => {
  const { comm, media } = setup();
  await comm.refresh(); await comm.enable("microphone");
  assert.equal(await comm.startTalk(), true);
  assert.equal(await comm.startTalk(), false);
  assert.equal(media.calls.length, 2);                                // permission + one capture only
});

test("speech is chunk by chunk, and talking stops it at once (anti-echo)", async () => {
  const ctx = setup({ slowPlayer: true });
  const { comm, sent, players } = ctx;
  await comm.refresh(); await comm.enable("speaker"); await comm.enable("microphone");
  const speaking = comm.speak("Bonjour toytoy. Tout va bien.");
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(comm.state().speaker.state, "processing");
  await comm.startTalk();                                             // the user talks: the voice stops
  assert.equal(players[0].stopped, true);
  assert.equal(await speaking, false);
  assert.ok(sent.some((c) => c.method === "DELETE" && c.path === "/v1/comm/tts"));
  assert.equal(sent.filter((c) => c.path === "/v1/comm/tts" && c.method === "POST").length, 1);
  assert.equal(await comm.speak("Encore ?"), false);                  // never while the microphone captures
});

test("speech plays every chunk when nothing interrupts", async () => {
  const { comm, sent } = setup();
  await comm.refresh(); await comm.enable("speaker");
  assert.equal(await comm.speak("Une. Deux."), true);
  assert.deepEqual(sent.filter((c) => c.method === "POST").map((c) => c.body.index), [0, 1]);
});

test("snapshot: one frame, camera released at once, result without identity", async () => {
  const { comm, media, sent } = setup();
  await comm.refresh(); await comm.enable("camera");
  const result = await comm.snapshot("presence");
  assert.equal(result.identity, null);
  assert.equal(media.live(), 0);
  assert.equal(sent[0].path, "/v1/comm/vision/describe?purpose=presence");
  assert.equal(comm.state().camera.state, "ready");
  const constraints = media.calls[media.calls.length - 1].video;
  assert.deepEqual([constraints.width.max, constraints.height.max, constraints.frameRate.max], [1280, 720, 15]);
});

test("hot-plug: a new camera is listed; the selected one gone falls back", async () => {
  const devices = [{ kind: "videoinput", deviceId: "cam1", label: "A" }];
  const media = fakeMedia(devices);
  const { comm } = setup({ media });
  await comm.refresh();
  devices.push({ kind: "videoinput", deviceId: "cam2", label: "B" });
  assert.equal(comm.select("camera", "cam2"), false);                 // not listed yet
  await comm.refresh();
  assert.equal(comm.select("camera", "cam2"), true);
  devices.splice(1, 1);
  await comm.refresh();
  assert.equal(comm.state().camera.selected, "cam1");
});

test("server errors keep the page usable", async () => {
  const { comm } = setup({ transport: async () => ({ status: 503, json: { error: "ENGINE_UNAVAILABLE" } }) });
  await comm.refresh(); await comm.enable("microphone");
  await comm.startTalk();
  assert.equal(await comm.stopTalk(), null);
  assert.equal(comm.state().microphone.state, "ready");
  assert.equal(comm.state().microphone.reason, "ENGINE_UNAVAILABLE");
});

test("WAV encoding resamples to 16 kHz mono 16-bit", () => {
  const wav = M.encodeWav(new Float32Array(48000).fill(1), 48000);
  const view = new DataView(wav.buffer);
  assert.equal(view.getUint32(40, true), 32000);                      // 1 s at 16 kHz, 2 bytes per sample
  assert.equal(view.getInt16(44, true), 32767);
  assert.equal(view.getUint16(22, true), 1);
});

test("G165: microphone unplugged while talking: capture dropped, nothing sent, state explains why", async () => {
  const devices = [{ kind: "audioinput", deviceId: "mic1", label: "USB" }, { kind: "videoinput", deviceId: "cam1", label: "W" }];
  const { comm, media, sent } = setup({ media: fakeMedia(devices) });
  await comm.refresh(); await comm.enable("microphone");
  await comm.startTalk();
  media.open[media.open.length - 1].end();                    // the track ends by itself (unplugged)
  await new Promise((r) => setImmediate(r));
  const s = comm.state();
  assert.deepEqual([s.microphone.state, s.microphone.reason, s.capturing], ["disabled", "débranché", false]);
  assert.equal(media.live(), 0);
  assert.equal(await comm.stopTalk(), null);
  assert.deepEqual(sent.filter((c) => c.path === "/v1/comm/stt"), []);
});

test("G165: the selected microphone disappears from the list during capture (devicechange)", async () => {
  const devices = [{ kind: "audioinput", deviceId: "mic1", label: "USB" }, { kind: "audioinput", deviceId: "mic2", label: "Intégré" }];
  const media = fakeMedia(devices);
  const { comm, sent } = setup({ media });
  await comm.refresh(); await comm.enable("microphone");
  await comm.startTalk();
  devices.splice(0, 1);                                       // USB microphone gone
  media.fire();
  await new Promise((r) => setImmediate(r));
  const s = comm.state();
  assert.deepEqual([s.microphone.state, s.microphone.reason, s.microphone.selected, s.capturing], ["disabled", "débranché", "mic2", false]);
  assert.equal(media.live(), 0);
  assert.deepEqual(sent.filter((c) => c.path === "/v1/comm/stt"), []);
});


test("G281: explicit permission reveals devices hidden before consent, then closes tracks", async () => {
  for (const [kind, deviceKind] of [["microphone", "audioinput"], ["camera", "videoinput"]]) {
    const devices = [], media = fakeMedia(devices);
    const get = media.getUserMedia;
    media.getUserMedia = async (constraints) => {
      const stream = await get(constraints);
      devices.push({kind: deviceKind, deviceId: "revealed", label: "Device"});
      return stream;
    };
    const {comm, sent} = setup({media});
    await comm.refresh();
    assert.equal(media.calls.length, 0);
    const state = await comm.enable(kind);
    assert.equal(state[kind].state, "ready");
    assert.equal(state[kind].selected, "revealed");
    assert.equal(media.calls[0][kind === "microphone" ? "audio" : "video"].deviceId, undefined);
    assert.equal(media.live(), 0);
    assert.equal(sent.length, 0);
  }
});

test("G281: permission rejection with an empty list stays a rejection", async () => {
  const {comm, media} = setup({media: fakeMedia([], {error: "NotAllowedError"})});
  await comm.refresh();
  assert.equal((await comm.enable("camera")).camera.state, "permission_denied");
  assert.equal(media.calls.length, 1);
  assert.equal(media.live(), 0);
});


test("G282: automatic segmentation releases the microphone before STT; silence never leaves PC", async () => {
  let sample;
  const recorder = (stream, callback) => { sample = callback; return {stop: async () => ({samples:new Float32Array(16000).fill(.1),rate:16000}),cancel(){}}; };
  const f=setup({recorder}); await f.comm.refresh(); await f.comm.enable("microphone");
  let result=f.comm.listenAutomatic(); await new Promise(r=>setImmediate(r));
  for(let i=0;i<100;i++)sample(new Float32Array(1600),16000);
  assert.equal((await result).empty,true);assert.equal(f.sent.length,0);assert.equal(f.media.live(),0);
  result=f.comm.listenAutomatic(); await new Promise(r=>setImmediate(r));
  for(let i=0;i<3;i++)sample(new Float32Array(1600).fill(.1),16000);
  for(let i=0;i<15;i++)sample(new Float32Array(1600),16000);
  assert.equal((await result).text,"Diagnostique le NAS.");assert.equal(f.media.live(),0);assert.equal(f.sent.length,1);
});

test("G282: stopping while permission is pending releases late tracks and drops capture", async () => {
  const f=setup();await f.comm.refresh();await f.comm.enable("microphone");
  const get=f.media.getUserMedia;let release;
  f.media.getUserMedia=async c=>{await new Promise(r=>release=r);return get(c);};
  const result=f.comm.listenAutomatic();f.comm.cancelTalk();release();
  assert.equal(await result,null);await new Promise(r=>setImmediate(r));assert.equal(f.media.live(),0);assert.equal(f.sent.length,0);
});

test('G286: stale selected microphone falls back once to OS default; refusal never retries', async()=>{
  let calls=0;
  const media=fakeMedia([{kind:'audioinput',deviceId:'default',label:'Windows default'}]);
  const get=media.getUserMedia;
  media.getUserMedia=async c=>{calls++;if(calls===1){const e=Error();e.name='OverconstrainedError';throw e;}return get(c);};
  const {comm}=setup({media});await comm.refresh();await comm.enable('microphone');
  assert.equal(calls,2);assert.equal(comm.state().microphone.state,'ready');assert.equal(media.live(),0);
});

test('G286: default Windows microphone takes precedence over enumeration order',async()=>{
 const {comm}=setup({media:fakeMedia([{kind:'audioinput',deviceId:'other',label:'Other'}, {kind:'audioinput',deviceId:'default',label:'Default'}])});
 await comm.refresh();assert.equal(comm.state().microphone.selected,'default');
});

test('G286: PIXY preferred when available, explicit camera choice is respected',async()=>{
 const media=fakeMedia([{kind:'videoinput',deviceId:'other',label:'Other webcam'},{kind:'videoinput',deviceId:'pixy',label:'EMEET PIXY 4K'}]);
 const {comm}=setup({media});await comm.refresh();assert.equal(comm.state().camera.selected,'pixy');
 comm.select('camera','other');await comm.refresh();assert.equal(comm.state().camera.selected,'other');
});
