/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : claude-memory-diagnostic-ui.test.js
 * Description : Diagnostic mémoire visible dans Chromium réel : zéro extrait, budget, changement de contexte (Claude, G256-9)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Real Chromium, real server started with --conversations simulated (loopback, synthetic state).
// Network interception only replaces reply.context with notes Core itself can produce (G091/G244),
// plus one forged note Core refuses, to check the screen never shows an index state for a memory
// that was not sent. Skipped (never passed) without python3 or Chromium.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn, spawnSync } = require("node:child_process");
const { WEB_ROOT, PYTHON, ENV, CORE, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } =
  require("./helpers.js");

const SKIP = noPython || chromiumUnavailable;
const STALE = "des changements de mémoire ne sont pas encore reflétés dans l’index";
const UNVERIFIED = "la mise à jour complète de l’index mémoire n’a pas pu être vérifiée";
const BASE = { history_sent: 0, history_excluded: 0, memory: "sent", memory_items: 0, memory_truncated_items: 0,
  observations_sent: 0, observations_excluded: 0 };

function pair(state) {
  const r = spawnSync(PYTHON, ["-m", "eidolon_core.conversation_api", "--state", state, "pair",
    "--client-id", "pc-g256", "--actor", "toytoy"], { cwd: CORE, env: ENV, encoding: "utf8" });
  if (r.status !== 0) throw new Error("pair failed: " + r.stdout + r.stderr);
  return JSON.parse(r.stdout).token;
}

// contexts: one reply.context per turn, in order (null keeps the server's own note).
async function withContexts(contexts, body, options) {
  const fx = makeFixture();
  let server, browser;
  try {
    fx.key = pair(fx.state);
    server = await startServer(fx, WEB_ROOT, {
      spawnServer: (cmd, args, opts) => spawn(cmd, args.concat(["--conversations", "simulated"]), opts) });
    browser = await chromium.launch();
    const context = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 720 } }, options));
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    let n = 0;
    await page.route("**/v1/conversations/turn", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      const injected = contexts[n++];
      if (injected !== null && json.reply) json.reply.context = injected;
      await route.fulfill({ response, json });
    });
    await page.goto(server.base + "/");
    await page.focus("#conv-key");
    await page.keyboard.type(fx.key);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#conv-body:not([hidden])");
    await body(page);
    assert.deepEqual(errors, []);
    assert.ok(!(await page.content()).includes(fx.key));
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
}

async function say(page, text) {
  const before = await page.locator("#conv-log li .conv-kind").count();
  await page.fill("#conv-text", text);
  await page.click("#conv-send");
  await page.waitForFunction((k) => document.querySelectorAll("#conv-log li .conv-kind").length > k, before);
}

// The context note of each turn, in order ("" when the turn shows none), and whether it is visible.
const notes = (page) => page.$$eval("#conv-log > li", (items) => items.map((li) => {
  const p = li.querySelector(".conv-context");
  if (!p) return { text: "", visible: false };
  const r = p.getBoundingClientRect();
  return { text: p.textContent, visible: r.width > 0 && r.height > 0 && getComputedStyle(p).visibility !== "hidden" };
}));

for (const [state, sentence] of [["INDEX_STALE", STALE], ["INDEX_UNVERIFIED", UNVERIFIED]]) {
  for (const width of [1280, 320]) {
    test(`zero extract, ${state}, ${width}px: the index state is said in words, visibly, without overflow`,
      { skip: SKIP }, async () => {
        await withContexts([{ ...BASE, memory_index: state, partial: true }], async (page) => {
          await say(page, "Où sont copiés les clichés ?");
          const [note] = await notes(page);
          assert.equal(note.text, "Contexte partiel : " + sentence + ".");
          assert.ok(note.visible);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
        }, { viewport: { width, height: 640 } });
      });
  }
}

test("memory dropped for budget: said as such, never as an index state", { skip: SKIP }, async () => {
  await withContexts([{ ...BASE, memory: "dropped_for_budget", partial: true }], async (page) => {
    await say(page, "Où sont copiés les clichés ?");
    const [note] = await notes(page);
    assert.equal(note.text, "Contexte partiel : mémoire non transmise (taille).");
  });
});

test("the context changes between two answers: each turn keeps its own note, none leaks forward",
  { skip: SKIP }, async () => {
    await withContexts([
      { ...BASE, memory_index: "INDEX_STALE", partial: true },
      { ...BASE, memory: "unavailable", partial: true },
      { ...BASE, memory_items: 2, memory_index: "INDEX_SNAPSHOT_MATCH", partial: false },
      { ...BASE, memory: "none", partial: false },
    ], async (page) => {
      for (const text of ["Premier message.", "Deuxième message.", "Troisième message.", "Quatrième message."]) {
        await say(page, text);
      }
      assert.deepEqual((await notes(page)).map((n) => n.text), [
        "Contexte partiel : " + STALE + ".",
        "Contexte partiel : mémoire indisponible.",
        "",
        "",
      ]);
    });
  });

// Core refuses this note (validate_context_note: an index state requires memory "sent"). Defence in depth:
// if such a note ever reached the screen, an absent memory must not be described by an index state.
test("a forged index state on a memory that was not sent is not displayed",
  { skip: SKIP },
  async () => {
    await withContexts([
      { ...BASE, memory: "dropped_for_budget", memory_index: "INDEX_STALE", partial: true },
      { ...BASE, memory: "unavailable", memory_index: "INDEX_UNVERIFIED", partial: true },
    ], async (page) => {
      await say(page, "Premier message.");
      await say(page, "Deuxième message.");
      assert.deepEqual((await notes(page)).map((n) => n.text), [
        "Contexte partiel : mémoire non transmise (taille).",
        "Contexte partiel : mémoire indisponible.",
      ]);
    });
  });
