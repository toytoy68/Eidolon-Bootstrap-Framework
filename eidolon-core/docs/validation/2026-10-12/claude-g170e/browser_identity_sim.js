/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : browser_identity_sim.js
 * Description : Recette navigateur de la simulation G170-E : aucun capteur ni réseau, parcours au clavier, captures
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// node browser_identity_sim.js <path to desktop/identity-sim/index.html> [captures dir]   (NODE_PATH -> playwright)
"use strict";
const { chromium } = require("playwright");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

(async () => {
  const [page_path, captures] = process.argv.slice(2);
  const url = pathToFileURL(path.resolve(page_path)).href;
  const out = { checks: [] };
  const check = (name, ok, detail) => out.checks.push({ check: name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 160) });
  const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: "/opt/pw-browsers/chromium" });
  try {
    for (const [width, height] of [[1920, 1080], [360, 760]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      const errors = [], foreign = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      page.on("request", (r) => { if (!r.url().startsWith("file:")) foreign.push(r.url()); });
      await page.addInitScript(() => {
        window.__sensor = 0;
        if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = () => { window.__sensor++; return Promise.reject(new Error("blocked")); };
      });
      await page.goto(url);
      const click = (name) => page.getByRole("button", { name, exact: true }).click();
      await click("Enregistrer voix · Alpha (inventé)");
      check(width + " consent first", (await page.textContent("#flow-text")).includes("présente et d'accord"));
      await click("La personne est présente et d'accord");
      await click("Commencer la prise");
      check(width + " indicator on while capturing", await page.isVisible("#indicator"));
      if (captures && width === 1920) await page.screenshot({ path: path.join(captures, "g170e-capturing-1920.png") });
      await click("Prise trop courte (simulée)");
      check(width + " retry message", (await page.textContent("#flow-text")).startsWith("Prise trop courte"));
      check(width + " indicator off after capture", !(await page.isVisible("#indicator")));
      for (let i = 0; i < 3; i++) { await click("Commencer la prise"); await click("Prise réussie (simulée)"); }
      await click("Confirmer");
      check(width + " enrolled, no right", (await page.textContent("#flow-text")).includes("Aucun droit"));
      check(width + " table updated", (await page.textContent("#profiles")).includes("Voix : enregistrée"));
      await page.selectOption("#proposal-state", "known");
      check(width + " suggestion only", /non vérifié.*connexion manuelle/.test(await page.textContent("#suggestion")));
      await page.selectOption("#proposal-state", "ambiguous");
      check(width + " ambiguous names nobody", !/Alpha|Beta/.test(await page.textContent("#suggestion")));
      if (captures) await page.screenshot({ path: path.join(captures, "g170e-enrolled-" + width + ".png"), fullPage: true });
      // keyboard: delete through Tab/Enter, then cancel with Enter on "Annuler"
      await page.getByRole("button", { name: "Effacer voix · Alpha (inventé)" }).focus();
      await page.keyboard.press("Enter");
      check(width + " delete asks confirmation", (await page.textContent("#flow-title")).startsWith("Effacer"));
      await click("Effacer définitivement");
      check(width + " deleted", (await page.textContent("#flow-text")).startsWith("Effacé"));
      check(width + " no horizontal scroll", await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
      check(width + " no sensor requested", (await page.evaluate(() => window.__sensor)) === 0);
      check(width + " no network", foreign.length === 0, foreign.join(" "));
      check(width + " no page error", errors.length === 0, errors.join(" | "));
      await page.close();
    }
  } finally { await browser.close(); }
  out.passed = out.checks.filter((c) => c.ok).length; out.total = out.checks.length;
  console.log(JSON.stringify(out, null, 1));
  process.exit(out.passed === out.total ? 0 : 1);
})();
