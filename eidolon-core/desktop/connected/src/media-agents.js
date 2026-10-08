/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : media-agents.js
 * Description : Espaces Image/Vidéo et brouillons locaux, sans transport
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  var TYPES = { "image/png": ".png", "image/jpeg": ".jpg,.jpeg", "image/webp": ".webp",
    "video/mp4": ".mp4", "video/webm": ".webm" };
  function allowed(agent, mode) {
    return Object.keys(TYPES).filter(function (t) {
      return agent === "image" ? t.indexOf("image/") === 0 :
        mode === "create" || t.indexOf("video/") === 0;
    });
  }
  function prepareDraft(agent, mode, prompt, file, format, duration) {
    if (["image", "video"].indexOf(agent) < 0 || ["create", "edit", "analyze"].indexOf(mode) < 0)
      throw new Error("Choisissez un agent et une opération valides.");
    if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 4000)
      throw new Error("Décrivez votre demande (1 à 4 000 caractères).");
    if (mode !== "create" && !file) throw new Error("Choisissez le fichier à modifier ou à analyser.");
    var source = null;
    if (file) {
      if (allowed(agent, mode).indexOf(file.type) < 0)
        throw new Error("Ce format de fichier n’est pas accepté pour cette opération.");
      var limit = file.type.indexOf("image/") === 0 ? 20 * 1024 * 1024 : 200 * 1024 * 1024;
      if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > limit)
        throw new Error("Fichier vide ou trop volumineux (image : 20 Mio ; vidéo : 200 Mio).");
      if (typeof file.name !== "string" || !file.name || file.name.length > 255 || /[\x00-\x1f\x7f]/.test(file.name))
        throw new Error("Le nom du fichier n’est pas accepté.");
      source = { name: file.name, type: file.type, size: file.size };
    }
    if (mode !== "analyze" && ["square", "landscape", "portrait"].indexOf(format) < 0)
      throw new Error("Choisissez un format de sortie.");
    if (mode !== "analyze" && agent === "video" && [5, 10, 15].indexOf(duration) < 0)
      throw new Error("Choisissez une durée proposée.");
    return { schema: "media-draft/1", agent: agent, operation: mode, request: prompt.trim(),
      source: source, output: mode === "analyze" ? null : { format: format,
        duration_seconds: agent === "video" ? duration : null },
      state: "LOCAL_DRAFT", submitted: false };
  }
  function mount(doc) {
    if (!doc.getElementById("media-agents")) return { clear: function () {} };
    var agents = ["image", "video"];
    function el(id) { return doc.getElementById(id); }
    function close() {
      agents.forEach(function (a) { el(a + "-workspace").hidden = true; el("open-" + a).setAttribute("aria-expanded", "false"); });
    }
    function invalidate(a) { el(a + "-draft").hidden = true; el(a + "-summary").textContent = "";
      el(a + "-request").textContent = ""; el(a + "-file-summary").textContent = "";
      el(a + "-status").textContent = ""; }
    function modeChanged(a) {
      var mode = el(a + "-mode").value;
      el(a + "-settings").hidden = mode === "analyze";
      el(a + "-source").accept = allowed(a, mode).map(function (t) { return t + "," + TYPES[t]; }).join(",");
      el(a + "-source-label").textContent = mode === "create" ? "Fichier de référence (facultatif)" : "Fichier à " + (mode === "edit" ? "modifier" : "analyser") + " (obligatoire)";
      el(a + "-prompt-label").textContent = mode === "create" ? "Décrivez votre idée" : mode === "edit" ? "Que souhaitez-vous modifier ?" : "Que souhaitez-vous comprendre ?";
      el(a + "-prompt").placeholder = mode === "analyze" ? "Décrire la scène, lire un texte, relever les éléments importants…" : "Sujet, ambiance, détails importants…";
      el(a + "-file-help").textContent = a === "image" ? "PNG, JPEG ou WebP · 20 Mio maximum." :
        mode === "create" ? "Référence PNG, JPEG, WebP (20 Mio), MP4 ou WebM (200 Mio)." : "MP4 ou WebM · 200 Mio maximum.";
      invalidate(a);
    }
    function clear(a) { el(a + "-form").reset(); modeChanged(a); }
    agents.forEach(function (a) {
      var open = el("open-" + a); open.disabled = false;
      open.addEventListener("click", function () { close(); el(a + "-workspace").hidden = false;
        open.setAttribute("aria-expanded", "true"); el(a + "-title").focus(); });
      el(a + "-back").addEventListener("click", function () { close(); open.focus(); });
      el(a + "-clear").addEventListener("click", function () { clear(a); el(a + "-prompt").focus(); });
      el(a + "-form").addEventListener("input", function () { invalidate(a); });
      el(a + "-form").addEventListener("change", function () { invalidate(a); });
      el(a + "-mode").addEventListener("change", function () { modeChanged(a); });
      el(a + "-form").addEventListener("submit", function (event) {
        event.preventDefault(); invalidate(a);
        try {
          var d = prepareDraft(a, el(a + "-mode").value, el(a + "-prompt").value,
            el(a + "-source").files[0] || null, el(a + "-format").value,
            a === "video" ? Number(el(a + "-duration").value) : null);
          el(a + "-summary").textContent = (a === "image" ? "Image" : "Vidéo") + " · " +
            ({ create: "Créer", edit: "Modifier", analyze: "Analyser" })[d.operation] +
            (d.output ? " · " + ({ square: "Carré", landscape: "Paysage", portrait: "Portrait" })[d.output.format] +
              (a === "video" ? " · " + d.output.duration_seconds + " secondes souhaitées" : "") : "");
          el(a + "-request").textContent = d.request;
          el(a + "-file-summary").textContent = d.source ? "Fichier choisi : " + d.source.name + " — contenu non lu." : "Sans fichier de référence.";
          el(a + "-draft").hidden = false;
          el(a + "-status").textContent = "Brouillon préparé. Aucune mission envoyée ; le moteur reste à raccorder.";
        } catch (err) { el(a + "-status").textContent = err.message; }
      });
      modeChanged(a);
    });
    return { clear: function () { agents.forEach(clear); close(); } };
  }
  var api = { prepareDraft: prepareDraft, mount: mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonMediaAgents = api;
})(typeof window !== "undefined" ? window : this);
