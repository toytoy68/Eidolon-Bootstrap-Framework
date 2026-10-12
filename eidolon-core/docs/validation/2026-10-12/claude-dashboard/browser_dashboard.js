/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : browser_dashboard.js
 * Description : Dashboard servi par Core : voix/caméra (faux périphériques Chromium) et état des machines (C147, G158)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// node browser_dashboard.js <page url> <conversation key> [captures dir]   (NODE_PATH -> playwright)
"use strict";
const { chromium } = require("playwright");
const path = require("node:path");

(async () => {
  const [url, key, captures] = process.argv.slice(2);
  const origin = new URL(url).origin;
  const out = { checks: [] };
  const check = (name, ok, detail) => out.checks.push({ check: name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 200) });
  const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
    ...(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: "/opt/pw-browsers/chromium" }) });
  try {
    for (const width of [1280, 360]) {
      const page = await browser.newPage({ viewport: { width, height: width === 360 ? 760 : 800 } });
      const errors = [], foreign = [], comm = [], monitor = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      page.on("request", (r) => { if (!r.url().startsWith(origin)) foreign.push(r.url()); if (r.url().includes("/v1/comm/")) comm.push(r.method() + " " + new URL(r.url()).pathname);
        if (r.url().includes("/v1/monitor/")) monitor.push(r.method()); });
      await page.goto(url);
      await page.fill("#conv-key", key); await page.press("#conv-key", "Enter");
      await page.waitForSelector("#conv-body:not([hidden])");
      await page.waitForFunction(() => document.getElementById("comm-mic-state").textContent.length > 0);
      const initial = await page.evaluate(() => ["mic", "speaker", "camera"].map((k) => [document.getElementById("comm-" + k + "-on").checked, document.getElementById("comm-" + k + "-state").textContent]));
      check(width + " : tout éteint par défaut", initial.every(([on]) => !on) && /désactivé/.test(initial[0][1]), JSON.stringify(initial));
      check(width + " : aucune requête voix avant activation", comm.length === 0, comm.join(","));
      // Microphone: permission, push to talk, transcript placed in the field, NOT sent.
      await page.check("#comm-mic-on");
      await page.waitForFunction(() => /prêt/.test(document.getElementById("comm-mic-state").textContent));
      await page.click("#comm-talk");
      await page.waitForFunction(() => document.getElementById("comm-mic-state").classList.contains("recording"));
      const recording = await page.textContent("#comm-mic-state");
      await page.waitForTimeout(1200);
      await page.click("#comm-talk");
      await page.waitForFunction(() => document.getElementById("conv-text").value.length > 0, null, { timeout: 15000 });
      const typed = await page.inputValue("#conv-text");
      const turns = await page.locator("#conv-log li").count();
      check(width + " : voyant rouge pendant la capture seulement", /capture en cours/.test(recording)
        && !(await page.evaluate(() => document.getElementById("comm-mic-state").classList.contains("recording"))), recording);
      check(width + " : transcription dans le champ, non envoyée", /parole simulée/.test(typed) && turns === 0, typed);
      // Voice: switched on, then a sent message's reply is read aloud through Web Audio.
      await page.check("#comm-speaker-on");
      await page.fill("#conv-text", "Diagnostique le nas.");
      await page.click("#conv-send");
      await page.waitForFunction(() => document.querySelectorAll("#conv-log .conv-reply").length === 1, null, { timeout: 15000 });
      await page.waitForFunction(() => /prêt/.test(document.getElementById("comm-speaker-state").textContent), null, { timeout: 20000 });
      check(width + " : réponse lue à voix haute (synthèse demandée)", comm.some((c) => c === "POST /v1/comm/tts"), comm.join(","));
      // Camera: one frame, presence, no identity, camera released.
      await page.check("#comm-camera-on");
      await page.waitForFunction(() => /prêt/.test(document.getElementById("comm-camera-state").textContent));
      await page.click("#comm-presence");
      await page.waitForFunction(() => /visible/.test(document.getElementById("comm-note").textContent), null, { timeout: 15000 });
      const note = await page.textContent("#comm-note");
      const live = await page.evaluate(() => /capture/.test(document.getElementById("comm-camera-state").textContent));
      check(width + " : présence décrite, observation non vérifiée, caméra relâchée", /non vérifiée/.test(note) && !live, note);
      // G156/G158: machine dashboard — visible once the key is open, nothing read before the click.
      check(width + " : état des machines visible, aucune lecture avant demande",
        (await page.isVisible("#monitor")) && monitor.length === 0 && !(await page.isChecked("#monitor-auto")), monitor.join(","));
      await page.click("#monitor-refresh");
      await page.waitForFunction(() => document.querySelectorAll("#monitor-machines .monitor-card").length === 3, null, { timeout: 15000 });
      const cards = await page.$$eval("#monitor-machines .monitor-card", (els) => els.map((e) => e.textContent));
      check(width + " : Core gris, jamais présenté comme sécurisé, périmètre et fraîcheur visibles",
        /Gris/.test(cards[0]) && /PAS un état sécurisé/.test(cards[0]) && /Périmètre/.test(cards[0]) && /il y a \d+ s/.test(cards[0])
        , cards[0]);
      check(width + " : mesures eidolon-machine/1 du vrai collecteur (CPU, charge, mémoire, swap, disque), GPU non sondé",
        /Mesures il y a \d+ s/.test(cards[0]) && /Mémoire.*utilisés sur/.test(cards[0]) && /Disque du journal/.test(cards[0])
        && /GPUnon sondé/.test(cards[0]), cards[0].slice(-220));
      check(width + " : Memory indisponible et GPU non surveillé, aucune mesure inventée",
        /Indisponible/.test(cards[1]) && /Non surveillé/.test(cards[2]) && !/Gio|%/.test(cards[1] + cards[2]), cards.slice(1).join(" | "));
      await page.waitForTimeout(1500);
      check(width + " : une seule lecture sans actualisation automatique", monitor.length === 1, monitor.join(","));
      if (captures) await page.locator("#monitor").screenshot({ path: path.join(captures, "dashboard-monitor-" + width + ".png") });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      const storage = await page.evaluate(() => [localStorage.length, document.cookie.length]);
      const html = await page.content();
      check(width + " : même origine seulement (CSP inchangée)", foreign.length === 0, foreign.join(","));
      check(width + " : pas de débordement, aucune erreur", overflow === 0 && errors.length === 0, JSON.stringify({ overflow, errors }));
      check(width + " : clé ni stockée ni affichée", storage[0] === 0 && storage[1] === 0 && !html.includes(key), JSON.stringify(storage));
      if (captures) await page.locator("#comm").screenshot({ path: path.join(captures, "dashboard-comm-" + width + ".png") });
      await page.click("#conv-close");
      await page.waitForSelector("#monitor", { state: "hidden" });
      check(width + " : fermeture de la conversation : tableau masqué et vidé",
        (await page.locator("#monitor-machines li").count()) === 0, "");
      await page.close();
    }
    // G165: Windows display scaling (CSS pixels = screen / scale) and keyboard only.
    for (const [label, width, height, scale] of [["1366x768 à 125 %", 1093, 614, 1.25], ["1366x768 à 150 %", 911, 512, 1.5],
                                                 ["1920x1080 à 150 %", 1280, 720, 1.5]]) {
      const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(url);
      await page.fill("#conv-key", key); await page.press("#conv-key", "Enter");
      await page.waitForSelector("#conv-body:not([hidden])");
      await page.waitForFunction(() => document.getElementById("comm-mic-state").textContent.length > 0);
      // Keyboard only: Tab to the microphone switch, Space to enable, Tab to "Parler", Enter twice.
      let reached = false;
      for (let i = 0; i < 40 && !reached; i++) { await page.keyboard.press("Tab"); reached = await page.evaluate(() => document.activeElement.id === "comm-mic-on"); }
      await page.keyboard.press("Space");
      await page.waitForFunction(() => /prêt/.test(document.getElementById("comm-mic-state").textContent));
      let talk = false;
      for (let i = 0; i < 12 && !talk; i++) { await page.keyboard.press("Tab"); talk = await page.evaluate(() => document.activeElement.id === "comm-talk"); }
      const outline = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
      await page.keyboard.press("Enter");
      await page.waitForFunction(() => document.getElementById("comm-mic-state").classList.contains("recording"));
      await page.waitForTimeout(800);
      await page.keyboard.press("Enter");
      await page.waitForFunction(() => document.getElementById("conv-text").value.length > 0, null, { timeout: 15000 });
      check(label + " : micro activé, parler et terminer au clavier seul, focus visible", reached && talk && outline !== "none", outline);
      await page.click("#monitor-refresh");
      await page.waitForFunction(() => document.querySelectorAll("#monitor-machines .monitor-card").length === 3, null, { timeout: 15000 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      check(label + " : aucun débordement horizontal, aucune erreur", overflow === 0 && errors.length === 0, JSON.stringify({ overflow, errors }));
      if (captures && scale === 1.5 && width === 911) await page.locator("#comm").screenshot({ path: path.join(captures, "dashboard-comm-911-150.png") });
      await context.close();
    }
  } catch (e) { out.checks.push({ check: "exécution", ok: false, detail: String(e).slice(0, 300) }); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
