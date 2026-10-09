/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : browser_g127.js
 * Description : La page relit la conversation média (8 demandes) à 1280 et 360 px, sans chemin privé (C-TASK-G127)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// node browser_g127.js <page url> <conversation key> <private folder to look for>  (NODE_PATH → playwright)
"use strict";
const { chromium } = require("playwright");
const path = require("node:path");

(async () => {
  const [url, key, privateDir] = process.argv.slice(2);
  const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: "/opt/pw-browsers/chromium" });
  const out = { ok: false, widths: {} };
  try {
    for (const width of [1280, 360]) {
      const page = await browser.newPage({ viewport: { width, height: width === 360 ? 740 : 720 } });
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(url);
      await page.fill("#conv-key", key);
      await page.press("#conv-key", "Enter");
      await page.waitForSelector("#conv-recent:not([hidden]) button[data-resume]");
      await page.click("#conv-recent-list button[data-resume]");
      await page.waitForFunction(() => document.querySelectorAll("#conv-log li").length >= 8);
      await page.click("#conv-media-load");
      await page.waitForFunction(() => /demande\(s\) ou résultat/.test(document.getElementById("conv-media-state").textContent));
      const list = await page.textContent("#conv-media-list");
      const html = await page.content();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      const tickets = (list.match(/Demande mt-/g) || []).length;
      out.widths[width] = {
        tickets, overflow, errors,
        partial: /Collecte partielle : 1 sur 2/.test(list),
        uncertain: /Tentative enregistrée — le moteur peut encore travailler/.test(list),
        unverified: /non vérifié/.test(list),
        privatePath: html.includes(privateDir), keyShown: html.includes(key),
        buttons: await page.locator("#conv-media-list button, #conv-media-list a, #conv-media-list img").count() };
      if (process.env.CAPTURES) await page.locator("#conv-media").screenshot({ path: path.join(process.env.CAPTURES, `g127-media-${width}.png`) });
      await page.close();
    }
    out.ok = Object.values(out.widths).every((w) => w.tickets === 8 && w.overflow === 0 && !w.errors.length && w.partial
      && w.uncertain && w.unverified && !w.privatePath && !w.keyShown && w.buttons === 0);
  } catch (e) { out.error = String(e); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
