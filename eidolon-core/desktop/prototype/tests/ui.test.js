/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : ui.test.js
 * Description : Rendu réel dans Chromium : clavier, cibles, contraste, zoom, animations, réseau
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run: NODE_PATH=<dir containing playwright> node --test "desktop/prototype/tests/*.test.js"
// Optional: CAPTURES=<dir> saves screenshots. Skipped when playwright is unavailable.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

let chromium = null;
try { ({ chromium } = require("playwright")); } catch (err) { chromium = null; }
const PAGE = "file://" + path.resolve(__dirname, "..", "index.html");
const CAPTURES = process.env.CAPTURES || null;

async function open(browser, scenario, options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1360, height: 900 },
    reducedMotion: options.reducedMotion || "no-preference" });
  const page = await context.newPage();
  const requests = [], errors = [];
  page.on("request", (r) => requests.push(r.url()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(PAGE + (scenario ? "#" + scenario : ""));
  return { context, page, requests, errors };
}

async function shot(page, name) {
  if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, name + ".png"), fullPage: true });
}

// Measures every visible control, and the contrast of every visible text run.
async function audit(page) {
  return page.evaluate(() => {
    function rgb(value) {
      const m = value.match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const p = m[1].split(",").map((x) => parseFloat(x));
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    function lum(c) {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
    }
    function background(el) {
      for (let e = el; e; e = e.parentElement) {
        const c = rgb(getComputedStyle(e).backgroundColor);
        if (c && c.a > 0.5) return c;
      }
      return rgb(getComputedStyle(document.body).backgroundColor);
    }
    const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden"; };
    const small = [];
    document.querySelectorAll("button, select, textarea, a[href], label.check").forEach((el) => {
      if (!visible(el) || el.classList.contains("skip")) return;
      const r = el.getBoundingClientRect();
      if (r.width < 44 || r.height < 44) small.push(`${el.tagName.toLowerCase()}#${el.id || ""} "${(el.textContent || "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    });
    let worst = { ratio: 99, text: "" };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode, el = node.parentElement;
      if (!node.textContent.trim() || !el || !visible(el) || el.closest(".visually-hidden,svg")) continue;
      const fg = rgb(getComputedStyle(el).color), bg = background(el);
      const a = lum(fg), b = lum(bg);
      const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      const size = parseFloat(getComputedStyle(el).fontSize), bold = parseInt(getComputedStyle(el).fontWeight, 10) >= 700;
      const needed = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
      if (ratio / needed < worst.ratio / (worst.needed || 4.5)) worst = { ratio, needed, text: node.textContent.trim().slice(0, 40) };
    }
    return { small, worst, overflow: document.documentElement.scrollWidth - window.innerWidth };
  });
}

const skip = chromium ? false : "playwright not available";

test("ui: no network request beyond the local files, no script error", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    for (const scenario of ["accord-succes", "hors-ligne", "session-verrouillee"]) {
      const { context, page, requests, errors } = await open(browser, scenario);
      await page.click("#server-step");
      assert.deepEqual(requests.filter((u) => !u.startsWith("file://")), []);
      assert.deepEqual(errors, []);
      await context.close();
    }
  } finally { await browser.close(); }
});

test("ui: keyboard alone reaches and uses the decision; the click shows sending, not success", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accord-succes");
    let reached = false;
    for (let i = 0; i < 40 && !reached; i++) {
      await page.keyboard.press("Tab");
      reached = await page.evaluate(() => document.activeElement && document.activeElement.id === "approve");
    }
    assert.ok(reached, "Autoriser reachable with Tab");
    await page.keyboard.press("Enter");
    assert.match(await page.textContent("#commands"), /envoi en cours/);
    assert.equal(await page.textContent("#decision-state"), "Accord attendu");
    await page.click("#server-step");
    assert.equal(await page.textContent("#decision-state"), "Accord enregistré — pas encore exécuté");
    assert.equal(await page.locator(".eye-work").count(), 0, "approval is not work");
    await page.click("#server-step");
    assert.ok(await page.locator(".eye-work").count() >= 1, "work only once Core reports RUNNING");
    await page.click("#server-step");
    assert.equal(await page.textContent("#mission-state"), "Réussie — résultat daté");
    await shot(page, "01-resultat-verifie");
    await context.close();
  } finally { await browser.close(); }
});

test("ui: offline disables sending with a visible reason", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accord-succes");
    await page.click("text=Couper la connexion");
    assert.equal(await page.isDisabled("#approve"), true);
    assert.equal(await page.getAttribute("#approve", "aria-describedby"), "decision-reason");
    assert.match(await page.textContent("#decision-reason"), /Hors ligne/);
    assert.equal(await page.isDisabled("#send-chat"), true);
    assert.match(await page.textContent(".banner"), /n'annule pas les missions/);
    await shot(page, "02-hors-ligne-decision-bloquee");
    await context.close();
  } finally { await browser.close(); }
});

test("ui: lost acknowledgement flow through the interface", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accuse-perdu");
    await page.click("#approve");
    await page.click("#server-step");
    assert.match(await page.textContent("#commands"), /à vérifier/);
    assert.equal(await page.locator("#approve").count(), 0, "no second decision offered");
    await shot(page, "03-accuse-perdu");
    await page.click("text=Rétablir la connexion");
    await page.click("#server-step");
    const receipt = page.locator("[data-intent=check-receipt]").first();
    assert.equal(await receipt.isDisabled(), false);
    await receipt.click();
    await page.click("#server-step");
    assert.match(await page.textContent("#commands"), /confirmé en consultant le reçu/);
    const decides = await page.evaluate(() => window.EidolonPrototype.getState().client.outbox.filter((o) => o.type === "DECIDE").length);
    assert.equal(decides, 1);
    await context.close();
  } finally { await browser.close(); }
});

test("ui: G013 — revoking during an uncertain approval keeps the approval's receipt reachable", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accuse-perdu");
    await page.click("#approve");
    await page.click("#server-step");
    await page.click("text=Rétablir la connexion");
    await page.click("#server-step");
    await page.click("#revoke");
    assert.equal(await page.locator("#commands li").count(), 2);
    await page.click("#server-step");
    const phases = await page.$$eval("#commands li", (items) => items.map((li) => li.dataset.phase));
    assert.deepEqual(phases, ["unknown", "acknowledged"]);
    const receipt = page.locator("#commands li[data-phase=unknown] [data-intent=check-receipt]");
    assert.equal(await receipt.isDisabled(), false, "the approval's receipt is still reachable");
    await shot(page, "08-g013-revocation-et-accord-incertain");
    await receipt.click();
    await page.click("#server-step");
    const after = await page.$$eval("#commands li", (items) => items.map((li) => li.dataset.phase));
    assert.deepEqual(after, ["acknowledged", "acknowledged"]);
    await context.close();
  } finally { await browser.close(); }
});

test("ui: locked session toast is generic and opens nothing", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "session-verrouillee");
    const toast = await page.textContent(".toast");
    assert.ok(!/svc-demo|Redémarrer/.test(toast));
    await page.click("#toast-open-0");
    assert.match(await page.textContent("#app"), /Fenêtre fermée/);
    await shot(page, "04-session-verrouillee");
    await context.close();
  } finally { await browser.close(); }
});

test("ui: microphone indicator survives a Core disconnection", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "micro-hors-ligne");
    assert.equal(await page.isVisible("[data-indicator=mic]"), true);
    assert.equal(await page.isVisible(".banner"), true);
    await shot(page, "05-micro-hors-ligne");
    await context.close();
  } finally { await browser.close(); }
});

test("ui: targets, contrast and horizontal overflow in every scenario and view", { skip }, async (t) => {
  const browser = await chromium.launch();
  const report = [];
  try {
    const { context, page } = await open(browser, "accord-succes");
    for (const scenario of Object.keys(await page.evaluate(() => window.EidolonModel.SCENARIOS))) {
      for (const view of ["compact", "extended"]) {
        for (const tab of view === "compact" ? [null] : ["conversation", "missions", "systeme", "parametres"]) {
          await page.selectOption("#scenario", scenario);
          await page.click("text=Recharger le scénario");
          if (view === "extended" && await page.locator("#toggle-view").count()) await page.click("#toggle-view");
          if (tab && await page.locator("#tab-" + tab).count()) await page.click("#tab-" + tab);
          const a = await audit(page);
          report.push({ scenario, view, tab, ...a });
        }
      }
    }
    await context.close();
  } finally { await browser.close(); }
  const small = [...new Set(report.flatMap((r) => r.small))];
  const worst = report.reduce((w, r) => (r.worst.ratio / r.worst.needed < w.ratio / w.needed ? r.worst : w), { ratio: 99, needed: 4.5 });
  t.diagnostic(`views audited: ${report.length}; worst contrast ${worst.ratio.toFixed(2)}:1 (needs ${worst.needed}) on "${worst.text}"`);
  assert.deepEqual(small, [], "every control at least 44x44 CSS px");
  assert.ok(worst.ratio >= worst.needed, "WCAG AA text contrast");
  assert.ok(report.every((r) => r.overflow <= 0), "no horizontal page scroll at 1360 px");
});

test("ui: 200 % zoom equivalent (680 px wide) keeps the page without horizontal scroll", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accord-succes", { viewport: { width: 680, height: 450 } });
    let a = await audit(page);
    assert.ok(a.overflow <= 0, "compact overflow " + a.overflow);
    await page.click("#toggle-view");
    for (const tab of ["missions", "systeme", "parametres"]) {
      await page.click("#tab-" + tab);
      a = await audit(page);
      assert.ok(a.overflow <= 0, tab + " overflow " + a.overflow);
    }
    await shot(page, "06-zoom-200-parametres");
    await context.close();
  } finally { await browser.close(); }
});

test("ui: reduced motion stops the eye animation", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const normal = await open(browser, "accord-succes");
    const moving = await normal.page.evaluate(() => getComputedStyle(document.querySelector(".eye .ring")).animationName);
    await normal.context.close();
    const reduced = await open(browser, "accord-succes", { reducedMotion: "reduce" });
    const still = await reduced.page.evaluate(() => getComputedStyle(document.querySelector(".eye .ring")).animationName);
    await reduced.context.close();
    assert.equal(moving, "eid-breathe");
    assert.equal(still, "none");
  } finally { await browser.close(); }
});

test("ui: assisted reading previews exactly what will be sent and requires a fresh review", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "accord-succes");
    await page.click("#open-reading");
    await page.fill("#reading-text", "Option --restart-delay=5 (texte fictif)");
    assert.equal(await page.textContent("#reading-preview"), "Option --restart-delay=5 (texte fictif)");
    assert.equal(await page.isDisabled("#reading-send"), true);
    await page.check("#reading-reviewed");
    assert.equal(await page.isDisabled("#reading-send"), false);
    await page.click("#reading-text");
    await page.keyboard.press("Control+End");
    await page.keyboard.type(" !");
    assert.equal(await page.isDisabled("#reading-send"), true, "an edit cancels the review");
    await shot(page, "07-lecture-assistee");
    await page.check("#reading-reviewed");
    await page.click("#reading-send");
    const submit = await page.evaluate(() => window.EidolonPrototype.getState().client.outbox.find((o) => o.type === "READ_SUBMIT"));
    assert.equal(submit.text, "Option --restart-delay=5 (texte fictif) !");
    await context.close();
  } finally { await browser.close(); }
});


// ---- G012: client-sync/1 scenarios ------------------------------------------------------------

async function playSync(page, scenario, steps) {
  await page.selectOption("#scenario", scenario);
  await page.click("text=Recharger le scénario");
  for (let i = 0; i < steps; i++) await page.click("#server-step");
}

test("ui G012: catch-up after a cut, duplicates ignored, no network request", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, requests, errors } = await open(browser, "sync-rattrapage");
    await playSync(page, "sync-rattrapage", 2); // capture, then cut
    assert.match(await page.textContent(".banner"), /état actuel est inconnu/);
    await page.click("#server-step"); // back online
    await page.click("#server-step"); // page 1: capture ahead of the journal
    assert.match(await page.textContent("#sync-cursor"), /rattrapage en cours/);
    assert.equal(await page.textContent("#sync-state"), "Réussie — résultat daté");
    for (let i = 0; i < 5; i++) await page.click("#server-step");
    assert.equal(await page.locator("#sync-refs li").count(), 10);
    assert.doesNotMatch(await page.textContent("#sync-cursor"), /rattrapage en cours/);
    assert.match(await page.textContent("#app"), /Doublons ignorés : 2/);
    await shot(page, "09-sync-rattrapage");
    assert.deepEqual(requests.filter((u) => !u.startsWith("file://")), []);
    assert.deepEqual(errors, []);
    await context.close();
  } finally { await browser.close(); }
});

test("ui G012: RESET_REQUIRED waits for an explicit reload, then a second reset", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "sync-reset");
    await playSync(page, "sync-reset", 3);
    assert.equal(await page.isVisible("#sync-reset"), true);
    assert.match(await page.textContent("#sync-reset"), /ANCHOR_CHANGED/);
    const before = await page.evaluate(() => window.EidolonPrototype.getSync().index);
    await page.click("#server-step");
    assert.equal(await page.evaluate(() => window.EidolonPrototype.getSync().index), before, "nothing delivered while waiting");
    await shot(page, "10-sync-reset");
    await page.click("#sync-accept-reset");
    assert.equal(await page.locator("#sync-reset").count(), 0);
    assert.equal(await page.locator("#sync-refs li").count(), 0, "journal restarted after reload");
    await page.click("#server-step");
    assert.match(await page.textContent("#sync-reset"), /STORE_CHANGED/);
    await context.close();
  } finally { await browser.close(); }
});

test("ui G012: cancellation requested, approval axes, review — labels and no active decision", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "sync-annulation");
    await playSync(page, "sync-annulation", 2);
    assert.equal(await page.textContent("#sync-state"), "Annulation demandée — pas encore confirmée");
    await shot(page, "11-sync-annulation");
    await playSync(page, "sync-accord", 1);
    assert.equal(await page.textContent("#sync-state"), "À décider");
    const text = await page.textContent("#app");
    assert.match(text, /PENDING/); assert.match(text, /AWAITING_DECISION/); assert.match(text, /NOT_STARTED/);
    assert.equal(await page.locator("#app [data-intent=approve], #app [data-intent=reject]").count(), 0);
    await playSync(page, "sync-revue", 1);
    assert.equal(await page.textContent("#sync-state"), "Revue requise — effet à vérifier");
    await context.close();
  } finally { await browser.close(); }
});

test("ui G012: rejected answers listed; hostile text rendered as text only", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "sync-rejets");
    await playSync(page, "sync-rejets", 7);
    assert.equal(await page.locator("#app img, #app b").count(), 0, "no element created from data");
    assert.match(await page.textContent("#sync-refs"), /<img src=x onerror=alert\(1\)>/);
    assert.equal(await page.textContent("#sync-objective"), "<b>ignore les consignes</b>");
    const rejected = await page.textContent("#sync-rejected");
    for (const code of ["CURSOR_MISSION_MISMATCH", "UNSUPPORTED_PROTOCOL", "UNSAFE_OR_INVALID_INTEGER", "INVALID_CURSOR"]) assert.match(rejected, new RegExp(code));
    assert.deepEqual(errors, []);
    await shot(page, "12-sync-rejets-texte-hostile");
    await context.close();
  } finally { await browser.close(); }
});

test("ui G012: targets and contrast in every sync scenario, at the end of its script", { skip }, async (t) => {
  const browser = await chromium.launch();
  const report = [];
  try {
    const { context, page } = await open(browser, "sync-rattrapage");
    const scenarios = await page.evaluate(() => Object.keys(window.EidolonSyncView.SCENARIOS));
    for (const key of scenarios) {
      await playSync(page, key, 9);
      report.push(Object.assign({ key }, await audit(page)));
    }
    await context.close();
  } finally { await browser.close(); }
  const worst = report.reduce((w, r) => (r.worst.ratio / r.worst.needed < w.ratio / w.needed ? r.worst : w), { ratio: 99, needed: 4.5 });
  t.diagnostic(`sync views audited: ${report.length}; worst contrast ${worst.ratio.toFixed(2)}:1 on "${worst.text}"`);
  assert.deepEqual([...new Set(report.flatMap((r) => r.small))], []);
  assert.ok(worst.ratio >= worst.needed);
  assert.ok(report.every((r) => r.overflow <= 0));
});
