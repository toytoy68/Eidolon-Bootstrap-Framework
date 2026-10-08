/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : make_logo.js
 * Description : Dérive le logo d'en-tête du client connecté depuis le logo officiel (C-TASK-G078)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:
//   NODE_PATH=<playwright> node docs/validation/2026-10-08/claude-g078/make_logo.js
// Reads assets/branding/eidolon-logo.png (never modified), keeps its own pixels: a crop to
// the visible drawing (dark margin removed) and a high-quality reduction. No redrawing.
"use strict";
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const CORE = path.resolve(__dirname, "..", "..", "..", "..");
const SOURCE = path.join(CORE, "assets", "branding", "eidolon-logo.png");
const OUT = path.join(CORE, "desktop", "connected", "eidolon-logo.png");
const HEIGHT = 112;          // 2 x the 56 px header height (HiDPI)
const THRESHOLD = 60;        // brightest channel above this counts as drawing
const MARGIN = 24;           // source pixels kept around the drawing (glow)

(async () => {
  const src = fs.readFileSync(SOURCE);
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setContent("<html><body></body></html>");
    const out = await page.evaluate(async ({ data, height, threshold, margin }) => {
      const img = new Image(); img.src = data; await img.decode();
      const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
      const x = c.getContext("2d"); x.drawImage(img, 0, 0);
      const px = x.getImageData(0, 0, c.width, c.height).data;
      let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
      for (let y = 0; y < c.height; y++) for (let i = 0; i < c.width; i++) {
        const o = (y * c.width + i) * 4;
        if (Math.max(px[o], px[o + 1], px[o + 2]) > threshold) {
          if (i < x0) x0 = i; if (i > x1) x1 = i; if (y < y0) y0 = y; if (y > y1) y1 = y;
        }
      }
      x0 = Math.max(0, x0 - margin); y0 = Math.max(0, y0 - margin);
      x1 = Math.min(c.width - 1, x1 + margin); y1 = Math.min(c.height - 1, y1 + margin);
      const w = x1 - x0 + 1, h = y1 - y0 + 1;
      // Halving steps then one final step: avoids the aliasing of a single large reduction.
      let cur = document.createElement("canvas"); cur.width = w; cur.height = h;
      cur.getContext("2d").drawImage(c, x0, y0, w, h, 0, 0, w, h);
      while (cur.height / 2 >= height) {
        const n = document.createElement("canvas"); n.width = Math.round(cur.width / 2); n.height = Math.round(cur.height / 2);
        const nx = n.getContext("2d"); nx.imageSmoothingQuality = "high"; nx.drawImage(cur, 0, 0, n.width, n.height); cur = n;
      }
      const f = document.createElement("canvas"); f.height = height; f.width = Math.round(w * height / h);
      const fx = f.getContext("2d"); fx.imageSmoothingQuality = "high"; fx.drawImage(cur, 0, 0, f.width, f.height);
      return { crop: [x0, y0, w, h], size: [f.width, f.height], png: f.toDataURL("image/png") };
    }, { data: "data:image/png;base64," + src.toString("base64"), height: HEIGHT, threshold: THRESHOLD, margin: MARGIN });
    const png = Buffer.from(out.png.split(",")[1], "base64");
    fs.writeFileSync(OUT, png);
    const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");
    console.log(JSON.stringify({ source: path.relative(CORE, SOURCE), source_sha256: sha(src),
      crop_xywh: out.crop, output: path.relative(CORE, OUT), size: out.size, bytes: png.length, output_sha256: sha(png) }, null, 1));
  } finally { await browser.close(); }
})().catch((err) => { console.error(err); process.exit(1); });
