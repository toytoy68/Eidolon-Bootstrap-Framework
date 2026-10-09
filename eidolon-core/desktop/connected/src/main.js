/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : main.js
 * Description : Démarrage navigateur du client connecté : fetch même origine, sans stockage (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  if (typeof document === "undefined") return;
  var C = root.EidolonConnected, V = root.EidolonConnectedView;
  var TIMEOUT_MS = 10000, AUTO_MS = 10000;

  // Same-origin, relative "/v1/..." paths only; no credentials, cache or redirect followed.
  function transport(method, path, body, token) {
    if (typeof path !== "string" || path.indexOf("/v1/") !== 0) return Promise.reject(new Error("PATH_REFUSED"));
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);
    var headers = { "Authorization": "Bearer " + token };
    var init = { method: method, headers: headers, cache: "no-store", credentials: "omit",
      redirect: "error", referrerPolicy: "no-referrer", signal: controller.signal };
    if (body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    return fetch(path, init).then(function (res) {
      return res.text().then(function (text) {
        var json = null;
        try { json = JSON.parse(text); } catch (err) { json = null; }
        return { status: res.status, json: json };
      });
    }).finally(function () { clearTimeout(timer); });
  }

  // The logo is an optional asset: a server that does not serve it keeps the text name (G078).
  function showLogo() {
    var logo = document.getElementById("brand-logo");
    if (!logo || typeof logo.decode !== "function") return;
    logo.decode().then(function () {
      if (!logo.naturalWidth) return;
      logo.hidden = false;
      document.getElementById("brand-name").hidden = true;
    }, function () { /* not served: the text name stays */ });
  }

  function start() {
    var autoTimer = null;
    showLogo();
    var media = root.EidolonMediaAgents.mount(document);
    window.addEventListener("pagehide", function () { media.clear(); });
    var conversation = null;
    var session = C.createSession({ transport: transport, onChange: function (s) {
      V.render(document, s);
      if (s.phase !== "connected" || !s.list.selection) stopAuto();
      if (conversation) conversation.refresh();
    } });
    // G088: the conversation follows its mission through the read session (same capture, same rules).
    conversation = root.EidolonConversation.mount(document, {
      transport: transport,
      missionStatus: function (st) {
        var id = st.submission && st.submission.receipt && st.submission.receipt.mission_id;
        var sel = session.state().list.selection;
        var view = sel && sel.missionId === id && sel.sync && sel.sync.view;
        return view && view.mission ? view.mission.status : null;
      },
      follow: function (id) {
        session.relist().then(function () { return session.selectMission(id); }).then(function () {
          document.getElementById("details").scrollIntoView({ block: "start" });
        });
      }
    });
    window.addEventListener("pagehide", function () { conversation.clear(); });

    function stopAuto() {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
      document.getElementById("auto").checked = false;
    }

    document.getElementById("connect-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var input = document.getElementById("token");
      var value = input.value.trim();
      input.value = "";                    // the DOM never keeps the token
      // G037: success moves the focus to the mission list; a refusal keeps it on the token field.
      session.connect(value).then(function (ok) {
        if (ok) document.getElementById("missions").focus();
        else input.focus();
      });
    });
    document.getElementById("disconnect").addEventListener("click", function () { stopAuto(); session.disconnect(); media.clear(); });
    document.getElementById("relist").addEventListener("click", function () { session.relist(); });
    document.getElementById("refresh").addEventListener("click", function () { session.refreshSelection(); });
    document.getElementById("accept-reset").addEventListener("click", function () { session.acceptReset(); });
    document.getElementById("archives-load").addEventListener("click", function () { session.loadArchives(); });
    document.getElementById("archives-more").addEventListener("click", function () { session.moreArchives(); });
    document.getElementById("mission-list").addEventListener("click", function (event) {
      var button = event.target.closest("button[data-mission-id]");
      if (button) session.selectMission(button.dataset.missionId);
    });
    document.getElementById("receipt-form").addEventListener("submit", function (event) {
      event.preventDefault();
      session.lookupReceipt(document.getElementById("receipt-client").value.trim(),
        document.getElementById("receipt-key").value.trim());
    });
    document.getElementById("auto").addEventListener("change", function (event) {
      if (!event.target.checked) { stopAuto(); return; }
      autoTimer = setInterval(function () { session.refreshSelection(); }, AUTO_MS);
    });
    V.render(document, session.state());
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})(typeof window !== "undefined" ? window : this);
