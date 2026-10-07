/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : research.test.js
 * Description : Missions de recherche synthétique C-021 vues par le client, projections Core réelles (C-TASK-G060)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run from eidolon-core/: NODE_PATH=<dir containing playwright> node --test "desktop/connected/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const C = require("../src/session.js");
const { WEB_ROOT, chromium, chromiumUnavailable, noPython, cli, startServer, nodeTransport, cleanup } = require("./helpers.js");

// One real state per C-021 scenario, created by the CLI (fixed fixtures, no network).
// The query carries synthetic personal data: it must never reach the client.
const QUERY = "notice pont jean@example.invalid 06 12 34 56 78";
const SECRETS = ["jean@example.invalid", "06 12 34 56 78", "notice pont"];

function researchState(scenario) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "eidolon-g060-"));
  const state = path.join(dir, "state");
  const pre = ["--research-scenario", scenario, "research", QUERY, "--required-pages", "2"];
  const mission = cli(state, pre, "research-sim");
  const token = crypto.randomBytes(32).toString("base64url");
  const tokenFile = path.join(dir, "read-token");
  fs.writeFileSync(tokenFile, token + "\n", { mode: 0o600 });
  return { dir, state, token, tokenFile, id: mission.id };
}

const EXPECTED = {
  readable: { status: "SUCCEEDED", outcome: "ACHIEVED", label: "Réussie — pages synthétiques récupérées", note: /complète.*pas une information confirmée/ },
  partial: { status: "BLOCKED", outcome: "PARTIAL", label: "Bloquée — récupération partielle", note: /partielle.*objectif non atteint/ },
  empty: { status: "BLOCKED", outcome: "NOT_ACHIEVED", label: "Bloquée — aucune page vérifiée", note: /Aucune page vérifiée/ }
};

test("G060 real Core projections of research missions: labels, notes, no query or page text", { skip: noPython }, async () => {
  for (const scenario of Object.keys(EXPECTED)) {
    const env = researchState(scenario);
    let server;
    try {
      server = await startServer(env, null);
      const s = C.createSession({ transport: nodeTransport(server.base) });
      assert.equal(await s.connect(env.token), true);
      await s.selectMission(env.id);
      const st = s.state();
      const m = st.list.selection.sync.view.mission;
      const want = EXPECTED[scenario];
      assert.equal(m.objective_kind, "research_retrieval.synthetic", scenario);
      assert.equal(m.status, want.status, scenario);
      assert.equal(m.outcome_status, want.outcome, scenario);
      assert.equal(C.missionLabel(m), want.label, scenario);
      assert.match(C.researchNote(m), want.note, scenario);
      assert.equal(C.objectiveLabel(m.objective_kind), "Recherche synthétique (pages fixes)");
      const all = JSON.stringify(st);
      for (const secret of SECRETS) assert.ok(!all.includes(secret), scenario + ": " + secret + " reached the client");
      assert.ok(!all.includes("synthétique : information"), "page text never projected");
    } finally { await cleanup({ servers: [server], dirs: [env.dir] }); }
  }
});

test("G060 labels never claim truth; unknown objectives and outcomes stay as received", () => {
  const base = { id: "m-" + "1".repeat(32), revision: 1, phase: "DONE", cancel_requested: false, action_view: null,
    progress: { completed: 1, total: 1 } };
  const research = Object.assign({}, base, { objective_kind: "research_retrieval.synthetic" });
  for (const outcome of ["ACHIEVED", "PARTIAL", "NOT_ACHIEVED"]) {
    const note = C.researchNote(Object.assign({}, research, { status: "BLOCKED", outcome_status: outcome }));
    assert.doesNotMatch(note, /vrai|vérité|prouv|garanti|exact/i, outcome);
  }
  // The only mention of confirmation is a negation.
  assert.match(C.researchNote(Object.assign({}, research, { status: "SUCCEEDED", outcome_status: "ACHIEVED" })),
    /Ce n'est pas une information confirmée\.$/);
  assert.equal(C.researchNote(Object.assign({}, research, { status: "SUCCEEDED", outcome_status: "FUTURE_CODE" })),
    "Issue FUTURE_CODE : non interprétée par ce client.");
  const other = Object.assign({}, base, { objective_kind: "future.kind/2", status: "SUCCEEDED", outcome_status: "ACHIEVED" });
  assert.equal(C.objectiveLabel("future.kind/2"), "future.kind/2");
  assert.equal(C.objectiveLabel(null), "hors catalogue");
  assert.equal(C.objectiveLabel("__proto__"), "__proto__");
  assert.equal(C.researchNote(other), null);
  assert.equal(C.missionLabel(other), "Réussie — résultat daté", "non-research labels unchanged");
  assert.equal(C.missionLabel(Object.assign({}, research, { status: "REVIEW_REQUIRED", outcome_status: "NOT_ACHIEVED" })),
    "Revue requise — effet à vérifier", "review keeps priority");
  assert.equal(C.missionLabel(Object.assign({}, research, { status: "BLOCKED", outcome_status: "CLARIFICATION" })),
    "Bloquée — précision demandée");
});

test("G060 Chromium on the real server: research note shown, no command, no query", { skip: noPython || chromiumUnavailable }, async () => {
  const env = researchState("partial");
  let server, browser;
  try {
    server = await startServer(env, WEB_ROOT);
    browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(server.base + "/");
    await page.fill("#token", env.token);
    await page.click("#connect");
    await page.waitForSelector(".mission-button");
    await page.click(".mission-button");
    await page.waitForSelector(".research-note");
    const text = await page.textContent("body");
    assert.match(text, /Bloquée — récupération partielle/);
    assert.match(text, /Recherche synthétique \(pages fixes\)/);
    assert.match(text, /Récupération partielle/);
    for (const secret of SECRETS) assert.ok(!text.includes(secret), secret);
    const labels = await page.$$eval("button", (b) => b.map((x) => x.textContent));
    assert.deepEqual(labels.filter((x) => /rechercher|relancer|lancer|approuv|annuler/i.test(x)), []);
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [env.dir] }); }
});
