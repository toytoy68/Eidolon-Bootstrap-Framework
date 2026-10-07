/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : a11y.test.js
 * Description : Clavier seul, focus, zoom 200 %, 320×640, 1280×720, texte long, contraste, mouvement réduit (C-TASK-G037)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Real Chromium on the real server with the C-009g fixture. Skipped (never passed) without
// python3 or Chromium. CAPTURES=<dir> saves comparable screenshots.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { WEB_ROOT, CAPTURES, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } = require("./helpers.js");

const SKIP = noPython || chromiumUnavailable;

async function withPage(options, body) {
  const fx = makeFixture();
  let server, browser;
  try {
    server = await startServer(fx, WEB_ROOT);
    browser = await chromium.launch();
    const context = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 720 } }, options));
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(server.base + "/");
    await body(page, fx, server);
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
}

const focused = (page) => page.evaluate(() => {
  const e = document.activeElement;
  return e ? (e.id || e.dataset.missionId || e.tagName.toLowerCase()) : null;
});

async function connectByKeyboard(page, token) {
  await page.keyboard.press("Tab");               // skip link
  await page.keyboard.press("Tab");               // token field
  assert.equal(await focused(page), "token");
  await page.keyboard.type(token);
  await page.keyboard.press("Enter");
  await page.waitForSelector(".mission-button");
}

// Contrast of every visible text run and size of every visible control (WCAG 2.2 AA: 4.5:1, 24 px minimum; we aim 44).
async function audit(page) {
  return page.evaluate(() => {
    function rgb(v) { const m = v.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
    function lum(c) { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); }
    function bg(el) { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c && c.a > 0.5) return c; } return { r: 255, g: 255, b: 255 }; }
    const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden"; };
    const low = [], small = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const n = walker.currentNode, el = n.parentElement;
      if (!n.textContent.trim() || !visible(el) || el.closest("[disabled]") || el.closest(".skip")) continue;
      const fg = rgb(getComputedStyle(el).color), b = bg(el);
      const L1 = lum(fg), L2 = lum(b), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      if (ratio < 4.5) low.push(n.textContent.trim().slice(0, 30) + " " + ratio.toFixed(2));
    }
    document.querySelectorAll("button, input, a[href]").forEach((el) => {
      if (!visible(el) || el.classList.contains("skip")) return;
      const r = el.getBoundingClientRect();
      const t = el.type === "checkbox" ? el.closest("label").getBoundingClientRect() : r;
      if (t.height < 24 || t.width < 24) small.push((el.id || el.textContent.trim()).slice(0, 20) + " " + Math.round(t.width) + "x" + Math.round(t.height));
    });
    const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
    return { low, small, overflow };
  });
}

test("keyboard only: connect, list, select, refresh, receipt; focus is never lost to the page body", { skip: SKIP }, async () => {
  await withPage({}, async (page, fx) => {
    await connectByKeyboard(page, fx.token);
    assert.equal(await focused(page), "missions", "after connection, focus goes to the mission list");
    await page.keyboard.press("Tab");             // Relire la liste
    await page.keyboard.press("Tab");             // first mission
    const first = await focused(page);
    assert.match(first, /^m-/);
    await page.keyboard.press("Enter");
    await page.waitForSelector(".fields");
    assert.equal(await focused(page), first, "the selected mission button keeps the focus after re-rendering");
    await page.keyboard.press("Tab");
    assert.notEqual(await focused(page), "body");
    await page.focus("#refresh");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(300);
    assert.equal(await focused(page), "refresh");
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g037-keyboard-1280x720.png"), fullPage: true });
  });
});

test("focus after a refused token goes back to the token field, with the status announced", { skip: SKIP }, async () => {
  await withPage({}, async (page) => {
    await page.fill("#token", "x".repeat(43));
    await page.press("#token", "Enter");
    await page.waitForFunction(() => /Jeton refusé/.test(document.querySelector("#connection-status").textContent));
    assert.equal(await focused(page), "token");
    assert.equal(await page.getAttribute("#connection", "aria-live"), "polite");
  });
});

test("visible focus indicator on every control reached by Tab", { skip: SKIP }, async () => {
  await withPage({}, async (page, fx) => {
    await connectByKeyboard(page, fx.token);
    await page.click(".mission-button");
    await page.waitForSelector(".fields");
    const missing = [];
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const e = document.activeElement;
        if (!e || e === document.body) return null;
        const s = getComputedStyle(e);
        return { id: e.id || e.textContent.trim().slice(0, 15), outline: s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2 };
      });
      if (info && !info.outline) missing.push(info.id);
    }
    assert.deepEqual(missing, []);
  });
});

for (const [name, options] of [
  ["1280x720", { viewport: { width: 1280, height: 720 } }],
  ["zoom 200 % (1280x720 vu à 640x360)", { viewport: { width: 640, height: 360 }, deviceScaleFactor: 2 }],
  ["320x640", { viewport: { width: 320, height: 640 } }]]) {
  test("layout " + name + ": no horizontal scroll, contrast >= 4.5, controls >= 24 px, long text wraps", { skip: SKIP }, async () => {
    await withPage(options, async (page, fx) => {
      await page.fill("#token", fx.token);
      await page.click("#connect");
      await page.waitForSelector(".mission-button");
      await page.click(".mission-button:has-text('" + fx.role("approval_revoked").slice(0, 10) + "')");
      await page.waitForSelector(".fields");
      await page.fill("#receipt-client", "beta-fixture");
      await page.fill("#receipt-key", "historical-approve-" + "x".repeat(60));   // long text
      await page.click("#receipt-lookup");
      await page.waitForSelector(".receipt-missing");
      const result = await audit(page);
      if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g037-" + name.split(" ")[0].replace("%", "") + ".png"), fullPage: true });
      assert.deepEqual(result, { low: [], small: [], overflow: 0 });
    });
  });
}

test("reduced motion: no animation or transition anywhere", { skip: SKIP }, async () => {
  await withPage({ reducedMotion: "reduce" }, async (page) => {
    const moving = await page.evaluate(() => [...document.querySelectorAll("*")].filter((e) => {
      const s = getComputedStyle(e);
      return s.animationName !== "none" || (s.transitionDuration && s.transitionDuration.split(",").some((d) => parseFloat(d) > 0));
    }).length);
    assert.equal(moving, 0);
  });
});

test("dark color scheme keeps contrast", { skip: SKIP }, async () => {
  await withPage({ colorScheme: "dark" }, async (page, fx) => {
    await page.fill("#token", fx.token);
    await page.click("#connect");
    await page.waitForSelector(".mission-button");
    await page.click(".mission-button");
    await page.waitForSelector(".fields");
    const result = await audit(page);
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g037-dark.png"), fullPage: true });
    assert.deepEqual(result.low, []);
  });
});
