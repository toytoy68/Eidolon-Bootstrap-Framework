/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : browser_g083.js
 * Description : Affichage du logo dans Chromium réel : présent → image, absent → nom texte (C-TASK-G083)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// node browser_g083.js <page url> present|missing   (NODE_PATH must reach playwright)
"use strict";
const { chromium } = require("playwright");

(async () => {
  const [url, mode] = process.argv.slice(2);
  const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: "/opt/pw-browsers/chromium" });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    const external = [];
    page.on("request", (r) => { if (!r.url().startsWith(url.replace(/\/$/, ""))) external.push(r.url()); });
    await page.goto(url);
    await page.waitForTimeout(800);
    const state = await page.evaluate(() => ({
      logoShown: !document.getElementById("brand-logo").hidden,
      natural: document.getElementById("brand-logo").naturalWidth,
      nameShown: !document.getElementById("brand-name").hidden }));
    const ok = errors.length === 0 && external.length === 0 &&
      (mode === "present" ? state.logoShown && state.natural > 0 && !state.nameShown
                          : !state.logoShown && state.nameShown);
    console.log(JSON.stringify({ mode, ok, state, errors, external }));
    process.exitCode = ok ? 0 : 1;
  } finally { await browser.close(); }
})().catch((e) => { console.log(String(e)); process.exitCode = 2; });
