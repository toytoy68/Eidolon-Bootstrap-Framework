/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : transport-g278.test.js
 * Description : Real browser transport deadlines and cleanup with controlled clocks
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm"), path = require("node:path");
function harness() {
  const timers = [], cleared = [], requests = [];
  const context = { module: { exports: {} }, AbortController,
    setTimeout: (fn, ms) => { timers.push({fn, ms}); return timers.length; },
    clearTimeout: (id) => cleared.push(id),
    fetch: (url, init) => new Promise((resolve, reject) => {
      requests.push({url, init, resolve});
      init.signal.addEventListener("abort", () => reject(new Error("aborted")));
    }) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"../src/main.js"),"utf8"),context);
  return {transport:context.module.exports.transport,timers,cleared,requests};
}
test("G278: model turn has a bounded 150s deadline while reads keep 10s", async () => {
  const h=harness();
  const turn=h.transport("POST","/v1/conversations/turn",{text:"bonjour"},"private");
  assert.equal(h.timers[0].ms,150000);
  assert.equal(h.requests[0].init.signal.aborted,false);
  h.requests[0].resolve({status:200,text:async()=>'{"reply":{}}'});
  assert.equal((await turn).status,200);
  assert.deepEqual(h.cleared,[1]);
  const read=h.transport("POST","/v1/conversations/page",{},"private");
  assert.equal(h.timers[1].ms,10000);
  h.timers[1].fn();
  await assert.rejects(read,/aborted/);
  assert.deepEqual(h.cleared,[1,2]);
});
test("G278: turn timeout aborts once without a silent resend", async () => {
  const h=harness(), pending=h.transport("POST","/v1/conversations/turn",{},"private");
  h.timers[0].fn();
  await assert.rejects(pending,/aborted/);
  assert.equal(h.requests.length,1);
  assert.deepEqual(h.cleared,[1]);
});
