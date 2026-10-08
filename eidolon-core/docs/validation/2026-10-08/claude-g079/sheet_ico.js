/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : sheet_ico.js
 * Description : Planche des images extraites de icon.ico, 1:1 et agrandies sans lissage, sur trois fonds (C-TASK-G079)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// NODE_PATH=<playwright> node sheet_ico.js <dir with entry-<size>.png from inspect_ico.py> <out.png>
"use strict";
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
const SIZES = [16, 24, 32, 48, 256];
const BACKS = [["clair (#f3f3f3)", "#f3f3f3", "#1b1b1b"], ["sombre (#202020)", "#202020", "#f0f0f0"], ["fond bleu (#1d4e89)", "#1d4e89", "#ffffff"]];
(async () => {
  const [dir, out] = process.argv.slice(2);
  const src = (s) => "data:image/png;base64," + fs.readFileSync(path.join(dir, `entry-${s}.png`)).toString("base64");
  const cell = (s, bg, ink) => `<td style="background:${bg};color:${ink}">
      <img src="${src(s)}" width="${s}" height="${s}"><br>
      ${s <= 48 ? `<img src="${src(s)}" width="${s * 6}" height="${s * 6}" style="image-rendering:pixelated">` : ""}</td>`;
  const html = `<html><body style="margin:0;font:13px system-ui;background:#fff">
    <table style="border-collapse:collapse"><tr><th></th>${SIZES.map((s) => `<th style="padding:6px">${s} px (1:1 puis ×6)</th>`).join("")}</tr>
    ${BACKS.map(([label, bg, ink]) => `<tr><th style="padding:6px">${label}</th>${SIZES.map((s) => cell(s, bg, ink)).join("")}</tr>`).join("")}
    </table><style>td{padding:10px;text-align:center;vertical-align:middle}</style></body></html>`;
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ deviceScaleFactor: 1 });
    await page.setContent(html);
    await page.locator("table").screenshot({ path: out });
  } finally { await browser.close(); }
  console.log("wrote " + out);
})().catch((e) => { console.error(e); process.exit(1); });
