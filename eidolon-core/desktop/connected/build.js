/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : build.js
 * Description : Assemble app.js (seul script servi par http_api) à partir des sources (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// From eidolon-core/:  node desktop/connected/build.js          (writes app.js)
//                      node desktop/connected/build.js --check  (exit 1 if app.js is outdated)
// The pure consumers come unchanged from desktop/prototype/ (tested there); nothing is minified.
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const HERE = __dirname;
const SOURCES = ["../prototype/sync-state.js", "../prototype/mission-list-state.js",
  "src/archives.js", "src/session.js", "src/view.js", "src/media-agents.js", "src/main.js"];
const OUT = path.join(HERE, "app.js");

function bundle() {
  const head = "/* ==========================================================\n"
    + " * Projet      : Eidolon Core\n"
    + " * Organisation: Eidolon Core Technologies (ECT)\n"
    + " * Fichier     : app.js\n"
    + " * Description : FICHIER GÉNÉRÉ par build.js — ne pas modifier à la main (C-TASK-G031)\n"
    + " * Standard    : Eidolon Presentation Standard v1\n"
    + " * ========================================================== */\n";
  return head + SOURCES.map((rel) => "\n/* ---- " + rel + " ---- */\n"
    + fs.readFileSync(path.join(HERE, rel), "utf8")).join("");
}

if (require.main === module) {
  const text = bundle();
  if (process.argv.includes("--check")) {
    const current = fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8") : "";
    if (current !== text) { console.error("app.js is outdated: run node desktop/connected/build.js"); process.exit(1); }
    console.log("app.js up to date");
  } else {
    fs.writeFileSync(OUT, text);
    console.log("wrote " + path.relative(process.cwd(), OUT) + " (" + Buffer.byteLength(text) + " bytes)");
  }
}
module.exports = { bundle, SOURCES };
