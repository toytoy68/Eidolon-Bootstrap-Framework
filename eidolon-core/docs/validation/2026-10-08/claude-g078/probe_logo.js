/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : probe_logo.js
 * Description : Logo officiel du client connecté sur serveur réel : 360/1280, clair/sombre, repli sans logo (C-TASK-G078)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:
//   NODE_PATH=<playwright> node docs/validation/2026-10-08/claude-g078/probe_logo.js <patched src> [captures dir]
// "actuel" = the server of this checkout (does not serve the logo); "propose" = <patched src>, the same
// sources plus http_api-logo.patch. C-009g fixture, loopback only, temporary folders cleaned.
"use strict";
const path = require("node:path");
const { spawn } = require("node:child_process");
const { WEB_ROOT, chromium, makeFixture, startServer, cleanup } = require("../../../../desktop/connected/tests/helpers.js");

const PATCHED = path.resolve(process.argv[2]);
const CAPTURES = process.argv[3] ? path.resolve(process.argv[3]) : null;
const withSrc = (src) => (cmd, args, opts) => spawn(cmd, args, Object.assign({}, opts, { env: Object.assign({}, opts.env, { PYTHONPATH: src }) }));

async function look(page) {
  return page.evaluate(() => {
    const logo = document.getElementById("brand-logo"), name = document.getElementById("brand-name");
    const h1 = document.querySelector("h1"), top = document.querySelector(".top").getBoundingClientRect();
    const r = logo.getBoundingClientRect();
    const shown = !logo.hidden && r.width > 0;
    return {
      logo: shown ? `affiché ${Math.round(r.width)}×${Math.round(r.height)} px` : "non affiché",
      nom_h1: shown ? logo.alt : name.textContent,
      texte_visible: name.hidden ? "masqué" : "visible",
      image_cassée: [...document.images].filter((i) => !i.hidden && i.complete && i.naturalWidth === 0).length,
      dans_en_tete: !shown || (r.left >= top.left && r.right <= top.right),
      débordement_px: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}

(async () => {
  const fx = makeFixture();
  const servers = [];
  let browser;
  const results = [];
  try {
    servers.push(Object.assign(await startServer(fx, WEB_ROOT), { label: "actuel" }));
    servers.push(Object.assign(await startServer(fx, WEB_ROOT, { spawnServer: withSrc(PATCHED) }), { label: "propose" }));
    browser = await chromium.launch();
    for (const server of servers) {
      for (const [w, h] of [[360, 740], [1280, 720]]) {
        for (const scheme of ["light", "dark"]) {
          const context = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, deviceScaleFactor: 2 });
          const page = await context.newPage();
          const errors = [], failed = [];
          page.on("pageerror", (e) => errors.push(String(e)));
          page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
          page.on("requestfailed", (r) => failed.push(r.url()));
          page.on("response", (r) => { if (r.status() >= 400) failed.push(new URL(r.url()).pathname + " " + r.status()); });
          await page.goto(server.base + "/");
          await page.waitForLoadState("networkidle");
          const before = await look(page);
          await page.fill("#token", fx.token);
          await page.click("#connect");
          await page.waitForSelector(".mission-button");
          const after = await look(page);
          const label = `${server.label}-${w}x${h}-${scheme}`;
          // Connecting moves focus (and scroll) to the mission list: capture the header from the top.
          await page.evaluate(() => window.scrollTo(0, 0));
          if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, label + ".png") });
          results.push({ cas: label, avant_connexion: before, connecté: after, réponses_en_erreur: failed, erreurs_console: errors });
          await context.close();
        }
      }
    }
  } finally { await cleanup({ browser, servers, dirs: [fx.dir] }); }
  console.log(JSON.stringify(results, null, 1));
})().catch((err) => { console.error(err); process.exit(1); });
