/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : variants.js
 * Description : Variantes d'icône proposées (coins transparents, simplifiée) et planche de comparaison
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// NODE_PATH=<playwright> node variants.js <référence.png> <dossier icônes actuelles png>   (depuis ce dossier)
"use strict";
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
const SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512];
const b64 = (f) => fs.readFileSync(f).toString("base64");
(async () => {
  const [ref, current] = process.argv.slice(2);
  const browser = await chromium.launch(); const page = await browser.newPage();
  await page.setContent("<html><body></body></html>");
  const out = await page.evaluate(async ({ refData, svgData, sizes }) => {
    const load = async (src) => { const i = new Image(); i.src = src; await i.decode(); return i; };
    const down = (src, s) => {               // halving steps, then the final size
      let c = src;
      while (c.width / 2 >= s) { const n = document.createElement("canvas"); n.width = n.height = Math.floor(c.width / 2);
        const x = n.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, n.width, n.height); c = n; }
      const f = document.createElement("canvas"); f.width = f.height = s;
      const x = f.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, s, s); return f.toDataURL("image/png");
    };
    const rounded = (x, cx, cy, w, h, r) => { x.beginPath(); x.roundRect(cx, cy, w, h, r); x.fill(); };
    // V1: the reference, with a soft rounded mask so corners become transparent and the halo fades out.
    const img = await load(refData);
    const side = 1085, ox = 85, oy = 73;
    const v1 = document.createElement("canvas"); v1.width = v1.height = side;
    const x1 = v1.getContext("2d"); x1.drawImage(img, ox, oy, side, side, 0, 0, side, side);
    const mask = document.createElement("canvas"); mask.width = mask.height = side;
    const m = mask.getContext("2d"); m.filter = "blur(10px)"; m.fillStyle = "#000"; rounded(m, 12, 12, side - 24, side - 24, 250);
    x1.globalCompositeOperation = "destination-in"; x1.drawImage(mask, 0, 0);
    // V2: simplified vector drawing.
    const svg = await load(svgData);
    const v2 = document.createElement("canvas"); v2.width = v2.height = 1024; v2.getContext("2d").drawImage(svg, 0, 0, 1024, 1024);
    const res = { v1: {}, v2: {} };
    for (const s of sizes) { res.v1[s] = down(v1, s); res.v2[s] = down(v2, s); }
    return res;
  }, { refData: "data:image/png;base64," + b64(ref), svgData: "data:image/svg+xml;base64," + b64(path.join(__dirname, "simplifie.svg")), sizes: SIZES });
  for (const [v, set] of Object.entries(out)) for (const [s, url] of Object.entries(set))
    fs.writeFileSync(path.join(__dirname, "png", `${v === "v1" ? "coins-transparents" : "simplifie"}-${s}.png`), Buffer.from(url.split(",")[1], "base64"));
  // Comparison sheet: current derivative (A), transparent corners (B), simplified (C), and the proposed mix.
  const img = (f, s, z = 1) => `<img src="data:image/png;base64,${b64(f)}" width="${s * z}" height="${s * z}" style="image-rendering:${z > 1 ? "pixelated" : "auto"}">`;
  const small = [16, 20, 24, 32, 48];
  const set = (name, pick) => ["#202020", "#f3f3f3", "#0a3d8f"].map((bg) =>
    `<div style="background:${bg};padding:8px 10px;display:flex;gap:16px;align-items:end;font:12px sans-serif;color:${bg === "#f3f3f3" ? "#222" : "#ddd"}"><b style="width:230px">${name}</b>${small.map((s) => `<div style="text-align:center">${img(pick(s), s)}<br>${s}</div>`).join("")}<div>${img(pick(24), 24, 4)}</div></div>`).join("");
  const cur = (s) => path.join(current, `e-${s}.png`);
  const v1 = (s) => path.join(__dirname, "png", `coins-transparents-${s}.png`);
  const v2 = (s) => path.join(__dirname, "png", `simplifie-${s}.png`);
  const mix = (s) => (s <= 24 ? v2(s) : v1(s));
  const html = `<html><body style="margin:0">${set("A · actuelle (fidèle, RGB)", cur)}${set("B · coins transparents", v1)}${set("C · simplifiée", v2)}${set("B+C · proposé : C ≤ 24 px, B au-delà", mix)}</body></html>`;
  const p2 = await browser.newPage({ viewport: { width: 760, height: 400 } });
  await p2.setContent(html); await p2.screenshot({ path: path.join(__dirname, "comparaison.png"), fullPage: true });
  const p3 = await browser.newPage({ viewport: { width: 560, height: 280 } });
  await p3.setContent(`<html><body style="margin:0;display:flex;gap:20px;padding:20px;background:#f3f3f3">${img(cur(256), 256)}${img(v1(256), 256)}</body></html>`);
  await p3.screenshot({ path: path.join(__dirname, "grand-format-A-B.png") });
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
