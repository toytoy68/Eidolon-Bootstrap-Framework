/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : profile-services.js
 * Description : Explicit remembering, Internet and file actions with durable receipts
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  function parameters(action, value, folder) {
    if (action === "remember") return { text: value };
    if (action === "web.search") return { query: value };
    if (action === "web.fetch") return { url: value };
    return { root: folder, path: value };
  }
  function mount(doc, conv) {
    var panel = doc.getElementById("profile-services");
    if (!panel) return null;
    var value = doc.getElementById("service-value"), action = doc.getElementById("service-action");
    var folder = doc.getElementById("service-root"), output = doc.getElementById("service-output");
    var discuss = doc.getElementById("service-discuss");
    var confirm = doc.getElementById("service-confirm"), preview = null, session = null, busy = false;
    var labels = { PREVIEW: "À confirmer", COMMITTED: "Résultat enregistré", UNKNOWN: "Effet incertain — consulter les reçus" };
    function show(result) {
      preview = result && result.proposal ? result : null;
      var names = { "remember": "Retenir ceci", "web.search": "Recherche Internet", "web.fetch": "Lecture Internet", "file.read": "Lecture de fichier" };
      if (preview) {
        var p = result.proposal, data = p.parameters, r = result.result;
        var shown = data.text || data.query || data.url || (data.root + "/" + data.path);
        var text = (labels[result.state] || result.state) + "\nProfil : " + p.profile_id + "\n" + names[p.action] + "\n" + shown;
        if (r && result.state === "COMMITTED") {
          if (p.action === "remember") text += "\nInformation mémorisée, non vérifiée.";
          else if (r.text) text += "\n\n" + r.text;
          else if (Array.isArray(r.results)) text += "\n\n" + r.results.map(function (hit) { return hit.title + "\n" + hit.url + "\n" + hit.snippet; }).join("\n\n");
          if (r.status) text += "\nÉtat de la source : " + r.status;
          if (r.url) text += "\nSource : " + r.url;
        }
        output.textContent = text;
      } else if (result && Array.isArray(result.entries)) {
        output.textContent = result.entries.map(function (e) { return (e.kind === "directory" ? "Dossier : " : "Fichier : ") + e.name; }).join("\n") + (result.truncated ? "\nListe limitée à 100 entrées." : "");
      } else output.textContent = "Aucun résultat exploitable.";
      discuss.hidden = !preview || preview.state !== "COMMITTED" || preview.proposal.action === "remember";
      confirm.hidden = !preview || !(preview.state === "PREVIEW" ||
        preview.state === "UNKNOWN" && preview.proposal.action === "remember");
      confirm.textContent = preview && preview.state === "UNKNOWN" ? "Reprendre la même mémorisation" : "Confirmer cette action";
    }
    async function call(route, body) {
      if (busy) return;
      busy = true; confirm.disabled = true;
      try {
        var result = await conv.service(route, body);
        if (result.stale) return;
        if (result.ok) show(result.json);
        else { output.textContent = "Action indisponible (" + result.code + "). Consultez les reçus avant de recommencer."; confirm.hidden = true; }
      } finally { busy = false; confirm.disabled = false; }
    }
    doc.getElementById("service-preview").addEventListener("click", function () {
      if (busy) return;
      var bytes = new Uint8Array(16); root.crypto.getRandomValues(bytes);
      var key = Array.from(bytes, function (b) { return b.toString(16).padStart(2, "0"); }).join("");
      call("action_preview", { request_key: key, action: action.value,
        parameters: parameters(action.value, value.value, folder.value) });
    });
    confirm.addEventListener("click", function () {
      if (preview) call("action_commit", { id: preview.proposal.id, sha256: preview.sha256 });
    });
    discuss.addEventListener("click", async function () {
      if (!preview || busy) return;
      var input = doc.getElementById("conv-text");
      var question = input.value.trim() || "Résume ce résultat en français en précisant les sources et les incertitudes.";
      if (await conv.send(question, null, preview.proposal.id)) input.value = "";
    });
    doc.getElementById("service-receipts").addEventListener("click", async function () {
      if (busy) return;
      var r = await conv.service("action_receipts", {});
      if (r.stale) return;
      if (!r.ok) { output.textContent = "Reçus indisponibles (" + r.code + ")."; return; }
      var receipts = r.json.receipts || [];
      output.textContent = ""; confirm.hidden = true; discuss.hidden = true; preview = null;
      receipts.forEach(function (item) {
        var button = doc.createElement("button"); button.type = "button";
        button.textContent = (labels[item.state] || item.state) + " — " + item.proposal.action + " — " + item.proposal.created_at;
        button.addEventListener("click", function () { show(item); });
        output.appendChild(button);
      });
      if (!receipts.length) output.textContent = "Aucun reçu pour ce client.";
    });
    doc.getElementById("service-files").addEventListener("click", function () {
      call("files", { root: folder.value, path: value.value });
    });
    doc.getElementById("service-use-draft").addEventListener("click", function () {
      value.value = doc.getElementById("conv-text").value; action.value = "remember"; value.focus();
    });
    doc.getElementById("service-upload").addEventListener("change", async function (event) {
      var file = event.target.files[0], epoch = session;
      event.target.value = "";
      if (!file) return;
      if (file.size > 16000) { output.textContent = "Choisissez un fichier texte UTF-8 de 16 000 octets au maximum."; return; }
      try {
        var text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
        if (epoch !== session) return;
        if (text.indexOf("\0") >= 0) throw new Error("binary");
        value.value = text; action.value = "remember";
        output.textContent = "Fichier ouvert sur le PC. Relisez le texte puis préparez sa mémorisation.";
      } catch (_) { output.textContent = "Fichier texte UTF-8 requis."; }
    });
    var last = 0;
    function active(event) {
      if (!event.isTrusted || panel.hidden || Date.now() - last < 10000) return;
      last = Date.now(); conv.service("activity", {});
    }
    doc.addEventListener("keydown", active); doc.addEventListener("pointerdown", active);
    return { update: function (state) {
      var next = state.phase === "open" && state.services ? state.conversationId : null;
      panel.hidden = !next;
      if (next !== session) { session = next; preview = null; output.textContent = ""; value.value = ""; folder.value = ""; confirm.hidden = true; discuss.hidden = true; doc.getElementById("service-profile").textContent = ""; }
      if (next) {
        Array.from(action.options).forEach(function (option) {
          option.disabled = option.value === "remember" ? !state.services.remember :
            option.value.indexOf("web.") === 0 ? !state.services.web : !state.services.file_roots.length;
        });
        if (action.selectedOptions[0] && action.selectedOptions[0].disabled) {
          var available = Array.from(action.options).filter(function (option) { return !option.disabled; });
          if (available.length) action.value = available[0].value;
        }
        doc.getElementById("service-profile").textContent = "Profil : " + state.services.profile_id +
          " · Internet : " + (state.services.web ? "autorisé, " + state.services.daily_web_limit + " appels/jour" : "désactivé") +
          " · Dossiers : " + (state.services.file_roots.join(", ") || "aucun");
      }
    } };
  }
  var api = { mount: mount, parameters: parameters };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonProfileServices = api;
})(typeof window !== "undefined" ? window : this);
