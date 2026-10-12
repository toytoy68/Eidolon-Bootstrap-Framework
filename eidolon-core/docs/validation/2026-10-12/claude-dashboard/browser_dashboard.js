/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : browser_dashboard.js
 * Description : Dashboard servi par Core : bloc voix/caméra avec faux micro et fausse caméra de Chromium (C147)
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
      const errors = [], foreign = [], comm = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      page.on("request", (r) => { if (!r.url().startsWith(origin)) foreign.push(r.url()); if (r.url().includes("/v1/comm/")) comm.push(r.method() + " " + new URL(r.url()).pathname); });
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
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      const storage = await page.evaluate(() => [localStorage.length, document.cookie.length]);
      const html = await page.content();
      check(width + " : même origine seulement (CSP inchangée)", foreign.length === 0, foreign.join(","));
      check(width + " : pas de débordement, aucune erreur", overflow === 0 && errors.length === 0, JSON.stringify({ overflow, errors }));
      check(width + " : clé ni stockée ni affichée", storage[0] === 0 && storage[1] === 0 && !html.includes(key), JSON.stringify(storage));
      if (captures) await page.locator("#comm").screenshot({ path: path.join(captures, "dashboard-comm-" + width + ".png") });
      await page.close();
    }
  } catch (e) { out.checks.push({ check: "exécution", ok: false, detail: String(e).slice(0, 300) }); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
