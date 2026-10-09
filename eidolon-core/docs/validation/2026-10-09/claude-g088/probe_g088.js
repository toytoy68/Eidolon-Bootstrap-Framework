/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : probe_g088.js
 * Description : Accueil conversationnel dans Chromium sur serveur réel patché : parcours, clavier, 1280/360, rechargement (C-TASK-G088)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:
//   NODE_PATH=<playwright> node docs/validation/2026-10-09/claude-g088/probe_g088.js <patched src> [captures dir]
// <patched src> = eidolon-core/src + http_api-conversations.patch. C-009g fixture, simulated dialogue model,
// loopback only, temporary folders cleaned. The mission is run by the synthetic runtime, as an operator would.
"use strict";
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { WEB_ROOT, PYTHON, chromium, makeFixture, startServer, cleanup } = require("../../../../desktop/connected/tests/helpers.js");

const PATCHED = path.resolve(process.argv[2]);
const CAPTURES = process.argv[3] ? path.resolve(process.argv[3]) : null;
const ENV = Object.assign({}, process.env, { PYTHONPATH: PATCHED, PYTHONDONTWRITEBYTECODE: "1" });
const FORBIDDEN = /approuv|lancer|annuler|exécut/i;

function python(args) {
  const r = spawnSync(PYTHON, args, { env: ENV, encoding: "utf8" });
  if (r.status !== 0) throw new Error(args.join(" ") + ": " + r.stdout + r.stderr);
  return r.stdout;
}
const spawnPatched = (cmd, args, opts) => spawn(cmd, args.concat(["--conversations", "simulated"]),
  Object.assign({}, opts, { env: ENV }));

async function audit(page) {
  return page.evaluate((forbidden) => {
    const buttons = [...document.querySelectorAll("button")].filter((b) => !b.hidden && b.offsetParent !== null)
      .map((b) => b.textContent.trim());
    return { overflow_px: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      command_buttons: buttons.filter((t) => new RegExp(forbidden, "i").test(t)),
      conversation_buttons: [...document.querySelectorAll("#conversation button")].filter((b) => !b.hidden && b.offsetParent !== null)
        .map((b) => b.textContent.trim()),
      key_in_dom: document.documentElement.outerHTML.includes("ecc_") };
  }, FORBIDDEN.source);
}

async function scenario(browser, server, fx, key, width, height) {
  const out = { viewport: `${width}x${height}`, steps: [] };
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const step = async (name, extra) => out.steps.push(Object.assign({ step: name }, await audit(page), extra || {}));
  await page.goto(server.base + "/");
  await step("lecture seule, avant toute clé", { status: await page.textContent("#conv-status") });
  // Read connection (existing form), then the conversation key — by keyboard.
  await page.fill("#token", fx.token); await page.press("#token", "Enter");
  await page.waitForSelector(".mission-button");
  await page.focus("#conv-key"); await page.keyboard.type(fx.convKey); await page.keyboard.press("Enter");
  await page.waitForSelector("#conv-body:not([hidden])");
  const focus = await page.evaluate(() => document.activeElement.id);
  await step("conversation ouverte", { focus_after_open: focus, status: await page.textContent("#conv-status") });
  async function say(text) {
    const before = await page.locator("#conv-log li").count();
    await page.fill("#conv-text", text);
    await page.focus("#conv-send"); await page.keyboard.press("Enter");
    await page.waitForFunction((n) => document.querySelectorAll("#conv-log li .conv-kind").length > n, before);
    const last = page.locator("#conv-log li").last();
    return { kind: await last.locator(".conv-kind").textContent(), state: await last.locator(".conv-state").textContent() };
  }
  await step("réponse", await say("Bonjour !"));
  await step("question en retour", await say("Peux-tu vérifier l'état du service ?"));
  await step("proposition", Object.assign(await say("Diagnostique le nas."),
    { proposal: await page.textContent("#conv-proposal-request"), meta: await page.textContent("#conv-proposal-meta") }));
  if (CAPTURES) await page.locator("#conversation").screenshot({ path: path.join(CAPTURES, `proposition-${width}.png`) });
  await page.fill("#conv-reason", "Diagnostic demandé dans la conversation.");
  await page.click("#conv-submit");
  await page.waitForFunction(() => /enregistrée/.test(document.getElementById("conv-submission-state").textContent));
  await step("validation enregistrée", { submission: await page.textContent("#conv-submission-state"),
    mission: await page.textContent("#conv-mission-state") });
  // The operator side runs the created mission with the synthetic runtime (not the page).
  const missionId = await page.getAttribute("#conv-follow", "data-mission-id");
  python(["-c", "import sys; from eidolon_core.diagnostics import synthetic_runtime; from eidolon_core.store import Store;"
    + " print(synthetic_runtime(Store(sys.argv[1])).run(sys.argv[2])['status'])", fx.state, missionId]);
  await page.click("#conv-follow");
  await page.waitForFunction(() => /Résultat/.test(document.getElementById("conv-mission-state").textContent), null, { timeout: 15000 });
  await step("mission suivie", { mission: await page.textContent("#conv-mission-state"),
    details: (await page.textContent("#details-body")).includes("SUCCEEDED") });
  await page.evaluate(() => window.scrollTo(0, 0));
  if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, `parcours-${width}.png`), fullPage: true });
  await page.reload();
  await step("après rechargement", { status: await page.textContent("#conv-status"),
    body_hidden: await page.locator("#conv-body").isHidden() });
  out.errors = errors;
  await context.close();
  return out;
}

(async () => {
  const fx = makeFixture();
  let server, browser;
  try {
    fx.convKey = JSON.parse(python(["-m", "eidolon_core.conversation_api", "--state", fx.state, "pair",
      "--client-id", "pc-recette", "--actor", "toytoy"])).token;
    server = await startServer(fx, WEB_ROOT, { spawnServer: spawnPatched });
    browser = await chromium.launch();
    const results = [];
    for (const [w, h] of [[1280, 720], [360, 740]]) results.push(await scenario(browser, server, fx, fx.convKey, w, h));
    console.log(JSON.stringify(results, null, 1));
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
})().catch((err) => { console.error(err); process.exit(1); });
