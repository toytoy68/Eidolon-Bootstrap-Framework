const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
(async () => {
  const dir = process.argv[2], out = process.argv[3];
  const sizes = [16, 20, 24, 32, 40, 48, 64];
  const img = (s, scale) => `<img src="data:image/png;base64,${fs.readFileSync(path.join(dir, `e-${s}.png`)).toString("base64")}" width="${s * scale}" height="${s * scale}" style="image-rendering:pixelated">`;
  const row = (bg, label) => `<div style="background:${bg};padding:10px;display:flex;gap:18px;align-items:end;font:12px sans-serif;color:${bg === "#f3f3f3" ? "#222" : "#ddd"}"><b style="width:150px">${label}</b>${sizes.map((s) => `<div style="text-align:center">${img(s, 1)}<br>${s}</div>`).join("")}</div>`;
  const zoom = `<div style="background:#202020;padding:10px;display:flex;gap:18px;align-items:end;font:12px sans-serif;color:#ddd"><b style="width:150px">×4 (pixels réels)</b>${[16, 24, 32, 48].map((s) => `<div style="text-align:center">${img(s, 4)}<br>${s}</div>`).join("")}</div>`;
  const html = `<html><body style="margin:0">${row("#202020", "Barre des tâches sombre")}${row("#f3f3f3", "Barre des tâches claire")}${row("#0a3d8f", "Fond bleu (bureau)")}${zoom}</body></html>`;
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 900, height: 400 } });
  await p.setContent(html); await p.screenshot({ path: out, fullPage: true }); await b.close();
})();
