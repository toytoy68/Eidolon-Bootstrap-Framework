/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : manuscrit.js
 * Description : Icône « e manuscrit » : cadre de la référence validée, e tracé à la plume, variante petites tailles
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// NODE_PATH=<playwright> node manuscrit.js <référence.png>     (depuis ce dossier ; écrit png/manuscrit-*.png)
"use strict";
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
const SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512];
// Cursive lowercase e in a 1000×1000 box: crossbar, loop up and around, then a tail to the right.
const E_PATH = "M 300 560 C 430 572, 640 560, 700 470 C 748 392, 690 268, 540 268 C 372 268, 270 400, 280 560"
  + " C 290 730, 410 812, 560 806 C 660 802, 735 760, 800 690";
(async () => {
  const ref = fs.readFileSync(process.argv[2]).toString("base64");
  const browser = await chromium.launch(); const page = await browser.newPage();
  await page.setContent("<html><body></body></html>");
  const out = await page.evaluate(async ({ ref, E_PATH, sizes }) => {
    const load = async (src) => { const i = new Image(); i.src = src; await i.decode(); return i; };
    const svgPath = document.createElementNS("http://www.w3.org/2000/svg", "path"); svgPath.setAttribute("d", E_PATH);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.appendChild(svgPath); document.body.appendChild(svg);
    const length = svgPath.getTotalLength();
    // Broad-nib stroke: an ellipse inclined at -40° stamped densely along the path (thick/thin like a pen).
    const nib = (x, box, scale, nibW, fill, glow) => {
      x.save(); x.translate(box.x, box.y); x.scale(scale, scale);
      if (glow) { x.shadowColor = glow.color; x.shadowBlur = glow.blur; }
      x.fillStyle = fill;
      for (let t = 0; t <= length; t += 1.5) {
        const p = svgPath.getPointAtLength(t);
        const w = nibW * (0.82 + 0.18 * Math.sin(Math.PI * t / length));       // slight pressure variation
        x.beginPath(); x.ellipse(p.x, p.y, w, w * 0.34, -40 * Math.PI / 180, 0, 2 * Math.PI); x.fill();
      }
      x.restore();
    };
    const down = (src, s) => {
      let c = src;
      while (c.width / 2 >= s) { const n = document.createElement("canvas"); n.width = n.height = Math.floor(c.width / 2);
        const x = n.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, n.width, n.height); c = n; }
      const f = document.createElement("canvas"); f.width = f.height = s;
      const x = f.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, s, s); return f.toDataURL("image/png");
    };
    // Large version: reference frame (crop + soft rounded mask, as variant B), interior repainted, e drawn with glow.
    const img = await load("data:image/png;base64," + ref);
    const side = 1085, ox = 85, oy = 73;
    const big = document.createElement("canvas"); big.width = big.height = side;
    const g = big.getContext("2d"); g.drawImage(img, ox, oy, side, side, 0, 0, side, side);
    const cx = 627 - ox, cy = 615 - oy;                      // centre of the rounded square (measured)
    g.save(); g.beginPath(); g.roundRect(cx - 455, cy - 455, 910, 910, 175); g.clip();
    const bg = g.createRadialGradient(cx - 80, cy - 120, 40, cx, cy, 640);
    bg.addColorStop(0, "#07214f"); bg.addColorStop(0.55, "#03102b"); bg.addColorStop(1, "#010617");
    g.fillStyle = bg; g.fillRect(0, 0, side, side);
    g.strokeStyle = "rgba(70,140,255,0.16)"; g.lineWidth = 6; g.beginPath(); g.arc(cx, cy, 360, 0, 2 * Math.PI); g.stroke();
    g.restore();
    const eGrad = g.createLinearGradient(0, 250, 0, 820); eGrad.addColorStop(0, "#9bd4ff"); eGrad.addColorStop(0.45, "#3d9bff"); eGrad.addColorStop(1, "#1f5fff");
    const box = { x: cx - 520, y: cy - 520 }, scale = 1.04;
    nib(g, box, scale, 78, "#2b7cff", { color: "rgba(60,150,255,0.85)", blur: 45 });   // halo
    nib(g, box, scale, 70, eGrad, null);                                               // ink
    nib(g, { x: box.x - 2, y: box.y - 3 }, scale, 13, "rgba(225,245,255,0.30)", null);  // discreet highlight
    const mask = document.createElement("canvas"); mask.width = mask.height = side;
    const m = mask.getContext("2d"); m.filter = "blur(10px)"; m.fillStyle = "#000"; m.beginPath(); m.roundRect(12, 12, side - 24, side - 24, 250); m.fill();
    g.globalCompositeOperation = "destination-in"; g.drawImage(mask, 0, 0);
    // Small version (≤ 24 px): flat navy square, bright border, same e without halo or highlight.
    const small = document.createElement("canvas"); small.width = small.height = 1024;
    const s = small.getContext("2d");
    const sb = s.createLinearGradient(0, 0, 0, 1024); sb.addColorStop(0, "#06163a"); sb.addColorStop(1, "#020a1f");
    s.fillStyle = sb; s.beginPath(); s.roundRect(32, 32, 960, 960, 240); s.fill();
    s.strokeStyle = "#2f8cff"; s.lineWidth = 56; s.stroke();
    nib(s, { x: -10, y: -16 }, 1.04, 96, "#4aa3ff", null);
    const res = { grand: {}, petit: {} };
    for (const z of sizes) { res.grand[z] = down(big, z); res.petit[z] = down(small, z); }
    return res;
  }, { ref, E_PATH, sizes: SIZES });
  for (const [kind, set] of Object.entries(out)) for (const [z, url] of Object.entries(set))
    fs.writeFileSync(path.join(__dirname, "png", `manuscrit-${kind}-${z}.png`), Buffer.from(url.split(",")[1], "base64"));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
