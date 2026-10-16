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
    var upload = doc.getElementById("service-document"), rememberSource = doc.getElementById("service-remember-source");
    var selectedFile = null, canRemember = false;
    var confirm = doc.getElementById("service-confirm"), preview = null, session = null, busy = false;
    var labels = { PREVIEW: "À confirmer", COMMITTED: "Résultat enregistré", UNKNOWN: "Effet incertain — consulter les reçus" };
    function forgetPreview() { preview=null;confirm.hidden=true;discuss.hidden=true;rememberSource.hidden=true; }
    function show(result) {
      preview = result && result.proposal ? result : null;
      var names = { "remember": "Retenir ceci", "web.search": "Recherche Internet", "web.fetch": "Lecture Internet", "file.read": "Lecture de fichier", "document.import": "Document PC", "document.read": "Document autorisé" };
      if (preview) {
        var p = result.proposal, data = p.parameters, r = result.result;
        var shown = data.name || data.text || data.query || data.url || (data.root + "/" + data.path);
        var text = (labels[result.state] || result.state) + "\nProfil : " + p.profile_id + "\n" + names[p.action] + "\n" + shown;
        var extracted = p.action === "document.import" ? data : data.document;
        if (extracted) text += "\nSHA-256 : " + extracted.sha256 + "\n" + extracted.limitations +
          (extracted.truncated ? "\n[EXTRAIT TRONQUÉ À 16 000 CARACTÈRES]" : "") + "\n\n" + extracted.text + "\n\nExtrait non vérifié ; aucune mémorisation automatique.";
        if (r && result.state === "COMMITTED") {
          if (p.action === "remember") text += "\nInformation mémorisée, non vérifiée.";
          else if (r.text && !extracted) text += "\n\n" + r.text;
          else if (Array.isArray(r.results)) text += "\n\n" + r.results.map(function (hit) { return hit.title + "\n" + hit.url + "\n" + hit.snippet; }).join("\n\n");
          if (r.status) text += "\nÉtat de la source : " + r.status;
          if (r.url) text += "\nSource : " + r.url;
        }
        output.textContent = text;
      } else if (result && Array.isArray(result.entries)) {
        output.textContent = result.entries.map(function (e) { return (e.kind === "directory" ? "Dossier : " : "Fichier : ") + e.name; }).join("\n") + (result.truncated ? "\nListe limitée à 100 entrées." : "");
      } else output.textContent = "Aucun résultat exploitable.";
      discuss.hidden = !preview || preview.state !== "COMMITTED" || preview.proposal.action === "remember";
      rememberSource.hidden = !canRemember || !preview || preview.state !== "COMMITTED" || !preview.result || !preview.result.text;
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
        else { forgetPreview(); output.textContent = "Action indisponible (" + result.code + "). Consultez les reçus avant de recommencer."; }
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
    async function receiptPage(before) {
      if (busy) return;
      var mine=session;busy=true;
      var r;
      try { r=await conv.service("action_receipts", before ? {before:before} : {}); }
      finally { busy=false; }
      if(mine!==session)return;
      if (r.stale) return;
      if (!r.ok) { forgetPreview();output.textContent = "Reçus indisponibles (" + r.code + ")."; return; }
      var receipts = r.json.receipts || [];
      output.textContent = ""; confirm.hidden = true; discuss.hidden = true; rememberSource.hidden = true; preview = null;
      receipts.forEach(function (item) {
        var button = doc.createElement("button"); button.type = "button";
        button.textContent = (labels[item.state] || item.state) + " — " + item.proposal.action + " — " + item.proposal.created_at;
        button.addEventListener("click", function () { show(item); });
        output.appendChild(button);
      });
      if (!receipts.length) output.textContent = "Aucun reçu pour ce client.";
      if (r.json.next_before) {
        var older=doc.createElement("button");older.type="button";older.textContent="Reçus plus anciens";
        older.addEventListener("click",function(){receiptPage(r.json.next_before);});output.appendChild(older);
      }
    }
    doc.getElementById("service-receipts").addEventListener("click",function(){receiptPage(null);});
    doc.getElementById("service-files").addEventListener("click", function () {
      call("files", { root: folder.value, path: value.value });
    });
    doc.getElementById("service-use-draft").addEventListener("click", function () {
      value.value = doc.getElementById("conv-text").value; action.value = "remember"; value.focus();
    });
    rememberSource.addEventListener("click", function () {
      if (!preview || !preview.result || !preview.result.text || !canRemember) return;
      var r = preview.result;
      var text = "Source non vérifiée : " + (r.name || r.url || preview.proposal.id) +
        (r.sha256 ? "\nSHA-256 : " + r.sha256 : "") + "\n" + r.text;
      value.value = text.length > 16000 ? text.slice(0, 15900) + "\n[EXTRAIT TRONQUÉ POUR MÉMORISATION]" : text;
      action.value = "remember"; value.focus();
    });
    doc.getElementById("service-upload").addEventListener("change", function (event) {
      var file = event.target.files[0];
      forgetPreview();
      event.target.value = "";
      selectedFile = null; upload.disabled = true;
      if (!file) return;
      if (!file.size || file.size > 512 * 1024) { output.textContent = "Choisissez un document de 512 Kio au maximum."; return; }
      selectedFile = file; upload.disabled = false;
      output.textContent = "Sélection locale : " + file.name + " (" + file.size + " octets). Cliquez sur Envoyer à Core pour extraire le texte. Aucun envoi effectué.";
    });
    upload.addEventListener("click", async function () {
      if (!selectedFile || busy || !session) return;
      var file = selectedFile, epoch = session;
      upload.disabled = true;
      try {
        var bytes = new Uint8Array(await file.arrayBuffer());
        if (epoch !== session) return;
        var binary = "";
        for (var i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
        var key = new Uint8Array(16); root.crypto.getRandomValues(key);
        await call("document_preview", { request_key: Array.from(key, function (b) { return b.toString(16).padStart(2, "0"); }).join(""), name: file.name, data_base64: root.btoa(binary) });
      } catch (_) { if (epoch === session) output.textContent = "Document indisponible ; aucune mémorisation effectuée."; }
      finally { if (epoch === session) { selectedFile = null; upload.disabled = true; } }
    });
    var libraryCursor = null, libraryRoot = null;
    var libraryList = doc.getElementById("service-library-list"), libraryMore = doc.getElementById("service-library-more");
    async function libraryPage(more) {
      var current = session, selectedRoot = folder.value;
      if (!current || busy) return;
      busy = true; forgetPreview();
      try {
        var r = await conv.service("library_page", {root: selectedRoot, after: more && selectedRoot === libraryRoot ? libraryCursor || "" : ""});
        if (r.stale || current !== session) return;
        libraryList.textContent = ""; libraryCursor = null; libraryMore.hidden = true;
        if (!r.ok) { output.textContent = "Bibliothèque indisponible : vérifier le premier passage de synchronisation et le dossier choisi."; return; }
        libraryRoot = selectedRoot; libraryCursor = r.json.next_after; libraryMore.hidden = !libraryCursor;
        output.textContent = "Extraits synchronisés, sans écriture Memory. Dernier passage : " + (r.json.last_scan ? r.json.last_scan.completed_at : "aucun") + ".";
        r.json.entries.forEach(function (entry) {
          var button = doc.createElement("button"); button.type = "button";
          button.textContent = entry.path + (entry.present ? " — préparer la lecture actuelle" : " — absent au dernier passage");
          button.disabled = !entry.present;
          button.addEventListener("click", function () {
            if (current !== session) return;
            folder.value = selectedRoot; value.value = entry.path; action.value = "document.read";
            forgetPreview(); value.focus();
          });
          libraryList.appendChild(button);
        });
      } finally { busy = false; }
    }
    if (doc.getElementById("service-library")) {
      doc.getElementById("service-library").addEventListener("click", function () { libraryPage(false); });
      libraryMore.addEventListener("click", function () { libraryPage(true); });
    }
    var last = 0;
    function active(event) {
      if (!event.isTrusted || panel.hidden || Date.now() - last < 10000) return;
      last = Date.now(); conv.service("activity", {});
    }
    doc.addEventListener("keydown", active); doc.addEventListener("pointerdown", active);
    return { update: function (state) {
      var next = state.phase === "open" && state.services ? state.conversationId : null;
      panel.hidden = !next;
      if (next !== session) { if (libraryList) { libraryList.textContent=""; libraryMore.hidden=true; libraryCursor=libraryRoot=null; } session = next; preview = null; selectedFile = null; canRemember=false; upload.disabled = true; rememberSource.hidden = true; output.textContent = ""; value.value = ""; folder.value = ""; confirm.hidden = true; discuss.hidden = true; doc.getElementById("service-profile").textContent = ""; }
      if (next) {
        canRemember = state.services.remember === true;
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
