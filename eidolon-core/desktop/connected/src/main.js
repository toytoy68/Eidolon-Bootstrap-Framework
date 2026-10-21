/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : main.js
 * Description : Démarrage navigateur du client connecté : fetch même origine, sans stockage (C-TASK-G031)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  var C = root.EidolonConnected, V = root.EidolonConnectedView;
  var TIMEOUT_MS = 10000, TURN_TIMEOUT_MS = 150000, AUTO_MS = 10000;

  // Same-origin, relative "/v1/..." paths only; no credentials, cache or redirect followed.
  function transport(method, path, body, token) {
    if (typeof path !== "string" || path.indexOf("/v1/") !== 0) return Promise.reject(new Error("PATH_REFUSED"));
    var controller = new AbortController();
    // A model turn can legitimately exceed the short read/control deadline.
    var timeout = method === "POST" && path === "/v1/conversations/turn" ? TURN_TIMEOUT_MS : TIMEOUT_MS;
    var timer = setTimeout(function () { controller.abort(); }, timeout);
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

  if (typeof module !== "undefined" && module.exports) module.exports = { transport: transport };
  if (typeof document === "undefined") return;

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
    // G124: unfinished cancellation requests (ids, key, digest; no secret) survive a reload in this tab only.
    var cancelStorage = null;
    try { cancelStorage = window.sessionStorage; } catch (e) { cancelStorage = null; }
    var monitorPhase = null;
    var privateConversation = null, commUi = null;
    // G176: frame (eye, DARME button, sections). Pure views of the existing states, no new request.
    var shellApi = root.EidolonShell, shell = shellApi ? shellApi.mount(document) : null;
    var eyeInput = { phase: "closed", pending: false, comm: null };
    function eye() { if (shell) shell.renderEye(eyeInput); }
    conversation = root.EidolonConversation.mount(document, {
      transport: transport,
      beforeIdentityCapture: function () { if (comm) comm.reset(); var block=document.getElementById("comm");if(block)block.inert=true; },
      afterIdentityCapture: function () { var block=document.getElementById("comm");if(block)block.inert=false; },
      onPhase: function (phase, st) {
        var nextPrivate = phase === "open" && st ? st.conversationId : null;
        if (nextPrivate !== privateConversation) {
          privateConversation = nextPrivate;
          if (comm) comm.reset();
          media.clear();
          ["conv-text", "comm-note"].forEach(function (id) {
            var n = document.getElementById(id); if (n) { if ("value" in n) n.value = ""; else n.textContent = ""; }
          });
        }
        eyeInput.phase = phase;
        eyeInput.pending = !!(st && st.items && st.items.some(function (i) { return i.status === "sent" || i.status === "pending"; }));
        var closed = phase !== "open";
        ["comm"].forEach(function (id) { var n = document.getElementById(id); if (n) n.hidden = closed; });
        var note = document.getElementById("comm-closed-note"); if (note) note.hidden = !closed;
        var darmeNote = document.getElementById("darme-closed-note"); if (darmeNote) darmeNote.hidden = !closed;
        eye();
        if (commUi) commUi.conversationChanged(nextPrivate);
        if (!monitoring || phase === monitorPhase) return;
        monitorPhase = phase;
        if (phase === "open") monitoring.ready(); else if (phase === "closed") monitoring.stop();
      },
      storage: cancelStorage,
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
    // G156: machine dashboard (DARME status through Core's relay /v1/monitor/*), same paired key.
    var monApi = root.EidolonMonitoring, monitoring = null;
    if (monApi && document.getElementById("monitor")) {
      monitoring = monApi.createMonitoring({ transport: transport,
        key: function () { return conversation.conversation.authorization(); },
        onChange: function (st) { monApi.render(document, st); if (shell) shell.renderDarme(st); } });
      monApi.mount(document, monitoring);
      document.addEventListener("visibilitychange", function () { monitoring.visibility(document.hidden); });
      window.addEventListener("pagehide", function () { monitoring.stop(); });
    }
    // C147: voice and camera (all off by default), through Core's same-origin relay /v1/comm/*.
    var commApi = root.EidolonCommunication;
    if (commApi && document.getElementById("comm")) {
      var comm = commApi.createCommunication(commApi.browserDeps(window, function () {
        return conversation.conversation.authorization();
      }));
      comm.onChange(function (state) { eyeInput.comm = state; eye(); });
      commUi = commApi.mount(document, comm, { autoStart: root.__EIDOLON_DESKTOP_AUTOSTART === true, voiceSend: async function (text) {
        var engine = conversation.conversation, before = engine.state();
        if (document.getElementById("conv-text").value.trim()) throw new Error("Un brouillon est présent : envoyez-le ou effacez-le avant le vocal.");
        if (before.phase !== "open" || before.items.some(function (item) { return ["sent", "pending", "uncertain"].includes(item.status); })) throw new Error("Un message attend une réponse ou une vérification.");
        var count = before.items.length, id = before.conversationId;
        await engine.send(text);
        var after = engine.state(), item = after.items[count];
        if (after.conversationId !== id || !item || item.status !== "received" || !item.reply) throw new Error("Envoi non confirmé : consultez la conversation, aucun renvoi automatique.");
        var reply = item.reply;
        return reply.core_note ? (root.EidolonConversation.NOTES[reply.core_note] || "Consultez la réponse dans la conversation.") : reply.model_text;
      }, observe: function (node, fn) {
        if (window.MutationObserver) new MutationObserver(fn).observe(node, { childList: true });
      } });
      window.addEventListener("pagehide", function () { comm.reset(); });
    }

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
