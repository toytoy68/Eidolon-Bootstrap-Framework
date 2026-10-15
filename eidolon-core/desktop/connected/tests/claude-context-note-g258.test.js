/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : claude-context-note-g258.test.js
 * Description : Contre-revue G259 de la note de contexte : source et bundle identiques, notes malformées (Claude, G258-3)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// The same table of notes is evaluated by src/conversation.js (Node) and by the served app.js (real
// Chromium, real server, loopback, synthetic state): both must give exactly the same text. Malformed
// notes must never throw, never describe an absent memory by an index state, and never inject markup.
// Skipped (never passed) without python3 or Chromium. No todo: every assertion here must hold.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { contextNote } = require("../src/conversation.js");
const { WEB_ROOT, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } = require("./helpers.js");

const SKIP = noPython || chromiumUnavailable;
const STALE = "des changements de mémoire ne sont pas encore reflétés dans l’index";
const UNVERIFIED = "la mise à jour complète de l’index mémoire n’a pas pu être vérifiée";
const SENT = { history_sent: 0, history_excluded: 0, memory: "sent", memory_items: 0, memory_truncated_items: 0,
  observations_sent: 0, observations_excluded: 0, partial: true };

// [label, note, expected text or null]
const CASES = [
  ["absent", undefined, null], ["null", null, null], ["string", "INDEX_STALE", null], ["number", 42, null],
  ["array", ["INDEX_STALE"], null], ["empty object", {}, null],
  ["sent + STALE, zero excerpt", { ...SENT, memory_index: "INDEX_STALE" }, "Contexte partiel : " + STALE + "."],
  ["sent + UNVERIFIED", { ...SENT, memory_index: "INDEX_UNVERIFIED" }, "Contexte partiel : " + UNVERIFIED + "."],
  ["sent + MATCH, complete", { ...SENT, memory_index: "INDEX_SNAPSHOT_MATCH", partial: false }, null],
  ["sent + STALE + truncated", { ...SENT, memory_items: 2, memory_truncated_items: 1, memory_index: "INDEX_STALE" },
    "Contexte partiel : " + STALE + " ; 1 extrait(s) de mémoire déjà tronqué(s)."],
  ["none + STALE (forged)", { ...SENT, memory: "none", memory_index: "INDEX_STALE" }, null],
  ["absent memory field + STALE", { partial: true, memory_index: "INDEX_STALE" }, null],
  ["memory 'SENT' (case) + STALE", { ...SENT, memory: "SENT", memory_index: "INDEX_STALE" }, null],
  ["memory as object + STALE", { ...SENT, memory: { toString: null }, memory_index: "INDEX_STALE" }, null],
  ["dropped + UNVERIFIED (forged)", { ...SENT, memory: "dropped_for_budget", memory_index: "INDEX_UNVERIFIED" },
    "Contexte partiel : mémoire non transmise (taille)."],
  ["unavailable + STALE (forged)", { ...SENT, memory: "unavailable", memory_index: "INDEX_STALE" },
    "Contexte partiel : mémoire indisponible."],
  ["sent + index as object", { ...SENT, memory_index: { state: "INDEX_STALE" } }, null],
  ["sent + index lower case", { ...SENT, memory_index: "index_stale" }, null],
  ["history 2 + forged index on none", { ...SENT, history_excluded: 2, memory: "none", memory_index: "INDEX_STALE" },
    "Contexte partiel : 2 échanges plus anciens non transmis au modèle."],
];

// Found, not asserted as acceptable: documented in C-MSG-C186 (proposal, no todo here).
//  - sent + an unknown future state ("INDEX_NEW") with partial true renders nothing at all;
//  - sent + STALE with partial false renders nothing: the screen trusts Core's `partial`.

test("Node source: every malformed note is handled without throwing", () => {
  for (const [label, note, expected] of CASES) assert.equal(contextNote(note), expected, label);
});

async function withPage(body, contexts) {
  const fx = makeFixture();
  let server, browser;
  try {
    const { spawnSync } = require("node:child_process");
    const { PYTHON, ENV, CORE } = require("./helpers.js");
    const r = spawnSync(PYTHON, ["-m", "eidolon_core.conversation_api", "--state", fx.state, "pair",
      "--client-id", "pc-g258", "--actor", "toytoy"], { cwd: CORE, env: ENV, encoding: "utf8" });
    if (r.status !== 0) throw new Error("pair failed: " + r.stdout + r.stderr);
    fx.key = JSON.parse(r.stdout).token;
    server = await startServer(fx, WEB_ROOT, {
      spawnServer: (cmd, args, opts) => spawn(cmd, args.concat(["--conversations", "simulated"]), opts) });
    browser = await chromium.launch();
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    if (contexts) {
      let n = 0;
      await page.route("**/v1/conversations/turn", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        if (json.reply) json.reply.context = contexts[n++];
        await route.fulfill({ response, json });
      });
    }
    await page.goto(server.base + "/");
    await body(page, fx);
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
}

test("served bundle in Chromium gives exactly the source's text for every case", { skip: SKIP }, async () => {
  await withPage(async (page) => {
    const notes = CASES.map((c) => c[1] === undefined ? "__undefined__" : c[1]);
    const got = await page.evaluate((list) => list.map((n) =>
      window.EidolonConversation.contextNote(n === "__undefined__" ? undefined : n)), notes);
    assert.deepEqual(got, CASES.map((c) => c[2]));
  });
});

test("markup in a malformed counter is never rendered, as text or as elements", { skip: SKIP }, async () => {
  const evil = '<img src=x onerror="window.__pwned=1">';
  await withPage(async (page, fx) => {
    await page.focus("#conv-key");
    await page.keyboard.type(fx.key);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#conv-body:not([hidden])");
    await page.fill("#conv-text", "Bonjour.");
    await page.click("#conv-send");
    await page.waitForSelector("#conv-log li .conv-kind");
    const text = await page.textContent("#conv-log .conv-context");
    // Counters are only rendered when `> 0`; a string such as this never passes, so it is not shown.
    assert.equal(text, "Contexte partiel : mémoire indisponible.");
    assert.equal(await page.locator("#conv-log img").count(), 0);
    assert.equal(await page.evaluate(() => window.__pwned), undefined);
  }, [{ ...SENT, history_excluded: evil, memory: "unavailable", memory_index: "INDEX_STALE" }]);
});
