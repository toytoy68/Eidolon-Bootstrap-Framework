/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : monitoring.test.js
 * Description : Tableau de bord machines : rien au chargement, gris jamais sécurisé, périmé, refus, suivi borné (G158)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const M = require("../src/monitoring.js");

function darme(changes) {
  return Object.assign({ badge: "grey", secure_claim: false, visibility: "partial",
    sources: { "eidolon-core-api.service": true, "security-telemetry": false },
    scope: "local_service_availability_and_journal_disk", security_telemetry_installed: false,
    unacknowledged_alerts: 0, intervention: false, ingestion_paused: false,
    generated_at: "2026-10-12T10:00:00+00:00", age_seconds: 4, health_ttl_seconds: 60 }, changes || {});
}

function status(machines) {
  return { protocol: "eidolon-monitor/1", generated_at: "2026-10-12T10:00:04+00:00", poll_seconds: 10,
    machines: machines || [{ id: "core", label: "Core", state: "ok", darme: darme(), machine: null }],
    not_covered: ["VM101 GPU"], gpu_metrics: null, authorizes_execution: false };
}

function harness(replies) {
  const calls = [], timers = new Map(), states = [];
  let next = 1, key = "paired-key";
  const pending = [];
  const deps = {
    key: () => key,
    onChange: (s) => states.push(s),
    timers: { set: (fn, ms) => { const id = next++; timers.set(id, { fn, ms }); return id; }, clear: (id) => timers.delete(id) },
    transport: (method, path, body, token) => {
      calls.push({ method, path, body, token });
      const reply = replies.length ? replies.shift() : { status: 200, json: status() };
      if (reply === "hang") return new Promise((resolve) => pending.push(resolve));
      if (reply instanceof Error) return Promise.reject(reply);
      return Promise.resolve(reply);
    }
  };
  const mon = M.createMonitoring(deps);
  return { mon, calls, timers, states, pending, setKey: (k) => { key = k; },
    fire: async () => { const [id, t] = timers.entries().next().value; timers.delete(id); await t.fn(); } };
}

test("nothing is read when the conversation opens; one read on demand, never more than one timer", async () => {
  const h = harness([]);
  assert.equal(h.mon.ready(), true);
  assert.equal(h.calls.length, 0);
  assert.equal(h.mon.state().phase, "idle");
  await h.mon.refresh();
  assert.deepEqual(h.calls.map((c) => [c.method, c.path, c.body, c.token]), [["GET", "/v1/monitor/status", undefined, "paired-key"]]);
  assert.equal(h.mon.state().phase, "ok");
  assert.equal(h.timers.size, 0);                 // a single read does not start polling
});

test("grey is never secure; gold says its scope; red counts alerts; nothing claims more than the server", () => {
  const grey = M.describe({ id: "core", label: "Core", state: "ok", darme: darme(), machine: null });
  assert.equal(grey.badge, "Gris");
  assert.match(grey.text, /PAS un état sécurisé/);
  assert.match(grey.text, /Aucun collecteur de sécurité/);
  assert.match(grey.scope, /systemd actif/);
  assert.match(grey.freshness, /il y a 4 s/);
  assert.match(grey.metricsNote, /pas publiées/);
  assert.deepEqual(grey.services.map((x) => x.text), ["répond", "non installé"]);
  const gold = M.describe({ id: "c", label: "C", state: "ok", darme: darme({ badge: "gold", visibility: "complete", security_telemetry_installed: true }), machine: null });
  assert.match(gold.text, /pas une garantie de sécurité/);
  const red = M.describe({ id: "c", label: "C", state: "ok", darme: darme({ badge: "red", unacknowledged_alerts: 2 }), machine: null });
  assert.match(red.text, /^2 alerte\(s\)/);
  for (const v of [grey, gold, red]) assert.doesNotMatch(v.badge, /sécuris|protég/i);   // no badge word claims safety
});

test("stale status loses its colour; unavailable and invalid machines say so", () => {
  const stale = M.describe({ id: "c", label: "C", state: "stale", darme: darme({ badge: "gold", age_seconds: 300 }), machine: null });
  assert.equal(stale.cls, "stale");
  assert.equal(stale.badge, "Statut périmé");
  assert.match(stale.freshness, /il y a 5 min/);
  const down = M.describe({ id: "m", label: "Memory", state: "unavailable", error: "UNAVAILABLE", darme: null, machine: null });
  assert.deepEqual([down.cls, down.badge, down.text], ["unknown", "Indisponible", "service DARME absent ou arrêté"]);
  const bad = M.describe({ id: "m", label: "M", state: "invalid", error: "CLOCK_SKEW", darme: null, machine: null });
  assert.match(bad.text, /horloge/);
});

test("metrics follow eidolon-machine/1: null is 'indisponible', never zero; GPU never measured", () => {
  const machine = { sampled_at: "2026-10-12T10:00:00+00:00", age_seconds: 3, stale: false, cpu_count: 8, cpu_percent: 12.34,
    load_1_5_15: [0.456, 0.3, 0.2], memory: { total_bytes: 8 * 1024 ** 3, available_bytes: 5 * 1024 ** 3, used_bytes: 3 * 1024 ** 3 },
    swap: { total_bytes: 0, free_bytes: 0, used_bytes: 0 }, disk: { scope: "journal_filesystem", total_bytes: 4 * 1024 ** 3, free_bytes: 1024 ** 3, used_bytes: 3 * 1024 ** 3 },
    gpu: null, errors: [] };
  const v = M.describe({ id: "c", label: "C", state: "ok", darme: darme(), machine });
  assert.deepEqual(v.metrics.map((x) => x.name + " = " + x.text), [
    "CPU = 12.3 % de 8 vCPU", "Charge 1/5/15 min = 0.46 / 0.3 / 0.2", "Mémoire = 3.0 Gio utilisés sur 8.0 Gio",
    "Swap = aucun", "Disque du journal = 1.0 Gio libres sur 4.0 Gio", "GPU = non sondé sur cette machine"]);
  assert.equal(v.measured, "Mesures il y a 3 s.");
  assert.equal(v.metricsNote, null);
  const first = M.describe({ id: "c", label: "C", state: "ok", darme: darme(),
    machine: Object.assign({}, machine, { cpu_percent: null, memory: null, stale: true, age_seconds: 120, errors: ["memory_unavailable"] }) });
  assert.match(first.metrics[0].text, /indisponible \(premier sondage\)/);
  assert.equal(first.metrics[2].text, "indisponible");
  assert.match(first.measured, /PÉRIMÉES, il y a 2 min/);
  assert.match(first.metricsNote, /memory_unavailable/);
  const refused = M.describe({ id: "c", label: "C", state: "ok", darme: darme({ machine_error: "MACHINE_INVALID" }), machine: null });
  assert.deepEqual([refused.metrics.length, /refusées/.test(refused.metricsNote)], [0, true]);
});

test("polling: bounded interval, one request in flight, paused when hidden", async () => {
  const h = harness(["hang"]);
  h.mon.ready();
  h.mon.pause(true);                               // the user ticks automatic refresh
  assert.equal(h.calls.length, 1);
  await h.mon.refresh();                           // a click while a read is pending sends nothing
  assert.equal(h.calls.length, 1);
  h.pending[0]({ status: 200, json: status() });
  await new Promise((r) => setImmediate(r));
  assert.equal(h.timers.size, 1);
  assert.equal([...h.timers.values()][0].ms, M.POLL_MS);
  h.mon.visibility(true);
  assert.equal(h.timers.size, 0);
  h.mon.visibility(false);
  await new Promise((r) => setImmediate(r));
  assert.equal(h.calls.length, 2);
  assert.equal(h.timers.size, 1);
  h.mon.pause(false);
  assert.equal(h.timers.size, 0);
});

test("three failures in a row stop polling; the last data stays, marked", async () => {
  const h = harness([{ status: 200, json: status() }, new Error("net"), { status: 503, json: { protocol: "eidolon-monitor/1", error: "MONITOR_UNAVAILABLE" } }, new Error("net")]);
  h.mon.ready(); h.mon.pause(true);
  await new Promise((r) => setImmediate(r));
  for (let i = 0; i < 3; i++) await h.fire();
  const s = h.mon.state();
  assert.equal(s.polling, false);
  assert.equal(s.error, "MONITOR_UNREACHABLE_STOPPED");
  assert.equal(s.phase, "ok");
  assert.ok(s.data);
  assert.equal(h.timers.size, 0);
  assert.equal(h.calls.length, 4);
});

test("refusal (revoked key) and a Core without --monitor-port stop at once", async () => {
  const h = harness([{ status: 401, json: { protocol: "eidolon-monitor/1", error: "UNAUTHORIZED" } }]);
  h.mon.ready(); h.mon.pause(true);
  await new Promise((r) => setImmediate(r));
  assert.deepEqual([h.mon.state().phase, h.mon.state().polling, h.mon.state().data, h.timers.size], ["error", false, null, 0]);
  const plain = harness([{ status: 401, json: { error: "UNAUTHORIZED" } }]);   // the read API answered instead
  plain.mon.ready(); plain.mon.pause(true);
  await new Promise((r) => setImmediate(r));
  assert.deepEqual([plain.mon.state().phase, plain.mon.state().polling, plain.timers.size], ["not_enabled", false, 0]);
});

test("closing the conversation stops and forgets; a late answer is ignored", async () => {
  const h = harness(["hang"]);
  h.mon.ready(); h.mon.pause(true);
  h.mon.stop();
  h.pending[0]({ status: 200, json: status() });
  await new Promise((r) => setImmediate(r));
  assert.deepEqual([h.mon.state().phase, h.mon.state().data, h.timers.size], ["off", null, 0]);
  h.setKey(null);
  assert.equal(h.mon.ready(), false);
  assert.equal(await h.mon.refresh(), false);
  assert.equal(h.calls.length, 1);
});

test("a key that disappears between two reads stops the polling", async () => {
  const h = harness([]);
  h.mon.ready(); h.mon.pause(true);
  await new Promise((r) => setImmediate(r));
  h.setKey(null);
  await h.fire();
  assert.deepEqual([h.mon.state().phase, h.timers.size, h.calls.length], ["off", 0, 1]);
});
