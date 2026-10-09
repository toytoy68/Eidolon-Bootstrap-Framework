/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : logo_e.js
 * Description : Icône avec le « e » du logo programme validé, dans le cadre de l'icône de référence
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// NODE_PATH=<playwright> node logo_e.js <eidolon-icon-reference.png> <eidolon-logo.png>   (écrit png/logo-e-*.png)
"use strict";
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
const SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512];
(async () => {
  const [refFile, logoFile] = process.argv.slice(2);
  const b64 = (f) => "data:image/png;base64," + fs.readFileSync(f).toString("base64");
  const browser = await chromium.launch(); const page = await browser.newPage();
  await page.setContent("<html><body></body></html>");
  const out = await page.evaluate(async ({ ref, logo, sizes }) => {
    const load = async (src) => { const i = new Image(); i.src = src; await i.decode(); return i; };
    const down = (src, s) => {
      let c = src;
      while (c.width / 2 >= s) { const n = document.createElement("canvas"); n.width = n.height = Math.floor(c.width / 2);
        const x = n.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, n.width, n.height); c = n; }
      const f = document.createElement("canvas"); f.width = f.height = s;
      const x = f.getContext("2d"); x.imageSmoothingQuality = "high"; x.drawImage(c, 0, 0, s, s); return f.toDataURL("image/png");
    };
    // The e of the validated logo (unchanged pixels), cut before « IDOLON » with feathered edges.
    const L = await load(logo);
    const crop = (x0, y0, w, h, fadeRight) => {
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const g = c.getContext("2d"); g.drawImage(L, x0, y0, w, h, 0, 0, w, h);
      const m = document.createElement("canvas"); m.width = w; m.height = h;
      const k = m.getContext("2d");
      const hg = k.createLinearGradient(0, 0, w, 0); hg.addColorStop(0, "rgba(0,0,0,0)"); hg.addColorStop(0.04, "#000");
      hg.addColorStop(1 - fadeRight, "#000"); hg.addColorStop(1, "rgba(0,0,0,0)");
      k.fillStyle = hg; k.fillRect(0, 0, w, h);
      const vg = k.createLinearGradient(0, 0, 0, h); vg.addColorStop(0, "#000"); vg.addColorStop(0.06, "rgba(0,0,0,0)");
      vg.addColorStop(0.94, "rgba(0,0,0,0)"); vg.addColorStop(1, "#000");
      k.globalCompositeOperation = "destination-out"; k.fillStyle = vg; k.fillRect(0, 0, w, h);
      g.globalCompositeOperation = "destination-in"; g.drawImage(m, 0, 0);
      return c;
    };
    const eWide = crop(40, 300, 530, 360, 0.16);   // with the start of the orbit
    const eTight = crop(110, 315, 455, 335, 0.08); // letter only, for small sizes
    // Large: frame of the icon reference (crop + soft rounded mask), interior repainted, logo e composited (screen).
    const R = await load(ref);
    const side = 1085, ox = 85, oy = 73, cx = 627 - ox, cy = 615 - oy;
    const big = document.createElement("canvas"); big.width = big.height = side;
    const g = big.getContext("2d"); g.drawImage(R, ox, oy, side, side, 0, 0, side, side);
    g.save(); g.beginPath(); g.roundRect(cx - 455, cy - 455, 910, 910, 175); g.clip();
    const bg = g.createRadialGradient(cx - 80, cy - 120, 40, cx, cy, 640);
    bg.addColorStop(0, "#07214f"); bg.addColorStop(0.55, "#03102b"); bg.addColorStop(1, "#010617");
    g.fillStyle = bg; g.fillRect(0, 0, side, side);
    g.globalCompositeOperation = "screen";
    const w = 880, h = w * eWide.height / eWide.width;
    g.drawImage(eWide, cx - w / 2 - 10, cy - h / 2, w, h);
    g.restore();
    const mask = document.createElement("canvas"); mask.width = mask.height = side;
    const m = mask.getContext("2d"); m.filter = "blur(10px)"; m.fillStyle = "#000"; m.beginPath(); m.roundRect(12, 12, side - 24, side - 24, 250); m.fill();
    g.globalCompositeOperation = "destination-in"; g.drawImage(mask, 0, 0);
    // Small (≤ 24 px): flat navy square, bright border, the logo e enlarged without the orbit tail.
    const small = document.createElement("canvas"); small.width = small.height = 1024;
    const s = small.getContext("2d");
    const sb = s.createLinearGradient(0, 0, 0, 1024); sb.addColorStop(0, "#06163a"); sb.addColorStop(1, "#020a1f");
    s.fillStyle = sb; s.beginPath(); s.roundRect(32, 32, 960, 960, 240); s.fill();
    s.strokeStyle = "#2f8cff"; s.lineWidth = 56; s.stroke();
    s.save(); s.clip(); s.globalCompositeOperation = "screen"; s.filter = "brightness(1.35) contrast(1.25)";
    const sw = 800, sh = sw * eTight.height / eTight.width;
    s.drawImage(eTight, 512 - sw / 2 - 10, 512 - sh / 2 + 10, sw, sh); s.restore();
    const res = { grand: {}, petit: {} };
    for (const z of sizes) { res.grand[z] = down(big, z); res.petit[z] = down(small, z); }
    return res;
  }, { ref: b64(refFile), logo: b64(logoFile), sizes: SIZES });
  for (const [kind, set] of Object.entries(out)) for (const [z, url] of Object.entries(set))
    fs.writeFileSync(path.join(__dirname, "png", `logo-e-${kind}-${z}.png`), Buffer.from(url.split(",")[1], "base64"));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
