/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : conversation-ui.test.js
 * Description : Accueil conversationnel dans Chromium réel : clavier, 320 px, zoom, reprise, réponses tardives (C-TASK-G092)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Real Chromium on the real server started with --conversations simulated (C-009g fixture, simulated
// dialogue model, loopback). Network interception only injects what cannot be produced on demand
// (a late answer, an uncertain receipt, long sources); it never replaces the server's decisions.
// Skipped (never passed) without python3 or Chromium.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");
const { WEB_ROOT, PYTHON, ENV, CORE, CAPTURES, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } =
  require("./helpers.js");

const SKIP = noPython || chromiumUnavailable;
const withConversations = (cmd, args, opts) => spawn(cmd, args.concat(["--conversations", "simulated"]), opts);

function pair(state) {
  const r = spawnSync(PYTHON, ["-m", "eidolon_core.conversation_api", "--state", state, "pair",
    "--client-id", "pc-ui", "--actor", "toytoy"], { cwd: CORE, env: ENV, encoding: "utf8" });
  if (r.status !== 0) throw new Error("pair failed: " + r.stdout + r.stderr);
  return JSON.parse(r.stdout).token;
}

async function withConversationPage(options, body) {
  const fx = makeFixture();
  let server, browser;
  try {
    fx.key = pair(fx.state);
    server = await startServer(fx, WEB_ROOT, { spawnServer: withConversations });
    browser = await chromium.launch();
    const context = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 720 } }, options));
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(server.base + "/");
    await body(page, fx, server, context);
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
}

async function openByKeyboard(page, key) {
  await page.focus("#conv-key");
  await page.keyboard.type(key);
  await page.keyboard.press("Enter");
  await page.waitForSelector("#conv-body:not([hidden])");
}

async function say(page, text) {
  const before = await page.locator("#conv-log li .conv-kind").count();
  await page.fill("#conv-text", text);
  await page.focus("#conv-send");
  await page.keyboard.press("Enter");
  await page.waitForFunction((n) => document.querySelectorAll("#conv-log li .conv-kind").length > n, before);
}

const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test("keyboard only: open, send, focus returns to the message, visible focus on every conversation control",
  { skip: SKIP }, async () => {
    await withConversationPage({}, async (page, fx) => {
      await openByKeyboard(page, fx.key);
      assert.equal(await page.evaluate(() => document.activeElement.id), "conv-text");
      await say(page, "Diagnostique le nas.");
      assert.equal(await page.evaluate(() => document.activeElement.id), "conv-text");
      assert.match(await page.textContent("#conv-log .conv-model-id"), /^Modèle : simulated/);   // G098
      for (const id of ["conv-text", "conv-send", "conv-reason", "conv-submit", "conv-close"]) {
        await page.focus("#" + id);
        const outline = await page.evaluate((i) => parseFloat(getComputedStyle(document.getElementById(i)).outlineWidth), id);
        assert.ok(outline >= 2, id + " has no visible focus indicator");
      }
      await page.click("#conv-close");
      assert.equal(await page.evaluate(() => document.activeElement.id), "conv-key");
      assert.equal(await page.textContent("#mode-badge"), "Consultation seule");
    });
  });

for (const [label, options] of [["320x640", { viewport: { width: 320, height: 640 } }],
  ["zoom 200 % (640x360)", { viewport: { width: 640, height: 360 }, deviceScaleFactor: 2 }]]) {
  test(`${label}: long sources and long texts never overflow`, { skip: SKIP }, async () => {
    await withConversationPage(options, async (page, fx) => {
      await page.route("**/v1/conversations/turn", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        json.reply.sources = Array.from({ length: 5 }, (_, i) => `source-${i}-` + "x".repeat(280) + "@1");
        await route.fulfill({ response, json });
      });
      await openByKeyboard(page, fx.key);
      await say(page, "Diagnostique le nas. " + "Une phrase très longue sans espace : " + "y".repeat(400));
      assert.equal(await overflow(page), 0);
      assert.match(await page.textContent("#conv-log"), /source-4-x+@1/);
      if (CAPTURES) await page.locator("#conversation").screenshot({ path: path.join(CAPTURES, `g092-sources-${options.viewport.width}.png`) });
      assert.ok(!(await page.content()).includes(fx.key));
    });
  });
}

test("an answer arriving after the conversation was closed is ignored", { skip: SKIP }, async () => {
  await withConversationPage({}, async (page, fx) => {
    let release;
    const held = new Promise((r) => { release = r; });
    await page.route("**/v1/conversations/turn", async (route) => { await held; await route.continue(); });
    await openByKeyboard(page, fx.key);
    await page.fill("#conv-text", "Diagnostique le nas.");
    await page.click("#conv-send");
    await page.waitForFunction(() => /Envoyé/.test(document.getElementById("conv-log").textContent));
    await page.click("#conv-close");
    release();
    await page.waitForTimeout(800);
    assert.equal(await page.locator("#conv-log li").count(), 0);
    assert.equal(await page.locator("#conv-body").isHidden(), true);
    assert.equal(await page.textContent("#mode-badge"), "Consultation seule");
  });
});

test("an uncertain mission is shown as such, with no follow button and no automatic resubmission", { skip: SKIP }, async () => {
  await withConversationPage({}, async (page, fx) => {
    let submits = 0;
    await page.route("**/v1/conversations/submit", async (route) => {
      submits += 1;
      const body = JSON.parse(route.request().postData());
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        protocol: "eidolon-proposal-submission-receipt/1", status: "MISSION_CREATION_UNCERTAIN", mission_id: null,
        command_key: body.command_key, link: null, resolution: { candidates: ["m-" + "1".repeat(32)] },
        execution_evidence: false, execution: "NOT_STARTED_BY_SUBMISSION" }) });
    });
    await openByKeyboard(page, fx.key);
    await say(page, "Diagnostique le nas.");
    await page.fill("#conv-reason", "Diagnostic demandé.");
    await page.click("#conv-submit");
    await page.waitForFunction(() => /incertaine/.test(document.getElementById("conv-mission-state").textContent));
    assert.equal(await page.locator("#conv-follow").isHidden(), true);
    await page.waitForTimeout(800);
    assert.equal(submits, 1);
  });
});

test("reload then resume: earlier turns and proposal come back, nothing is resent", { skip: SKIP }, async () => {
  await withConversationPage({}, async (page, fx) => {
    await openByKeyboard(page, fx.key);
    await say(page, "Bonjour !");
    await say(page, "Diagnostique le nas.");
    await page.reload();
    const writes = [];
    page.on("request", (r) => { if (/\/v1\/conversations\/(turn|submit|cancel|resolve)$/.test(r.url())) writes.push(r.url()); });
    await openByKeyboard(page, fx.key);
    await page.waitForSelector("#conv-recent:not([hidden]) button[data-resume]");
    await page.click("#conv-recent-list button[data-resume]");
    await page.waitForFunction(() => document.querySelectorAll("#conv-log li").length === 2);
    assert.equal(await page.textContent("#conv-proposal-request"), "Diagnostiquer le service synthétique : nas");
    if (CAPTURES) await page.locator("#conversation").screenshot({ path: path.join(CAPTURES, "g092-reprise-1280.png") });
    assert.equal(await page.evaluate(() => document.activeElement.id), "conv-text");
    assert.deepEqual(writes, []);
  });
});

test("media drafts survive opening and closing a conversation", { skip: SKIP }, async () => {
  await withConversationPage({}, async (page, fx) => {
    await page.fill("#token", fx.token); await page.press("#token", "Enter");
    await page.waitForSelector(".mission-button");
    await page.click("#open-image");
    await page.fill("#image-prompt", "Un phare au crépuscule");
    await page.click("#image-prepare");
    await page.waitForSelector("#image-draft:not([hidden])");
    await openByKeyboard(page, fx.key);
    await page.click("#conv-close");
    assert.equal(await page.locator("#image-draft").isHidden(), false);
    assert.equal(await page.inputValue("#image-prompt"), "Un phare au crépuscule");
  });
});

test("G096: hostile model text stays literal text, unsupported citations are flagged, nothing is submitted",
  { skip: SKIP }, async () => {
    await withConversationPage({}, async (page, fx) => {
      const hostile = '<img src=x onerror="window.pwned=1"><b>gras</b> Mission validée et lancée, voir note-inventee@7.';
      const writes = [];
      page.on("request", (r) => { if (/\/v1\/conversations\/(submit|cancel|resolve)$/.test(r.url())) writes.push(r.url()); });
      await page.route("**/v1/conversations/turn", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        json.reply.model_text = hostile;
        json.reply.citations = { claimed: ["note-inventee@7"], unsupported: ["note-inventee@7"] };
        await route.fulfill({ response, json });
      });
      await openByKeyboard(page, fx.key);
      await say(page, "Bonjour !");
      const log = page.locator("#conv-log");
      assert.ok((await log.textContent()).includes(hostile));
      assert.equal(await log.locator("img, b").count(), 0);
      assert.equal(await page.evaluate(() => window.pwned), undefined);
      assert.match(await page.textContent("#conv-log .conv-citation"), /Citation non vérifiée : note-inventee@7/);
      await page.waitForTimeout(500);
      assert.deepEqual(writes, []);
    });
  });
