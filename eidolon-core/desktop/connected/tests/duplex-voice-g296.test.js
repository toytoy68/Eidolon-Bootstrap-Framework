/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : duplex-voice-g296.test.js
 * Description : Interruption vocale G296 : écho, vraie parole, bruit court, tour tardif
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const duplex = require("../src/duplex-voice.js");

const FRAME = 20; // ms
function rig(options) {
  const calls = [];
  const c = duplex.create({
    stopPlayback: (g) => calls.push(["stop", g]),
    beginUtterance: (u) => calls.push(["utterance", u])
  }, options);
  let at = 0;
  function feed(ms, rms, vad) {
    let result = null;
    for (let t = 0; t < ms; t += FRAME) {
      const r = c.frame({ at, ms: FRAME, rms, vad });
      at += FRAME;
      if (r && !result) result = r;
      if (r) break;
    }
    return result;
  }
  return { c, calls, feed, now: () => at, start: () => c.speaking(at) };
}

test("residual echo of Eidolon's own voice never interrupts it", () => {
  const r = rig();
  r.start();
  // 10 s of answer: echo after AEC between 0.02 and 0.06 RMS, VAD says "speech" all along.
  for (let i = 0; i < 500; i++) assert.equal(r.feed(FRAME, 0.02 + 0.04 * Math.abs(Math.sin(i / 7)), 0.9), null);
  assert.equal(r.c.state(), "speaking");
  assert.deepEqual(r.calls, []);
  assert.ok(r.c.stats().rejectedEcho > 0);
});

test("the user's voice over the answer stops playback at once, with pre-roll and bounded latency", () => {
  const r = rig();
  const token = r.start();
  r.feed(1000, 0.04, 0.9);                     // echo
  const onset = r.now();
  const result = r.feed(1000, 0.2, 0.95);      // user speaks louder than the echo peak
  assert.equal(result.event, "barge-in");
  assert.equal(result.generation, token);
  assert.ok(result.latencyMs <= duplex.DEFAULTS.bargeInMs + FRAME, "latency " + result.latencyMs);
  assert.deepEqual(r.calls[0], ["stop", token]);
  const utterance = r.calls[1][1];
  assert.equal(utterance.onsetAt, onset);
  assert.ok(utterance.preroll.some((f) => f.at === onset), "first syllable kept");
  assert.equal(r.c.state(), "listening");
});

test("a short cough or a door is not an interruption", () => {
  const r = rig();
  r.start();
  r.feed(1000, 0.03, 0.2);
  assert.equal(r.feed(100, 0.4, 0.9), null);  // 100 ms burst
  r.feed(500, 0.03, 0.2);
  assert.equal(r.feed(160, 0.4, 0.9), null);  // 160 ms burst
  assert.equal(r.c.state(), "speaking");
  assert.deepEqual(r.calls, []);
});

test("no interruption in the grace and echo-learning window, even for loud speech", () => {
  const r = rig();
  r.start();
  assert.equal(r.feed(duplex.DEFAULTS.graceMs + duplex.DEFAULTS.echoLearnMs, 0.5, 1), null);
  assert.deepEqual(r.calls, []);
});

test("energy-only frames (no VAD) still work and use the same echo rule", () => {
  const r = rig();
  r.start();
  r.feed(1000, 0.05);
  assert.equal(r.feed(1000, 0.06), null, "6 % over the echo peak is not enough");
  assert.equal(r.feed(1000, 0.3).event, "barge-in");
});

test("late callbacks of a stopped or replaced turn are ignored", () => {
  const r = rig();
  const first = r.start();
  r.feed(1000, 0.04, 0.9);
  r.feed(1000, 0.3, 0.9);
  const second = r.start();                    // a new answer begins
  assert.equal(r.c.outcome(first, "trop tard"), false);
  assert.equal(r.c.finished(first), false);
  assert.equal(r.c.state(), "speaking");
  assert.equal(r.c.finished(second), true);
  r.c.stop();
  assert.equal(r.c.frame({ at: r.now(), ms: FRAME, rms: 1, vad: 1 }), null);
});

test("an empty transcript after an interruption is counted as a false barge-in", () => {
  const r = rig();
  const token = r.start();
  r.feed(1000, 0.04, 0.9);
  r.feed(1000, 0.3, 0.9);
  assert.equal(r.c.outcome(token, "  "), true);
  assert.equal(r.c.stats().falseBargeIns, 1);
  assert.equal(r.c.stats().bargeIns, 1);
  assert.ok(r.c.stats().latencyMedianMs > 0);
});

test("invalid frames and missing callbacks are refused", () => {
  assert.throws(() => duplex.create({}), TypeError);
  const r = rig();
  r.start();
  for (const bad of [null, {}, { at: 0, ms: 0, rms: 0.1 }, { at: 0, ms: 20, rms: NaN }, { at: 0, ms: 20, rms: -1 }])
    assert.throws(() => r.c.frame(bad), TypeError);
});

test("not bundled in app.js: the existing client is unchanged by this lot", () => {
  const build = require("node:fs").readFileSync(require("node:path").join(__dirname, "..", "build.js"), "utf8");
  assert.equal(build.includes("duplex-voice"), false);
});

test("the outcome of an earlier interruption cannot close the current one", () => {
  const r = rig();
  const first = r.start();
  r.feed(1000, 0.04, 0.9); r.feed(1000, 0.3, 0.9);          // barge-in on answer 1
  const second = r.start();
  r.feed(1000, 0.04, 0.9); r.feed(1000, 0.3, 0.9);          // barge-in on answer 2
  assert.equal(r.c.state(), "listening");
  assert.equal(r.c.outcome(first, ""), false);              // late STT result of answer 1
  assert.equal(r.c.stats().falseBargeIns, 0);
  assert.equal(r.c.state(), "listening");
  assert.equal(r.c.outcome(second, "attends"), true);
});
