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
    const cursorText = await page.textContent("#sync-cursor");
    const stateText = await page.textContent("#sync-state");
    await page.click("#server-step"); // G016: a late answer of the same epoch arrives during the wait
    assert.equal(await page.textContent("#sync-cursor"), cursorText, "cursor frozen");
    assert.equal(await page.textContent("#sync-state"), stateText, "view frozen");
    assert.match(await page.textContent("#app"), /réponses ignorées pendant le reset : 1/);
    const before = await page.evaluate(() => window.EidolonPrototype.getSync().index);
    await page.click("#server-step");
    assert.equal(await page.evaluate(() => window.EidolonPrototype.getSync().index), before, "nothing polled while waiting");
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
    assert.equal(await page.textContent("#sync-state"), "Annulation demandée — issue non confirmée");
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


test("ui G016: review stays primary next to a cancellation request; no relaunch or decision button", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page } = await open(browser, "sync-revue-annulation");
    await playSync(page, "sync-revue-annulation", 1);
    assert.equal(await page.textContent("#sync-state"), "Revue requise — effet à vérifier");
    assert.match(await page.textContent("#sync-cancel"), /Annulation demandée : enregistrée, issue non garantie/);
    assert.match(await page.textContent("#app"), /UNKNOWN/);
    assert.doesNotMatch(await page.textContent("#app"), /attendre la capture CANCELLED/);
    assert.equal(await page.locator("#app button").count(), 0, "no relaunch, approve or cancel button");
    await shot(page, "13-g016-revue-et-annulation");
    await context.close();
  } finally { await browser.close(); }
});

test("ui G016: observed Core capture with objective_kind=null is displayed, nothing invented", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "sync-objectif-null");
    await playSync(page, "sync-objectif-null", 1);
    assert.equal(await page.textContent("#sync-objective"), "Aucun objectif reconnu (hors catalogue)");
    assert.equal(await page.textContent("#sync-state"), "Bloquée — précision demandée");
    assert.equal(await page.locator("#sync-rejected").count(), 0, "not rejected");
    assert.deepEqual(errors, []);
    await shot(page, "14-g016-objectif-nul");
    await context.close();
  } finally { await browser.close(); }
});


// ---- G018: mission-list/1 inventory -----------------------------------------------------------

const EXECUTION_WORDS = /Approuver|Refuser|Lancer|Relancer|Exécuter|Demander l'annulation|Révoquer/;

test("ui G018: complete pagination of observed pages, repeated page ignored, selection read, no network", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, requests, errors } = await open(browser, "liste-pagination");
    await playSync(page, "liste-pagination", 6);
    assert.equal(await page.textContent("#list-status"), "Capture entièrement lue (3)");
    assert.equal(await page.locator("#list-items li").count(), 3);
    assert.match(await page.textContent("#list-stats"), /pages répétées ou tardives ignorées : 1/);
    assert.equal(await page.locator("#list-items .synthetic", { hasText: "observé : trace Core C-008e" }).count(), 3);
    assert.match(await page.textContent("#sel-title"), /dérivé : selection_snapshots/);
    assert.match(await page.textContent("#sel-state"), /Annulation demandée — issue non confirmée/);
    assert.doesNotMatch(await page.textContent("#app"), EXECUTION_WORDS);
    assert.deepEqual(requests.filter((u) => !u.startsWith("file://")), []);
    assert.deepEqual(errors, []);
    await shot(page, "15-g018-pagination-et-selection");
    await context.close();
  } finally { await browser.close(); }
});

test("ui G018: reset between pages keeps the old inventory as stale until an explicit relisting", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "liste-reset");
    await playSync(page, "liste-reset", 3);
    assert.equal(await page.isVisible("#list-reset"), true);
    assert.match(await page.textContent("#list-reset"), /STATE_CHANGED/);
    assert.match(await page.textContent("#list-title"), /PÉRIMÉE/);
    assert.match(await page.textContent("#list-stats"), /réponses ignorées pendant le reset : 1/);
    const index = await page.evaluate(() => window.EidolonPrototype.getSync().index);
    await page.click("#server-step");
    assert.equal(await page.evaluate(() => window.EidolonPrototype.getSync().index), index, "nothing asked while stale");
    await shot(page, "16-g018-reset-entre-pages");
    await page.click("#list-relist");
    assert.equal(await page.locator("#list-reset").count(), 0);
    assert.match(await page.textContent("#list-status"), /Ancien inventaire périmé affiché/);
    for (let i = 0; i < 3; i++) await page.click("#server-step");
    assert.equal(await page.textContent("#list-status"), "Capture entièrement lue (3)");
    assert.doesNotMatch(await page.textContent("#list-title"), /PÉRIMÉE/);
    assert.deepEqual(errors, []);
    await context.close();
  } finally { await browser.close(); }
});

test("ui G018: a late answer for the first selection does not replace the second", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "liste-selection-en-vol");
    await playSync(page, "liste-selection-en-vol", 6); // pages, choice A, choice B, late answer for A
    const ids = await page.evaluate(() => window.EidolonListFixtures.observed.trace.fresh_pages.map((p) => p.items[0].mission.id));
    assert.match(await page.textContent("#sel-title"), new RegExp(ids[1].slice(0, 12)));
    assert.equal(await page.textContent("#sel-state"), "Lecture client-sync demandée…");
    assert.match(await page.textContent("#list-stats"), /réponses de sélection périmées : 1/);
    await page.click("#server-step");
    assert.match(await page.textContent("#sel-title"), new RegExp(ids[1].slice(0, 12)));
    assert.equal(await page.textContent("#sel-state"), "Nouvelle");
    assert.deepEqual(errors, []);
    await shot(page, "17-g018-selection-en-vol");
    await context.close();
  } finally { await browser.close(); }
});

test("ui G018: statuses not confused, user selection by keyboard, hostile text, empty and truncated lists", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "liste-variee");
    await playSync(page, "liste-variee", 1);
    const text = await page.textContent("#list-items");
    for (const label of ["Revue requise — effet à vérifier", "Annulation demandée — issue non confirmée", "Bloquée — précision demandée", "aucun reconnu (hors catalogue)"]) assert.ok(text.includes(label), label);
    assert.doesNotMatch(await page.textContent("#app"), EXECUTION_WORDS);
    assert.equal(await page.locator("#app button").filter({ hasNotText: /Voir la mission/ }).count(), 0, "only read buttons");
    await page.click("#list-items li:nth-child(1) button");
    assert.equal(await page.textContent("#sel-state"), "Revue requise — effet à vérifier");
    assert.match(await page.textContent("#sel-effect"), /^UNKNOWN/);
    await page.focus("#list-items li:nth-child(2) button");
    await page.keyboard.press("Enter");
    assert.match(await page.textContent("#sel-state"), /Revue requise|Annulation|Bloquée|Réussie|Terminée/);
    await shot(page, "18-g018-statuts-varies");
    await playSync(page, "liste-rejets", 6);
    assert.equal(await page.locator("#app img").count(), 0);
    assert.ok((await page.textContent("#list-items")).includes("<img src=x onerror=alert(1)>"));
    const rejected = await page.textContent("#list-rejected");
    for (const code of ["AUTHORITY_CLAIMED", "UNSAFE_OR_INVALID_INTEGER", "GENERATION_MIXED"]) assert.match(rejected, new RegExp(code));
    await playSync(page, "liste-vide", 1);
    assert.equal(await page.textContent("#list-empty"), "Aucune mission sur ce serveur dans cette capture.");
    await playSync(page, "liste-tronquee", 3);
    assert.equal(await page.textContent("#list-status"), "Liste tronquée : 200 affichées sur 250 annoncées");
    assert.deepEqual(errors, []);
    await context.close();
  } finally { await browser.close(); }
});

test("ui G018: targets and contrast in every list scenario, at the end of its script", { skip }, async (t) => {
  const browser = await chromium.launch();
  const report = [];
  try {
    const { context, page } = await open(browser, "liste-pagination");
    const scenarios = await page.evaluate(() => Object.keys(window.EidolonListView.SCENARIOS));
    for (const key of scenarios) {
      await playSync(page, key, 8);
      report.push(Object.assign({ key }, await audit(page)));
    }
    await context.close();
  } finally { await browser.close(); }
  const worst = report.reduce((w, r) => (r.worst.ratio / r.worst.needed < w.ratio / w.needed ? r.worst : w), { ratio: 99, needed: 4.5 });
  t.diagnostic(`list views audited: ${report.length}; worst contrast ${worst.ratio.toFixed(2)}:1 on "${worst.text}"`);
  assert.deepEqual([...new Set(report.flatMap((r) => r.small))], []);
  assert.ok(worst.ratio >= worst.needed);
  assert.ok(report.every((r) => r.overflow <= 0));
});

test("ui G021: a last page inconsistent with the announced total is refused, never shown as complete", { skip }, async () => {
  const browser = await chromium.launch();
  try {
    const { context, page, errors } = await open(browser, "liste-incoherente");
    await playSync(page, "liste-incoherente", 2);
    assert.equal(await page.isVisible("#list-halted"), true);
    assert.match(await page.textContent("#list-halted"), /LIST_ENDED_EARLY/);
    assert.match(await page.textContent("#list-status"), /Liste incomplète : réponse incohérente \(LIST_ENDED_EARLY\), 1 reçues sur 3 annoncées/);
    assert.doesNotMatch(await page.textContent("#app"), /entièrement lue/);
    assert.match(await page.textContent("#list-rejected"), /LIST_ENDED_EARLY/);
    const index = await page.evaluate(() => window.EidolonPrototype.getSync().index);
    await page.click("#server-step");
    assert.equal(await page.evaluate(() => window.EidolonPrototype.getSync().index), index, "nothing asked while halted");
    await shot(page, "19-g021-fin-incoherente");
    await page.click("#list-relist");
    for (let i = 0; i < 3; i++) await page.click("#server-step");
    assert.equal(await page.textContent("#list-status"), "Capture entièrement lue (3)");
    assert.deepEqual(errors, []);
    await context.close();
  } finally { await browser.close(); }
});
