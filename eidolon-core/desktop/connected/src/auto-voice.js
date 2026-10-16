/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : auto-voice.js
 * Description : Veille vocale sur VM locale, segmentation et envoi conversationnel
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  // Energy gate only: this is not a speech recognizer. Whisper performs recognition on the local VM.
  function createGate() {
    var elapsed = 0, voiced = 0, quiet = 0;
    return { feed: function (samples, rate) {
      var ms = samples.length * 1000 / rate, sum = 0;
      for (var i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
      elapsed += ms;
      if (Math.sqrt(sum / Math.max(1, samples.length)) >= 0.015) { voiced += ms; quiet = 0; }
      else quiet += ms;
      if (voiced >= 250 && quiet >= 1500) return "speech";
      // Long continuous speech is discarded, never silently submitted as a truncated command.
      if (elapsed >= 28000 || (voiced < 250 && elapsed >= 10000)) return "silence";
      return null;
    } };
  }
  function wake(text, calls) {
    var match = /^\s*[«"“]*\s*(eidolon|dis[\s-]+moi|dit[\s-]+moi)(?=$|[\s!?,.:;»"”])/i.exec(text || "");
    if (!match || !(match[1].toLowerCase() === "eidolon" ? calls.eidolon : calls.disMoi)) return null;
    return text.slice(match[0].length).replace(/^[\s!?,.:;»"”]+/, "").trim();
  }
  function create(deps) {
    var generation = 0, running = false;
    var pause = deps.pause || function () { return new Promise(function (resolve) { setTimeout(resolve, 400); }); };
    function change(state, note) { if (deps.change) deps.change(state, note); }
    function stop(note) {
      generation++; running = false; deps.cancel();
      change("off", note || "Vocal automatique arrêté. Micro relâché.");
    }
    async function start() {
      if (running) return;
      var calls = deps.calls();
      if (!calls.eidolon && !calls.disMoi) { change("off", "Choisissez au moins un appel vocal."); return; }
      var mine = ++generation, waiting = false;
      running = true;
      function current() { return running && mine === generation; }
      try {
        change("starting", "Autorisation du micro…");
        await deps.prepare();
        while (current()) {
          change(waiting ? "listening" : "standby", waiting ? "Je vous écoute — envoi après une pause de 1,5 s." : "Veille vocale active — dites « Eidolon » ou « Dis-moi ». Micro ouvert.");
          var result = await deps.listen();
          if (!current()) break;
          if (!result) throw new Error("Capture interrompue ou transcription indisponible. Relancez le vocal.");
          if (result.empty || !result.text || !result.text.trim()) { waiting = false; continue; }
          var text = waiting ? result.text.trim() : wake(result.text, calls);
          if (text === null) continue;
          if (!text) {
            change("speaking", "Eidolon : Oui ? — micro en pause.");
            if (!await deps.speak("Oui ?")) throw new Error("Voix indisponible : vérifiez la sortie audio.");
            if (!current()) break;
            await pause(); waiting = true; continue;
          }
          waiting = false;
          change("sending", "Message envoyé — micro en pause pendant la réponse.");
          var reply = await deps.send(text);
          if (!current()) break;
          if (typeof reply !== "string" || !reply.trim()) throw new Error("Réponse vocale indisponible : consultez la conversation.");
          change("speaking", "Eidolon répond — micro en pause.");
          if (!await deps.speak(reply.slice(0, 2000))) throw new Error("Lecture vocale interrompue ou indisponible.");
          if (!current()) break;
          await pause();
        }
      } catch (error) {
        if (current()) stop(error.message || "Vocal interrompu.");
      }
    }
    return { start: start, stop: stop, active: function () { return running; } };
  }
  var api = { createGate: createGate, wake: wake, create: create };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonAutoVoice = api;
})(typeof window !== "undefined" ? window : this);
