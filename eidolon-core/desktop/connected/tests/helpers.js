/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : helpers.js
 * Description : Outils partagés des bancs réels : CLI Core, jeu bêta, serveur loopback, nettoyage (G031, G036, G038)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Not a test file. Every helper creates its own temporary folder or process and the
// caller cleans exactly those, also on failure (see cleanup()). Nothing else is touched.
"use strict";
const { spawn, spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CORE = path.resolve(__dirname, "..", "..", "..");
// CONNECTED_WEB_ROOT lets a bench serve an older copy of the client (before/after comparisons).
const WEB_ROOT = process.env.CONNECTED_WEB_ROOT ? path.resolve(process.env.CONNECTED_WEB_ROOT) : path.resolve(__dirname, "..");
const PYTHON = process.env.PYTHON || "python3";
const CAPTURES = process.env.CAPTURES || null;
const ENV = Object.assign({}, process.env, { PYTHONPATH: path.join(CORE, "src"), PYTHONDONTWRITEBYTECODE: "1" });
let chromium = null;
try { ({ chromium } = require("playwright")); } catch (err) { chromium = null; }
const chromiumUnavailable = !chromium ? "playwright unavailable"
  : !fs.existsSync(chromium.executablePath()) ? "Chromium executable unavailable" : false;
const hasPython = spawnSync(PYTHON, ["-c", "import sys; assert sys.version_info >= (3, 11)"]).status === 0;
const noPython = !hasPython && "python3 >= 3.11 unavailable";

function cli(state, args, profile) {
  const pre = ["-m", "eidolon_core", "--state", state].concat(profile ? ["--profile", profile] : []);
  const r = spawnSync(PYTHON, pre.concat(args), { cwd: CORE, env: ENV, encoding: "utf8" });
  // The exit code reflects the mission (2 waiting, 4 cancelled...): the JSON answer is what counts.
  try { return JSON.parse(r.stdout); } catch (err) { throw new Error("cli " + args[0] + " failed (" + r.status + "): " + r.stderr); }
}

// Four real missions: SUCCEEDED (demo), NEW, BLOCKED awaiting a decision, NEW then cancelled later.
function makeState() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "eidolon-g031-"));
  const state = path.join(dir, "state");
  cli(state, ["demo"]);
  const fresh = cli(state, ["create", "compter les mots du texte rappelé"]).id;
  cli(state, ["restart", "nas"], "action-sim");
  const toCancel = cli(state, ["create", "autre texte synthétique"]).id;
  const token = crypto.randomBytes(32).toString("base64url");
  const tokenFile = path.join(dir, "read-token");
  fs.writeFileSync(tokenFile, token + "\n", { mode: 0o600 });
  return { dir, state, token, tokenFile, fresh, toCancel };
}

// Codex's C-009g beta fixture: six scenarios and three receipt queries (docs/BETA-FIXTURE.md).
function makeFixture() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "eidolon-g036-"));
  const out = path.join(dir, "demo");
  const r = spawnSync(PYTHON, ["-m", "eidolon_core.beta_fixture", "--output", out], { cwd: CORE, env: ENV, encoding: "utf8" });
  if (r.status !== 0) { fs.rmSync(dir, { recursive: true, force: true }); throw new Error("beta_fixture failed: " + r.stdout + r.stderr); }
  const manifest = JSON.parse(fs.readFileSync(path.join(out, "manifest.json"), "utf8"));
  const tokenFile = path.join(out, "read-token");
  const token = fs.readFileSync(tokenFile, "utf8").trim();
  const role = (name) => manifest.scenarios.find((s) => s.role === name).mission_id;
  return { dir, state: path.join(out, "state"), token, tokenFile, manifest, role };
}

// n extra NEW missions in ONE Python process (the CLI would start n processes). Same Runtime.create
// as `eidolon_core create`; requests are synthetic and numbered.
function bulkCreate(state, n) {
  const code = "import sys\nfrom eidolon_core.store import Store\nfrom eidolon_core.runtime import Runtime\n"
    + "r = Runtime(Store(sys.argv[1]))\nfor i in range(int(sys.argv[2])): r.create('mission synthétique de banc %04d' % i)\n";
  const r = spawnSync(PYTHON, ["-c", code, state, String(n)], { cwd: CORE, env: ENV, encoding: "utf8" });
  if (r.status !== 0) throw new Error("bulkCreate failed: " + r.stderr);
}

// Options inject only a synthetic child/short deadline for the lifecycle tests.
async function startServer(env, webRoot, { spawnServer = spawn, timeoutMs = 10000 } = {}) {
  const args = ["-m", "eidolon_core.http_api", "--state", env.state, "--token-file", env.tokenFile, "--port", "0"];
  if (webRoot) args.push("--web-root", webRoot);
  const child = spawnServer(PYTHON, args, { cwd: CORE, env: ENV, stdio: ["ignore", "pipe", "pipe"] });
  const server = { child };
  try {
    return await new Promise((resolve, reject) => {
      let out = "";
      const cleanupStartup = () => {
        clearTimeout(timer);
        child.removeListener("error", failed);
        child.removeListener("exit", exited);
        child.stdout.removeListener("data", data);
      };
      const failed = () => { cleanupStartup(); reject(new Error("server could not spawn")); };
      const exited = (code) => { cleanupStartup(); reject(new Error("server exited " + code)); };
      const data = (d) => {
        out = (out + d).slice(-4096);
        const m = out.match(/http:\/\/127\.0\.0\.1:(\d+)/);
        if (m) {
          cleanupStartup();
          resolve({ child, port: Number(m[1]), base: "http://127.0.0.1:" + m[1] });
        }
      };
      const timer = setTimeout(() => { cleanupStartup(); reject(new Error("server startup deadline")); }, timeoutMs);
      child.on("error", failed);
      child.once("exit", exited);
      child.stdout.on("data", data);
      // Drain both pipes, including after startup: diagnostics never become a blocked child.
      child.stdout.resume();
      child.stderr.resume();
    });
  } catch (err) {
    await stop(server);
    throw err;
  }
}

function stop(server, { graceMs = 1000, killMs = 3000 } = {}) {
  return new Promise((resolve, reject) => {
    if (!server || !server.child.pid || server.child.exitCode !== null || server.child.signalCode !== null) return resolve();
    const child = server.child;
    const cleanupStop = () => {
      clearTimeout(force); clearTimeout(deadline);
      child.removeListener("exit", exited);
    };
    const exited = () => { cleanupStop(); resolve(); };
    child.once("exit", exited);
    const force = setTimeout(() => child.kill("SIGKILL"), graceMs);
    const deadline = setTimeout(() => { cleanupStop(); reject(new Error("owned server did not exit")); }, graceMs + killMs);
    child.kill("SIGTERM");  // SIGINT can be inherited as ignored in noninteractive shells.
  });
}

// Same contract as main.js, with an absolute base because Node has no page origin.
function nodeTransport(base) {
  return async (method, p, body, token) => {
    const headers = { Authorization: "Bearer " + token };
    const init = { method, headers, redirect: "error" };
    if (body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    const res = await fetch(base + p, init);
    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch (err) { json = null; }
    return { status: res.status, json };
  };
}

// Closes, in order and even if one step throws: browser, servers, then the folders created.
async function cleanup({ browser, servers = [], dirs = [] }) {
  const errors = [];
  if (browser) { try { await browser.close(); } catch (err) { errors.push(err); } }
  for (const s of servers) { try { await stop(s); } catch (err) { errors.push(err); } }
  for (const d of dirs) { try { fs.rmSync(d, { recursive: true, force: true }); } catch (err) { errors.push(err); } }
  if (errors.length) throw errors[0];
}

module.exports = { CORE, WEB_ROOT, PYTHON, CAPTURES, ENV, chromium, chromiumUnavailable, hasPython, noPython,
  cli, makeState, makeFixture, bulkCreate, startServer, stop, nodeTransport, cleanup };
