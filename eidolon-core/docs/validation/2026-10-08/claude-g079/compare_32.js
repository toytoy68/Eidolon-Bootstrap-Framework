/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : compare_32.js
 * Description : 32 px actuel (version complète) contre variante simplifiée, 1:1 et ×6, trois fonds (C-TASK-G079)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/: NODE_PATH=<playwright> node docs/validation/2026-10-08/claude-g079/compare_32.js <out.png>
"use strict";
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
const P = path.resolve(__dirname, "..", "..", "..", "proposals", "2026-10-08-claude-icon-variants", "png");
const VARIANTS = [["actuel (complet)", "logo-e-grand-32.png"], ["proposé (simplifié)", "logo-e-petit-32.png"]];
const BACKS = [["clair", "#f3f3f3", "#1b1b1b"], ["sombre", "#202020", "#f0f0f0"], ["bleu", "#1d4e89", "#ffffff"]];
(async () => {
  const out = process.argv[2];
  const src = (f) => "data:image/png;base64," + fs.readFileSync(path.join(P, f)).toString("base64");
  const html = `<html><body style="margin:0;font:14px system-ui;background:#fff"><table style="border-collapse:collapse">
    <tr><th></th>${VARIANTS.map(([l]) => `<th style="padding:6px">32 px ${l}</th>`).join("")}</tr>
    ${BACKS.map(([l, bg, ink]) => `<tr><th style="padding:6px">${l}</th>${VARIANTS.map(([, f]) => `<td style="background:${bg};color:${ink};padding:12px;text-align:center">
      <img src="${src(f)}" width="32" height="32"> <img src="${src(f)}" width="192" height="192" style="image-rendering:pixelated;vertical-align:middle"></td>`).join("")}</tr>`).join("")}
    </table></body></html>`;
  const browser = await chromium.launch();
  try { const page = await browser.newPage(); await page.setContent(html); await page.locator("table").screenshot({ path: out }); }
  finally { await browser.close(); }
  console.log("wrote " + out);
})().catch((e) => { console.error(e); process.exit(1); });
