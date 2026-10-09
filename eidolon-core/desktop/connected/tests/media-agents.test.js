/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : media-agents.test.js
 * Description : Brouillons média, séparation des agents et absence d'envoi
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path");
const M = require("../src/media-agents.js");
const { WEB_ROOT, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } = require("./helpers.js");
const image = { name: "référence.png", type: "image/png", size: 42 };
const video = { name: "séquence.mp4", type: "video/mp4", size: 3000 };

test("all six operations prepare drafts, never submissions", () => {
  for (const agent of ["image", "video"]) for (const op of ["create", "edit", "analyze"]) {
    const d = M.prepareDraft(agent, op, "Mon idée", op === "create" ? null : agent === "image" ? image : video, "landscape", 5);
    assert.equal(d.state, "LOCAL_DRAFT"); assert.equal(d.submitted, false);
    assert.equal(d.output === null, op === "analyze");
    assert.equal(d.agent, agent);
  }
});
test("editing and analysis require a compatible source", () => {
  for (const op of ["edit", "analyze"]) {
    assert.throws(() => M.prepareDraft("image", op, "test", null, "square", null));
    assert.throws(() => M.prepareDraft("video", op, "test", image, "square", 5));
  }
  assert.throws(() => M.prepareDraft("image", "create", "test", video, "square", null));
  assert.equal(M.prepareDraft("video", "create", "test", image, "square", 5).source.type, "image/png");
});
test("budgets and input bounds reject oversized, empty or unsupported files", () => {
  for (const file of [{ ...image, size: 0 }, { ...image, size: 20 * 1024 * 1024 + 1 },
    { ...image, type: "image/svg+xml" }, { ...image, name: "bad\nname" }, { ...image, size: NaN }]) {
    assert.throws(() => M.prepareDraft("image", "analyze", "test", file, null, null));
  }
  assert.throws(() => M.prepareDraft("image", "create", " ", null, "square", null));
  assert.throws(() => M.prepareDraft("image", "create", "x".repeat(4001), null, "square", null));
  assert.throws(() => M.prepareDraft("video", "create", "test", null, "square", true));
});
test("preparation reads metadata only, never file content or paths", () => {
  const file = { ...image, arrayBuffer() { throw Error("content read"); },
    get path() { throw Error("path read"); }, get content() { throw Error("content read"); } };
  assert.deepEqual(M.prepareDraft("image", "analyze", "test", file, null, null).source, image);
});

// DOM event unit bench; real rendering is a separate Chromium test below.
function documentFixture() {
  const elements = new Map();
  const doc = { getElementById: (id) => elements.get(id), activeElement: null };
  for (const match of fs.readFileSync(path.join(WEB_ROOT, "index.html"), "utf8").matchAll(/\bid="([^"]+)"/g)) {
    const e = { id: match[1], value: "", textContent: "", hidden: false, files: [], disabled: false, attributes: {}, handlers: {},
      setAttribute(k, v) { this.attributes[k] = v; }, focus() { doc.activeElement = this; },
      addEventListener(k, fn) { (this.handlers[k] ||= []).push(fn); },
      fire(k) { let prevented = false; for (const fn of this.handlers[k] || []) fn({ preventDefault() { prevented = true; } }); return prevented; }
    }; elements.set(e.id, e);
  }
  for (const agent of ["image", "video"]) {
    doc.getElementById(agent + "-form").reset = () => {
      for (const [key, value] of [["mode", "create"], ["format", "square"], ["duration", "5"], ["prompt", ""], ["source", ""]]) {
        const e = doc.getElementById(agent + "-" + key); if (e) { e.value = value; e.files = []; }
      }
    };
    doc.getElementById(agent + "-form").reset();
  }
  return doc;
}
test("workspace navigation preserves separate drafts, edits invalidate summary, clear removes files", () => {
  const doc = documentFixture(), get = (id) => doc.getElementById(id), ui = M.mount(doc);
  get("open-image").fire("click"); assert.equal(doc.activeElement.id, "image-title");
  get("image-prompt").value = "<img src=x onerror=alert(1)>";
  assert.equal(get("image-form").fire("submit"), true);
  assert.equal(get("image-request").textContent, "<img src=x onerror=alert(1)>");
  assert.equal(get("image-draft").hidden, false);
  get("open-video").fire("click"); assert.equal(get("image-workspace").hidden, true);
  get("video-prompt").value = "Une vidéo";
  get("open-image").fire("click"); assert.equal(get("image-prompt").value, "<img src=x onerror=alert(1)>");
  get("image-form").fire("input"); assert.equal(get("image-draft").hidden, true);
  get("image-source").files = [image]; ui.clear();
  assert.equal(get("image-prompt").value, ""); assert.deepEqual(get("image-source").files, []);
  assert.equal(get("video-prompt").value, ""); assert.equal(get("image-workspace").hidden, true);
});
test("analysis hides generation settings and missing sources produce a useful message", () => {
  const doc = documentFixture(), get = (id) => doc.getElementById(id); M.mount(doc);
  get("video-mode").value = "analyze"; get("video-mode").fire("change");
  assert.equal(get("video-settings").hidden, true);
  get("video-prompt").value = "Que se passe-t-il ?"; get("video-form").fire("submit");
  assert.match(get("video-status").textContent, /Choisissez le fichier/);
  get("video-source").files = [video]; get("video-form").fire("submit");
  assert.equal(get("video-draft").hidden, false);
});
test("read-only HTML has no execution command button, including disabled placeholders (C103)", () => {
  const html = fs.readFileSync(path.join(WEB_ROOT, "index.html"), "utf8");
  const buttons = [...html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/gi)];
  assert.equal(buttons.filter(m => /approuv|lancer|annuler|exécut/i.test(m[1])).length, 0);
  for (const agent of ["image", "video"]) {
    assert.match(html, new RegExp('<p id="' + agent + '-availability"[^>]*>Exécution : indisponible</p>'));
  }
});
test("Chromium: media workspaces send nothing, preserve escaped text and reset on disconnect", { skip: noPython || chromiumUnavailable }, async () => {
  const fx = makeFixture(); let server, browser;
  try {
    server = await startServer(fx, WEB_ROOT); browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 360, height: 800 } });
    await page.goto(server.base);
    const calls = []; page.on("request", r => calls.push(r.url()));
    await page.click("#open-image"); await page.fill("#image-prompt", "<img src=x onerror=alert(1)>");
    await page.click("#image-prepare");
    assert.equal(await page.locator("#image-request img").count(), 0);
    assert.equal(await page.locator("#image-availability").textContent(), "Exécution : indisponible");
    assert.equal(await page.locator("#image-run").count(), 0);
    await page.click("#open-video"); await page.selectOption("#video-mode", "analyze");
    await page.fill("#video-prompt", "Analyse"); await page.click("#video-prepare");
    assert.match(await page.locator("#video-status").textContent(), /Choisissez/);
    assert.deepEqual(calls, []);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.fill("#token", fx.token); await page.click("#connect");
    await page.waitForSelector(".mission-button"); await page.click("#disconnect");
    assert.equal(await page.inputValue("#image-prompt"), "");
    assert.equal(await page.inputValue("#video-prompt"), "");
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
});
