// Downscale the approved reference in steps (halving) with high-quality smoothing; RGBA PNG out.
const fs = require("node:fs"); const path = require("node:path");
const { chromium } = require("playwright");
(async () => {
  const [src, out, crop] = [process.argv[2], process.argv[3], Number(process.argv[4])];
  const data = "data:image/png;base64," + fs.readFileSync(src).toString("base64");
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent("<html><body></body></html>");
  const sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512];
  const pngs = await p.evaluate(async ({ data, sizes, crop }) => {
    const img = new Image(); img.src = data; await img.decode();
    const side = img.width - 2 * crop;
    const result = {};
    for (const s of sizes) {
      let c = document.createElement("canvas"); c.width = c.height = side;
      c.getContext("2d").drawImage(img, crop, crop, side, side, 0, 0, side, side);
      while (c.width / 2 >= s) {           // halve until close to the target, then final step
        const n = document.createElement("canvas"); n.width = n.height = Math.floor(c.width / 2);
        const x = n.getContext("2d"); x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
        x.drawImage(c, 0, 0, n.width, n.height); c = n;
      }
      const f = document.createElement("canvas"); f.width = f.height = s;
      const x = f.getContext("2d"); x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
      x.drawImage(c, 0, 0, s, s);
      result[s] = f.toDataURL("image/png");
    }
    return result;
  }, { data, sizes, crop });
  for (const [s, url] of Object.entries(pngs)) fs.writeFileSync(path.join(out, `e-${s}.png`), Buffer.from(url.split(",")[1], "base64"));
  await b.close();
})();
