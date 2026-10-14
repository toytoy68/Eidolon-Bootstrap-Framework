/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : sim.js
 * Description : Rendu de la simulation G170-E (aucun capteur, aucun réseau)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function () {
  "use strict";
  var S = window.EidolonEnrolmentSim;
  var PROFILES = [{ profile_id: "profil-alpha", display_name: "Alpha (inventé)", confirmed: true },
    { profile_id: "profil-beta", display_name: "Beta (inventé)", confirmed: true },
    { profile_id: "profil-gamma", display_name: "Gamma (inventé)", confirmed: false }];
  var STATUS = { not_enrolled: "non enregistrée", enrolled: "enregistrée" };
  var LABEL = { start: "Commencer la prise", stop: "Arrêter", cancel: "Annuler", confirm: "Confirmer",
    "delete": "Effacer définitivement" };
  var state = S.create(PROFILES);
  function $(id) { return document.getElementById(id); }
  function button(text, onClick, kind) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = text; if (kind) b.className = kind;
    b.addEventListener("click", onClick);
    return b;
  }
  function apply(action) { state = S.act(state, action); render(); }

  function render() {
    var list = $("profiles"); list.textContent = "";
    state.profiles.forEach(function (p) {
      var li = document.createElement("li"), name = document.createElement("strong"), facts = document.createElement("span");
      name.textContent = p.display_name;
      facts.textContent = p.confirmed ? "Voix : " + STATUS[p.voice] + " · Visage : " + STATUS[p.face]
        : "Profil non confirmé : enregistrement impossible";
      li.appendChild(name); li.appendChild(facts); list.appendChild(li);
    });
    var v = S.view(state), controls = $("controls");
    $("flow-title").textContent = v.title;
    $("flow-text").textContent = v.text;
    $("indicator").hidden = !v.indicator;
    $("flow-error").hidden = !v.error;
    $("flow-error").textContent = v.error ? "Action refusée : " + v.error : "";
    controls.textContent = "";
    if (v.step === "idle") {
      state.profiles.filter(function (p) { return p.confirmed; }).forEach(function (p) {
        ["voice", "face"].forEach(function (m) {
          if (p[m] === "enrolled") {
            controls.appendChild(button("Effacer " + S.MODALITIES[m] + " · " + p.display_name,
              function () { apply({ type: "ask_delete", profile_id: p.profile_id, modality: m }); }));
          } else {
            controls.appendChild(button("Enregistrer " + S.MODALITIES[m] + " · " + p.display_name,
              function () { apply({ type: "begin", profile_id: p.profile_id, modality: m }); }));
          }
        });
      });
    } else if (v.step === "consent") {
      controls.appendChild(button("La personne est présente et d'accord",
        function () { apply({ type: "consent", present: true, agree: true }); }, "primary"));
      controls.appendChild(button(LABEL.cancel, function () { apply({ type: "cancel" }); }));
    } else if (v.step === "capturing") {
      var voice = state.flow.modality === "voice";
      controls.appendChild(button("Prise réussie (simulée)", function () {
        apply({ type: "finish", sample: voice ? { duration_s: 6, quality: "ok" } : { quality: "ok" } }); }, "primary"));
      controls.appendChild(button(voice ? "Prise trop courte (simulée)" : "Aucun visage (simulé)", function () {
        apply({ type: "finish", sample: voice ? { duration_s: 2 } : { quality: "no_face" } }); }));
      controls.appendChild(button(LABEL.stop, function () { apply({ type: "stop" }); }, "stop"));
    } else {
      v.actions.forEach(function (a) {
        controls.appendChild(button(LABEL[a] || a, function () { apply({ type: a }); },
          a === "cancel" ? "" : a === "delete" ? "stop" : "primary"));
      });
    }
  }

  var select = $("proposal-state");
  ["known", "ambiguous", "uncalibrated", "stale", "unavailable", "unknown"].forEach(function (s) {
    var o = document.createElement("option"); o.value = s; o.textContent = s; select.appendChild(o);
  });
  function suggest() {
    var proposal = { schema: "eidolon-identity-proposal/1", modality: "voice", state: select.value,
      profile_id: select.value === "known" ? "profil-alpha" : null, grants: [], authorizes_execution: false };
    $("suggestion").textContent = S.proposalView(proposal, state.profiles).text;
  }
  select.addEventListener("change", suggest);
  render(); suggest();
})();
