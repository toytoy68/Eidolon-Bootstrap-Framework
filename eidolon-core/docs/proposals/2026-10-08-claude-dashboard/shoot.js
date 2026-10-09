/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : shoot.js
 * Description : Captures 1366×768 de la maquette G076, contrôles clavier, contraste et débordement
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// NODE_PATH=<playwright> node shoot.js      (from this folder; file:// only, no network)
"use strict";
const path = require("node:path");
const { chromium } = require("playwright");

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function ratio(a, b) { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); }

(async () => {
  const url = "file://" + path.resolve(__dirname, "mockup.html");
  const browser = await chromium.launch();
  const report = [];
  try {
    for (const [hash, w, h, reduced, sources] of [["a-connected", 1366, 768, false, false], ["b-connected", 1366, 768, false, false],
      ["a-offline", 1366, 768, false, false], ["b-stale", 1366, 768, false, true], ["b-connected", 1920, 1080, true, false], ["a-connected", 1366, 768, false, true]]) {
      const page = await browser.newPage({ viewport: { width: w, height: h }, reducedMotion: reduced ? "reduce" : "no-preference" });
      const requests = [];
      page.on("request", (r) => { if (!r.url().startsWith("file://")) requests.push(r.url()); });
      await page.goto(url + "#" + hash);
      if (sources) await page.click("#sources");
      await page.waitForTimeout(200);
      const name = `${hash}-${w}x${h}${reduced ? "-reduced" : ""}${sources ? "-sources" : ""}.png`;
      await page.screenshot({ path: path.join(__dirname, "captures", name) });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      const anim = await page.evaluate(() => getComputedStyle(document.querySelector(".orb")).animationName);
      // Keyboard: Tab order reaches layout switch, sources toggle, then mission cards.
      const order = [];
      for (let i = 0; i < 8; i++) { await page.keyboard.press("Tab"); order.push(await page.evaluate(() => document.activeElement.id || document.activeElement.className)); }
      report.push({ name, overflow, orb_animation: anim, tab_order: order, external_requests: requests.length });
      await page.close();
    }
  } finally { await browser.close(); }
  const pairs = { "texte / fond": ["#e8f0fb", "#13233a"], "secondaire / panneau": ["#a9bdd6", "#13233a"], "accent / panneau": ["#5aa9ff", "#13233a"],
    "alerte / périmé": ["#f2c25b", "#3a3320"], "OK / panneau": ["#63d69a", "#13233a"], "bouton primaire": ["#ffffff", "#1f63bd"], "focus / fond": ["#ffd866", "#0a1220"] };
  const contrast = Object.fromEntries(Object.entries(pairs).map(([k, [a, b]]) => [k, Math.round(ratio(a, b) * 100) / 100]));
  console.log(JSON.stringify({ captures: report, contrast }, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
