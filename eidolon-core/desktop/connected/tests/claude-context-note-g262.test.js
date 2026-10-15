/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : claude-context-note-g262.test.js
 * Description : Contre-revue G261 du diagnostic d'index rendu dans Chromium, large et mobile (Claude, G262-7)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Real Chromium, real server (--conversations simulated, loopback, synthetic state). Interception only
// replaces reply.context. Checks the RENDERED turn, not only the function: wording, visibility, no
// overflow, no server text echoed, and source/bundle parity on a wider table than G261's. No todo.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn, spawnSync } = require("node:child_process");
const { contextNote } = require("../src/conversation.js");
const { WEB_ROOT, PYTHON, ENV, CORE, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } =
  require("./helpers.js");

const SKIP = noPython || chromiumUnavailable;
const STALE = "des changements de mémoire ne sont pas encore reflétés dans l’index";
const UNKNOWN = "l’état de l’index mémoire n’est pas reconnu";
const BASE = { history_sent: 0, history_excluded: 0, memory: "sent", memory_items: 0, memory_truncated_items: 0,
  observations_sent: 0, observations_excluded: 0 };
const FUTURE = "INDEX_REBUILD_IN_PROGRESS";

// [label, context, expected note text or ""]
const TURNS = [
  ["future state, partial true", { ...BASE, memory_index: FUTURE, partial: true }, "Contexte partiel : " + UNKNOWN + "."],
  ["future state, partial false", { ...BASE, memory_index: FUTURE, partial: false }, "Contexte partiel : " + UNKNOWN + "."],
  ["STALE, partial absent", { ...BASE, memory_index: "INDEX_STALE" }, "Contexte partiel : " + STALE + "."],
  ["STALE, partial false, 2 excluded", { ...BASE, history_excluded: 2, memory_index: "INDEX_STALE", partial: false },
    "Contexte partiel : 2 échanges plus anciens non transmis au modèle ; " + STALE + "."],
  ["MATCH, complete", { ...BASE, memory_items: 2, memory_index: "INDEX_SNAPSHOT_MATCH", partial: false }, ""],
  ["dropped + future state", { ...BASE, memory: "dropped_for_budget", memory_index: FUTURE, partial: true },
    "Contexte partiel : mémoire non transmise (taille)."],
  ["none + STALE, partial false", { ...BASE, memory: "none", memory_index: "INDEX_STALE", partial: false }, ""],
];

const EDGES = [
  ["INDEX_ only", { ...BASE, memory_index: "INDEX_", partial: false }, null],
  ["64 characters after INDEX_", { ...BASE, memory_index: "INDEX_" + "A".repeat(64), partial: false },
    "Contexte partiel : " + UNKNOWN + "."],
  ["65 characters after INDEX_", { ...BASE, memory_index: "INDEX_" + "A".repeat(65), partial: false }, null],
  ["trailing newline", { ...BASE, memory_index: "INDEX_STALE\n", partial: false }, null],
  ["object state", { ...BASE, memory_index: { toString: () => "INDEX_STALE" }, partial: false }, null],
];

test("Node source: G261 rules and edges", () => {
  for (const [label, note, expected] of [...TURNS.map(([l, n, e]) => [l, n, e || null]), ...EDGES]) {
    assert.equal(contextNote(note), expected, label);
  }
});

function pair(state) {
  const r = spawnSync(PYTHON, ["-m", "eidolon_core.conversation_api", "--state", state, "pair",
    "--client-id", "pc-g262", "--actor", "toytoy"], { cwd: CORE, env: ENV, encoding: "utf8" });
  if (r.status !== 0) throw new Error("pair failed: " + r.stdout + r.stderr);
  return JSON.parse(r.stdout).token;
}

for (const width of [1280, 320]) {
  test(`rendered turns at ${width}px: wording, visibility, no overflow, no server text`, { skip: SKIP }, async () => {
    const fx = makeFixture();
    let server, browser;
    try {
      fx.key = pair(fx.state);
      server = await startServer(fx, WEB_ROOT, {
        spawnServer: (cmd, args, opts) => spawn(cmd, args.concat(["--conversations", "simulated"]), opts) });
      browser = await chromium.launch();
      const page = await (await browser.newContext({ viewport: { width, height: 640 } })).newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      let n = 0;
      await page.route("**/v1/conversations/turn", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        if (json.reply) json.reply.context = TURNS[n++][1];
        await route.fulfill({ response, json });
      });
      await page.goto(server.base + "/");
      await page.focus("#conv-key");
      await page.keyboard.type(fx.key);
      await page.keyboard.press("Enter");
      await page.waitForSelector("#conv-body:not([hidden])");
      for (let i = 0; i < TURNS.length; i++) {
        await page.fill("#conv-text", `Message ${i}.`);
        await page.click("#conv-send");
        await page.waitForFunction((k) => document.querySelectorAll("#conv-log li .conv-kind").length > k, i);
      }
      const rendered = await page.$$eval("#conv-log > li", (items) => items.map((li) => {
        const p = li.querySelector(".conv-context");
        if (!p) return { text: "", visible: true };
        const r = p.getBoundingClientRect();
        return { text: p.textContent, visible: r.width > 0 && r.height > 0 };
      }));
      assert.deepEqual(rendered.map((r) => r.text), TURNS.map((t) => t[2]));
      assert.ok(rendered.every((r) => r.visible));
      const log = await page.textContent("#conv-log");
      assert.ok(!log.includes(FUTURE) && !log.includes("INDEX_"), "a protocol state is never echoed");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
      const bundle = await page.evaluate((notes) => notes.map((x) => window.EidolonConversation.contextNote(x)),
        [...TURNS, ...EDGES.filter((e) => e[0] !== "object state")].map((t) => t[1]));
      assert.deepEqual(bundle, [...TURNS, ...EDGES.filter((e) => e[0] !== "object state")].map((t) => t[2] || null));
      assert.deepEqual(errors, []);
    } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
  });
}
