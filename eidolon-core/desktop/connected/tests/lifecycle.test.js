/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : lifecycle.test.js
 * Description : Fin bornée des processus appartenant au banc local
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { startServer, stop } = require("./helpers.js");
const env = { state: "unused", tokenFile: "unused" };

test("missing executable rejects without an unhandled spawn error", async () => {
  await assert.rejects(startServer(env, null, {
    spawnServer: () => spawn("/nonexistent/eidolon-test-executable", [], { stdio: ["ignore", "pipe", "pipe"] })
  }), /could not spawn/);
});

test("startup deadline waits for its silent owned child to exit", async () => {
  let child;
  await assert.rejects(startServer(env, null, { timeoutMs: 100,
    spawnServer: () => (child = spawn(process.execPath, ["-e", "setInterval(()=>{},1000)"], { stdio: ["ignore", "pipe", "pipe"] }))
  }), /startup deadline/);
  assert.ok(child.exitCode !== null || child.signalCode !== null);
});

test("stderr is drained and a child ignoring TERM is killed, then stop is idempotent", async () => {
  const server = await startServer(env, null, {
    spawnServer: () => spawn(process.execPath, ["-e",
      "process.on('SIGTERM',()=>{}); process.stderr.write('x'.repeat(300000)); console.log('http://127.0.0.1:12345'); setInterval(()=>{},1000)"
    ], { stdio: ["ignore", "pipe", "pipe"] })
  });
  try {
    await stop(server, { graceMs: 50 });
    assert.equal(server.child.signalCode, "SIGKILL");
    await stop(server);
  } finally { await stop(server); }
});
