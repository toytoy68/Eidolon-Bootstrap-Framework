/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : shell.js
 * Description : Cadre PC (G176) : œil d'activité à gauche, saisie en haut, DARME à droite, navigation par sections
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Pure views of the existing states (conversation, voice/camera, DARME) + the navigation between sections.
// Rules: the eye shows Eidolon's ACTIVITY and, separately, the camera's REAL state: work in progress never looks
// like a capture, and showing the icon never switches a sensor on. The DARME button summarises without
// reassuring: grey stays grey, stale loses its colour, an unacknowledged alert stays visible.
(function (root) {
  "use strict";
  var VIEWS = ["conversation", "memory", "media", "missions", "settings"];
  var CAMERA = { capturing: "active", processing: "image en analyse, caméra éteinte", ready: "éteinte",
    disabled: "éteinte", stopped: "éteinte", unavailable: "indisponible", permission_denied: "refusée", busy: "occupée ailleurs" };

  // Eye: activity of Eidolon and camera state, from facts only.
  function eyeState(input) {
    var phase = input.phase, comm = input.comm, pending = !!input.pending;
    var mic = comm ? comm.microphone.state : "unavailable", cam = comm ? comm.camera.state : "unavailable";
    var speaker = comm ? comm.speaker.state : "disabled";
    var activity = phase !== "open" ? "fermée" : mic === "capturing" ? "écoute" :
      (pending || mic === "processing" || cam === "processing") ? "réfléchit" : speaker === "processing" ? "parle" : "disponible";
    var camera = CAMERA[cam] || "éteinte";
    return { activity: activity, camera: camera, cameraActive: cam === "capturing",
      busy: activity === "écoute" || activity === "réfléchit" || activity === "parle",
      text: (phase === "open" ? "Eidolon " + activity : "Conversation fermée") + " · caméra " + camera };
  }

  // DARME button: the WORST real state among machines, never a colour without data.
  function darmeSummary(st) {
    if (!st || st.phase === "off") return { level: "off", text: "DARME · conversation fermée" };
    if (st.phase === "idle") return { level: "idle", text: "DARME · non lu" };
    if (st.phase === "loading") return { level: "idle", text: "DARME · lecture…" };
    if (st.phase === "not_enabled") return { level: "idle", text: "DARME · non activé" };
    if (!st.data) return { level: "error", text: "DARME · indisponible" };
    var order = { red: 5, blue: 4, stale: 3, unknown: 2, grey: 1, gold: 0 }, worst = null, alerts = 0;
    st.data.machines.forEach(function (m) {
      var level = !m.darme ? "unknown" : m.state === "stale" ? "stale" : m.darme.badge;
      if (m.darme && m.darme.badge === "red" && m.state !== "stale") alerts += m.darme.unacknowledged_alerts || 0;
      if (worst === null || order[level] > order[worst]) worst = level;
    });
    var words = { red: "alerte", blue: "intervention", stale: "périmé", unknown: "incomplet", grey: "gris", gold: "or" };
    var text = "DARME · " + (worst === "red" && alerts ? alerts + " alerte(s)" : words[worst || "unknown"]);
    if (st.error) text += " · dernière lecture en échec";
    return { level: worst || "unknown", text: text };
  }

  function mount(doc, hooks) {
    hooks = hooks || {};
    function $(id) { return doc.getElementById(id); }
    var current = null;

    // Sections stay in the page (anchors): nothing is hidden, the link only marks where the user went.
    function show(view) {
      if (VIEWS.indexOf(view) < 0) return;
      current = view;
      Array.prototype.forEach.call(doc.querySelectorAll("[data-nav]"), function (link) {
        if (link.getAttribute("data-nav") === view) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    }

    function drawer(button, panel, open) {
      var willOpen = open === undefined ? panel.classList.contains("drawer-closed") : open;
      panel.classList.toggle("drawer-closed", !willOpen);
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
      return willOpen;
    }

    Array.prototype.forEach.call(doc.querySelectorAll("[data-nav]"), function (link) {
      link.addEventListener("click", function () { show(link.getAttribute("data-nav")); });
    });
    var eye = $("eye-button"), eyePanel = $("eye-drawer"), darme = $("darme-button"), darmePanel = $("darme-drawer");
    eye.addEventListener("click", function () { if (drawer(eye, eyePanel)) $("eye-drawer-title").focus(); });
    darme.addEventListener("click", function () { if (drawer(darme, darmePanel)) $("monitor-title").focus(); });
    Array.prototype.forEach.call(doc.querySelectorAll("[data-close-drawer]"), function (button) {
      button.addEventListener("click", function () {
        var target = button.getAttribute("data-close-drawer");
        drawer(target === "eye" ? eye : darme, target === "eye" ? eyePanel : darmePanel, false);
        (target === "eye" ? eye : darme).focus();
      });
    });
    doc.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      if (!eyePanel.classList.contains("drawer-closed")) { drawer(eye, eyePanel, false); eye.focus(); }
      else if (!darmePanel.classList.contains("drawer-closed")) { drawer(darme, darmePanel, false); darme.focus(); }
    });

    function renderEye(state) {
      var view = eyeState(state);
      $("eye-state").textContent = view.text;
      eye.classList.toggle("eye-busy", view.busy);
      eye.classList.toggle("eye-camera", view.cameraActive);
      eye.setAttribute("aria-label", "Activité d'Eidolon et caméra : " + view.text + ". Ouvrir la voix et la caméra.");
      return view;
    }
    function renderDarme(st) {
      var view = darmeSummary(st);
      $("darme-state").textContent = view.text;
      darme.setAttribute("data-level", view.level);
      darme.setAttribute("aria-label", view.text + ". Ouvrir le détail des machines.");
      return view;
    }
    // Side panels start under the top bar, whatever its height (wrapping, zoom, Windows scaling).
    var bar = doc.querySelector(".appbar");
    function place() {
      if (bar) doc.documentElement.style.setProperty("--appbar-h", Math.ceil(bar.getBoundingClientRect().height) + "px");
    }
    place();
    var view = doc.defaultView;
    if (view && view.ResizeObserver && bar) new view.ResizeObserver(place).observe(bar);
    else if (view) view.addEventListener("resize", place);
    show(hooks.initial || "conversation");
    return { show: show, renderEye: renderEye, renderDarme: renderDarme, view: function () { return current; } };
  }

  var api = { eyeState: eyeState, darmeSummary: darmeSummary, mount: mount, VIEWS: VIEWS };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonShell = api;
})(typeof window !== "undefined" ? window : this);
