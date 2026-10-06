/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : model.js
 * Description : États et transitions du prototype bureau Eidolon (C-TASK-G009)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */

/*
 * Pure, deterministic model. No network, no timer, no storage, no OS access.
 *
 * Two halves live in one state object but never read each other's fields:
 *   - state.client : what the desktop client knows (its projection of Core);
 *   - state.sim    : a synthetic Core used only to drive the demonstration.
 * The client changes its mission view ONLY by applying sequenced events from
 * the simulated Core. A click produces an outbox entry, never a server state.
 *
 * Loaded as a classic script (works from file://) and as a CommonJS module
 * for the Node tests.
 */
(function (root) {
  "use strict";

  var EPOCH = Date.UTC(2026, 9, 5, 14, 0, 0); // synthetic clock origin, labelled as such in the UI
  // Commands awaiting a receipt are never purged; resolved ones are kept up to this bound.
  var MAX_RESOLVED_COMMANDS = 10;
  var MAX_DECISION_HISTORY = 50;
  var UNRESOLVED = { sending: true, unknown: true, checking: true, "not-found": true };
  var FAMILY = { approve: "decision", reject: "decision", revoke: "revoke", cancel: "cancel" };

  var PROPOSAL_SHA = "9f2c41d07ab35e18c6f0d2a4b7e91c5304f6a8d2e1b0c9f7a6e5d4c3b2a19081";

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function syntheticTime(minute) {
    return new Date(EPOCH + minute * 60000).toISOString().replace(".000Z", "Z");
  }

  function clockLabel(minute) {
    var d = new Date(EPOCH + minute * 60000);
    var hh = String(d.getUTCHours()).padStart(2, "0");
    var mm = String(d.getUTCMinutes()).padStart(2, "0");
    return hh + ":" + mm + " UTC (synthétique)";
  }

  // ---- Core truth (simulated server) -----------------------------------------------------

  function coreMission() {
    return {
      id: "m-0042",
      title: "Redémarrer le service de démonstration",
      status: "BLOCKED",
      outcome: null,
      revision: 3,
      cancelRequested: false,
      proposal: {
        id: "p-7",
        sha256: PROPOSAL_SHA,
        tool: "service.restart.simulated",
        target: "svc-demo",
        condition: "état observé DEGRADED, révision 3",
        status: "PENDING",
        decidedAt: null,
        receipt: null
      },
      effect: "NOT_STARTED",
      evidence: [
        { id: "e-1", kind: "observation", label: "État du service svc-demo : DEGRADED",
          origin: "serveur simulé (sqlite-synthetic-services/1)", minute: -6,
          sha256: "3b8e0f6c1d2a49e7b5c4f3a2d1e0f9c8b7a6d5e4f3c2b1a0918273645546372a" }
      ]
    };
  }

  var SCENARIOS = {
    "accord-succes": {
      label: "Accord, exécution simulée, résultat vérifié",
      summary: "Mission en attente d'accord. L'accord est enregistré, puis Core simule l'exécution et vérifie l'effet."
    },
    "refus": {
      label: "Refus sans exécution",
      summary: "Même mission. Refuser n'entraîne aucune exécution et l'œil ne passe jamais « Au travail »."
    },
    "accuse-perdu": {
      label: "Accusé perdu puis consultation du reçu",
      summary: "L'accord part, la connexion tombe avant l'accusé. Au retour : rejeu sans doublon, puis consultation du reçu avant toute nouvelle émission."
    },
    "revue-requise": {
      label: "Revue requise, effet inconnu",
      summary: "Une tentative a commencé mais son effet n'est pas établi. Aucune relance automatique n'est proposée."
    },
    "hors-ligne": {
      label: "Core et appareils hors ligne",
      summary: "Le client n'a plus de nouvelles : il montre le dernier état connu, daté, sans rien affirmer de l'état actuel."
    },
    "session-verrouillee": {
      label: "Session verrouillée",
      summary: "Une décision attend pendant que la session Windows est verrouillée : notification générique, aucune décision possible."
    },
    "micro-hors-ligne": {
      label: "Micro actif, Core déconnecté",
      summary: "La capture locale (simulée) reste signalée même quand le serveur est injoignable."
    }
  };

  // ---- Initial state ----------------------------------------------------------------------

  function initialState(scenario) {
    if (!SCENARIOS[scenario]) throw new Error("unknown scenario " + scenario);
    var mission = coreMission();
    var sim = {
      minute: 0,
      ackMode: scenario === "accuse-perdu" ? "lost-once" : "ok",
      ackLost: false,
      mission: mission,
      log: [],          // every event Core emitted, in order
      receipts: {},     // request key -> recorded decision
      processed: 0      // outbox entries already handled
    };
    var client = {
      connection: "online",
      session: "open",
      windowOpen: true,
      view: "compact",
      tab: "conversation",
      silence: false,
      mic: "off",
      camera: "off",
      cursor: 0,                 // last applied event sequence
      seen: [],                  // applied sequences (duplicates are ignored)
      duplicatesIgnored: 0,
      snapshotRequested: false,
      lastContact: 0,
      mission: null,             // projection built from events
      commands: [],              // one entry per command key, until resolved (see purgeCommands)
      strayReplies: 0,           // replies whose key this client never sent, or already purged
      duplicateReplies: 0,       // repeated replies for an already resolved command
      decisionHistory: [],
      outbox: [],                // everything the client SENT (assertable)
      messages: [],
      toasts: [],
      notice: null,
      draft: "",
      reading: { open: false, text: "", reviewed: false }
    };
    var state = { scenario: scenario, sim: sim, client: client };

    if (scenario === "revue-requise") {
      mission.status = "REVIEW_REQUIRED";
      mission.proposal.status = "USED";
      mission.proposal.decidedAt = -30;
      mission.effect = "UNKNOWN";
      mission.evidence.push({ id: "e-2", kind: "attempt", label: "Tentative 1 lancée, aucun reçu de fin",
        origin: "serveur simulé", minute: -25, sha256: null });
    }
    deliver(state, emit(state, "MISSION_SNAPSHOT", { mission: clone(mission) }));
    client.messages = openingMessages(scenario);

    if (scenario === "hors-ligne" || scenario === "micro-hors-ligne") {
      sim.minute = 42;
      client.connection = "offline";
    }
    if (scenario === "micro-hors-ligne") client.mic = "on";
    if (scenario === "session-verrouillee") {
      client.session = "locked";
      client.windowOpen = false;
      pushToast(state, "decision");
    }
    return state;
  }

  function openingMessages(scenario) {
    var list = [
      { from: "user", text: "Le service de démonstration a l'air dégradé, tu peux regarder ?", minute: -8 },
      { from: "eidolon", text: "J'ai ouvert la mission m-0042. Le service svc-demo est observé DEGRADED. "
        + "Je propose de le redémarrer : c'est une action, elle attend ton accord.", minute: -6 },
      { from: "eidolon", text: "Une page de documentation sur ce service demande une connexion. "
        + "Je ne l'ai pas lue ; tu peux me l'envoyer par la lecture assistée.", minute: -5, reading: true }
    ];
    if (scenario === "revue-requise") {
      list[1] = { from: "eidolon", text: "La tentative de redémarrage de svc-demo a commencé, mais je n'ai pas reçu "
        + "sa fin. Je ne sais pas si le service a été redémarré : une revue est nécessaire.", minute: -24 };
    }
    return list;
  }

  // ---- Simulated Core: events -------------------------------------------------------------

  function emit(state, type, data) {
    var sim = state.sim;
    var event = { seq: sim.log.length + 1, type: type, minute: sim.minute, data: clone(data || {}) };
    sim.log.push(event);
    return event;
  }

  function deliver(state, event) {
    if (state.client.connection !== "online") return;
    applyEvent(state, event);
  }

  // Direct, unsequenced reply to the requesting client (acknowledgement or receipt).
  // Shared mission events never carry a client's request key. A reply only ever
  // touches the command with the same key; it never triggers a new emission.
  function reply(state, message) {
    if (state.client.connection !== "online") return;
    receive(state.client, message, state.sim.minute);
  }

  function findCommand(c, key) {
    for (var i = 0; i < c.commands.length; i++) if (c.commands[i].key === key) return c.commands[i];
    return null;
  }

  function isUnresolved(command) {
    return Boolean(UNRESOLVED[command.phase]);
  }

  function receive(c, message, minute) {
    var command = findCommand(c, message.key);
    if (!command) { c.strayReplies += 1; return; }
    if (!isUnresolved(command)) { c.duplicateReplies += 1; return; }
    if (message.found) {
      command.phase = "acknowledged";
      command.receipt = message.receipt;
      command.viaReceipt = message.type === "RECEIPT";
      command.resolvedMinute = minute;
      c.decisionHistory.push({ kind: command.kind, key: command.key, receipt: message.receipt });
      if (c.decisionHistory.length > MAX_DECISION_HISTORY) c.decisionHistory.shift();
      purgeCommands(c);
    } else if (message.type === "ACK") {
      // The server answered this request and refused it (proposal changed or already decided).
      command.phase = "refused";
      command.resolvedMinute = minute;
      purgeCommands(c);
    } else {
      // Receipt not found: NOT proof that nothing happened. Stays unresolved, never resent.
      command.phase = "not-found";
    }
  }

  // Unresolved commands are always kept; only the oldest resolved ones are dropped.
  function purgeCommands(c) {
    var resolved = c.commands.filter(function (x) { return !isUnresolved(x); });
    var excess = resolved.length - MAX_RESOLVED_COMMANDS;
    if (excess <= 0) return;
    var drop = resolved.slice(0, excess).map(function (x) { return x.key; });
    c.commands = c.commands.filter(function (x) { return drop.indexOf(x.key) === -1; });
  }

  function unresolvedOf(c, family) {
    return c.commands.filter(function (x) { return isUnresolved(x) && (!family || FAMILY[x.kind] === family); });
  }

  // Pure entry point for tests and future transports: deliver one direct reply.
  function receiveReply(state, message) {
    var s = clone(state);
    receive(s.client, message, s.sim.minute);
    return s;
  }

  // The client applies sequenced events once. A gap asks for a fresh snapshot.
  function applyEvent(state, event) {
    var c = state.client;
    if (event.seq <= c.cursor) {
      c.duplicatesIgnored += 1;
      return;
    }
    if (event.seq > c.cursor + 1 && event.type !== "MISSION_SNAPSHOT") {
      c.snapshotRequested = true;
      c.outbox.push({ type: "SNAPSHOT_REQUEST", after: c.cursor, minute: state.sim.minute });
      return;
    }
    c.cursor = event.seq;
    c.seen.push(event.seq);
    c.lastContact = event.minute;
    var d = event.data;
    switch (event.type) {
      case "MISSION_SNAPSHOT":
        c.mission = clone(d.mission);
        c.snapshotRequested = false;
        break;
      case "DECISION_RECORDED":
        c.mission.proposal.status = d.status;
        c.mission.proposal.decidedAt = event.minute;
        c.mission.revision = d.revision;
        break;
      case "APPROVAL_REVOKED":
        c.mission.proposal.status = "REVOKED";
        c.mission.revision = d.revision;
        break;
      case "MISSION_RUNNING":
        c.mission.status = "RUNNING";
        c.mission.proposal.status = "USED";
        c.mission.effect = "UNKNOWN";
        c.mission.revision = d.revision;
        break;
      case "EFFECT_VERIFIED":
        c.mission.status = "SUCCEEDED";
        c.mission.outcome = "ACHIEVED";
        c.mission.effect = "VERIFIED_PAST_EFFECT";
        c.mission.revision = d.revision;
        c.mission.evidence = clone(d.evidence);
        break;
      case "CANCEL_REQUESTED":
        c.mission.cancelRequested = true;
        c.mission.revision = d.revision;
        break;
      case "MISSION_CANCELLED":
        c.mission.status = "CANCELLED";
        c.mission.revision = d.revision;
        break;
      default:
        break;
    }
    if (event.type === "MISSION_SNAPSHOT" || event.type === "DECISION_RECORDED") maybeToast(state);
  }

  // One deterministic step of the simulated Core: first pending request, else the script.
  function serverStep(state) {
    var s = clone(state);
    var sim = s.sim, c = s.client;
    sim.minute += 1;
    if (c.connection !== "online") {
      return s; // in this simulation Core waits; nothing would reach this client anyway
    }
    var pending = c.outbox.slice(sim.processed);
    if (pending.length) {
      sim.processed += 1;
      handleRequest(s, pending[0]);
      return s;
    }
    var m = sim.mission;
    if (m.proposal.status === "APPROVED" && m.status === "BLOCKED" && !m.cancelRequested) {
      m.status = "RUNNING"; m.proposal.status = "USED"; m.effect = "UNKNOWN"; m.revision += 1;
      deliver(s, emit(s, "MISSION_RUNNING", { revision: m.revision }));
    } else if (m.status === "RUNNING" && !m.cancelRequested) {
      m.status = "SUCCEEDED"; m.outcome = "ACHIEVED"; m.effect = "VERIFIED_PAST_EFFECT"; m.revision += 1;
      m.evidence = m.evidence.concat([
        { id: "e-3", kind: "attempt", label: "Redémarrage simulé de svc-demo, tentative 1, reçu complet",
          origin: "service.restart.simulated", minute: sim.minute - 1,
          sha256: "a41f9c3e7b2d5068e1f4c7a9b3d2e6f0c8a7b5d4e3f2a1b0c9d8e7f6a5b4c3d2" },
        { id: "e-4", kind: "verification", label: "État observé après coup : RUNNING, révision 4",
          origin: "serveur simulé, nouvelle lecture", minute: sim.minute,
          sha256: "c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6" }
      ]);
      deliver(s, emit(s, "EFFECT_VERIFIED", { revision: m.revision, evidence: m.evidence }));
    } else if (m.cancelRequested && m.status === "BLOCKED") {
      m.status = "CANCELLED"; m.revision += 1;
      deliver(s, emit(s, "MISSION_CANCELLED", { revision: m.revision }));
    }
    return s;
  }

  function handleRequest(s, req) {
    var sim = s.sim, m = sim.mission, c = s.client;
    switch (req.type) {
      case "DECIDE": {
        var accepted = m.proposal.status === "PENDING" && req.proposalSha === m.proposal.sha256
          && req.expectedRevision === m.revision;
        if (!accepted) {
          reply(s, { type: "ACK", key: req.key, found: false });
          return;
        }
        m.proposal.status = req.decision === "approve" ? "APPROVED" : "REJECTED";
        m.revision += 1;
        var receipt = "r-" + req.key;
        sim.receipts[req.key] = { status: m.proposal.status, receipt: receipt, minute: sim.minute };
        var ev = emit(s, "DECISION_RECORDED", { status: m.proposal.status, revision: m.revision });
        if (sim.ackMode === "lost-once" && !sim.ackLost) {
          sim.ackLost = true;           // recorded by Core; event and acknowledgement never arrive
          goOffline(c);
          return;
        }
        deliver(s, ev);
        reply(s, { type: "ACK", key: req.key, found: true, receipt: receipt });
        return;
      }
      case "RECEIPT_QUERY": {
        var r = sim.receipts[req.key];
        reply(s, r ? { type: "RECEIPT", key: req.key, found: true, receipt: r.receipt }
          : { type: "RECEIPT", key: req.key, found: false });
        return;
      }
      case "REVOKE": {
        if (m.proposal.status !== "APPROVED") {
          reply(s, { type: "ACK", key: req.key, found: false });
          return;
        }
        m.proposal.status = "REVOKED"; m.revision += 1;
        sim.receipts[req.key] = { status: "REVOKED", receipt: "r-" + req.key, minute: sim.minute };
        deliver(s, emit(s, "APPROVAL_REVOKED", { revision: m.revision }));
        reply(s, { type: "ACK", key: req.key, found: true, receipt: "r-" + req.key });
        return;
      }
      case "CANCEL_REQUEST": {
        m.cancelRequested = true; m.revision += 1;
        sim.receipts[req.key] = { status: "CANCEL_REQUESTED", receipt: "r-" + req.key, minute: sim.minute };
        deliver(s, emit(s, "CANCEL_REQUESTED", { revision: m.revision }));
        reply(s, { type: "ACK", key: req.key, found: true, receipt: "r-" + req.key });
        return;
      }
      case "SYNC": {
        // Replay everything after the cursor, plus the last applied event again (a duplicate).
        var from = Math.max(0, req.after - 1);
        sim.log.slice(from).forEach(function (event) { deliver(s, event); });
        return;
      }
      case "SNAPSHOT_REQUEST": {
        deliver(s, emit(s, "MISSION_SNAPSHOT", { mission: clone(m) }));
        return;
      }
      default:
        return; // CHAT and READ_SUBMIT are only recorded in this prototype
    }
  }

  function goOffline(c) {
    c.connection = "offline";
    c.commands.forEach(function (x) { if (x.phase === "sending" || x.phase === "checking") x.phase = "unknown"; });
  }

  // ---- Client intents -----------------------------------------------------------------------

  function decisionBlocker(state) {
    var c = state.client, m = c.mission;
    if (c.connection !== "online") return "Hors ligne : aucune décision ne peut partir, et rien n'est mis en file.";
    if (c.session !== "open") return "Session verrouillée : déverrouille Windows pour voir et décider.";
    if (!c.windowOpen) return "Ouvre la fenêtre d'Eidolon pour décider.";
    if (unresolvedOf(c, "decision").length) return "Une décision précédente n'est pas réconciliée : consulte son reçu ; rien n'est renvoyé.";
    if (!m || m.proposal.status !== "PENDING" || m.status !== "BLOCKED") return "Aucune décision n'est attendue sur cette proposition.";
    return null;
  }

  function sendBlocker(state) {
    var c = state.client;
    if (c.connection !== "online") return "Hors ligne : rien n'est envoyé ni mis en file.";
    if (c.session !== "open") return "Session verrouillée.";
    return null;
  }

  function newCommand(kind, key, minute) {
    return { kind: kind, key: key, phase: "sending", receipt: null, viaReceipt: false,
      sentMinute: minute, resolvedMinute: null };
  }

  function newKey(state) {
    return "k" + state.sim.minute + "-" + state.client.outbox.length;
  }

  function dispatch(state, intent) {
    var s = clone(state);
    var c = s.client, m = c.mission;
    c.notice = null;
    var blocked;
    switch (intent.type) {
      case "approve":
      case "reject":
        blocked = decisionBlocker(s);
        if (blocked) { c.notice = blocked; return s; }
        var key = newKey(s);
        c.commands.push(newCommand(intent.type, key, s.sim.minute));
        c.outbox.push({ type: "DECIDE", decision: intent.type, key: key, proposalSha: m.proposal.sha256,
          expectedRevision: m.revision, minute: s.sim.minute });
        return s;
      case "revoke":
        blocked = sendBlocker(s);
        if (blocked) { c.notice = blocked; return s; }
        if (!m || m.proposal.status !== "APPROVED") {
          c.notice = m && m.proposal.status === "USED"
            ? "Accord déjà consommé : il ne peut plus être révoqué. Tu peux demander l'annulation de la mission."
            : "Aucun accord révocable.";
          return s;
        }
        if (unresolvedOf(c, "revoke").length) {
          c.notice = "Une révocation est déjà en cours ; elle n'est pas renvoyée.";
          return s;
        }
        var rk = newKey(s);
        c.commands.push(newCommand("revoke", rk, s.sim.minute));
        c.outbox.push({ type: "REVOKE", key: rk, minute: s.sim.minute });
        return s;
      case "request-cancel":
        blocked = sendBlocker(s);
        if (blocked) { c.notice = blocked; return s; }
        if (unresolvedOf(c, "cancel").length) {
          c.notice = "Une demande d'annulation est déjà en cours ; elle n'est pas renvoyée.";
          return s;
        }
        if (!m || !(m.status === "RUNNING" || m.status === "BLOCKED") || m.cancelRequested) {
          c.notice = "Aucune annulation possible pour cet état de mission.";
          return s;
        }
        var ck = newKey(s);
        c.commands.push(newCommand("cancel", ck, s.sim.minute));
        c.outbox.push({ type: "CANCEL_REQUEST", key: ck, minute: s.sim.minute });
        return s;
      case "check-receipt": {
        // A receipt query reads; it never re-emits the command itself.
        var target = intent.key ? findCommand(c, intent.key)
          : c.commands.filter(function (x) { return x.phase === "unknown" || x.phase === "not-found"; })[0];
        if (!target || (target.phase !== "unknown" && target.phase !== "not-found")) return s;
        if (c.connection !== "online") { c.notice = "Hors ligne : le reçu sera consultable au retour de la connexion."; return s; }
        target.phase = "checking";
        c.outbox.push({ type: "RECEIPT_QUERY", key: target.key, minute: s.sim.minute });
        return s;
      }
      case "close-window":
        c.windowOpen = false; // closes the window only: no decision, no mission change
        return s;
      case "open-window":
        c.windowOpen = true;
        return s;
      case "open-decision":
        if (c.session !== "open") { c.notice = "Déverrouille la session Windows pour voir la décision."; return s; }
        c.windowOpen = true; c.view = "extended"; c.tab = "missions";
        return s;
      case "set-view":
        c.view = intent.view === "extended" ? "extended" : "compact";
        if (c.view === "compact") c.tab = "conversation";
        return s;
      case "set-tab":
        c.view = "extended"; c.tab = intent.tab;
        return s;
      case "toggle-silence":
        c.silence = !c.silence;
        return s;
      case "draft":
        c.draft = String(intent.text || "").slice(0, 2000);
        return s;
      case "send-chat":
        blocked = sendBlocker(s);
        if (blocked) { c.notice = blocked + " Ton brouillon reste ici."; return s; }
        if (!c.draft.trim()) return s;
        c.outbox.push({ type: "CHAT", text: c.draft, minute: s.sim.minute });
        c.messages.push({ from: "user", text: c.draft, minute: s.sim.minute, pending: true });
        c.draft = "";
        return s;
      case "open-reading":
        c.reading = { open: true, text: c.reading.text || "", reviewed: false };
        return s;
      case "close-reading":
        c.reading.open = false;
        return s;
      case "reading-text":
        c.reading.text = String(intent.text || "").slice(0, 8000);
        c.reading.reviewed = false; // any edit requires a new explicit review
        return s;
      case "reading-reviewed":
        c.reading.reviewed = Boolean(intent.value);
        return s;
      case "reading-send":
        blocked = sendBlocker(s);
        if (blocked) { c.notice = blocked; return s; }
        if (!c.reading.reviewed || !c.reading.text.trim()) {
          c.notice = "Relis le texte et coche la case avant l'envoi.";
          return s;
        }
        c.outbox.push({ type: "READ_SUBMIT", text: c.reading.text, provenance: "fourni par l'utilisateur",
          minute: s.sim.minute });
        c.reading = { open: false, text: "", reviewed: false };
        c.notice = "Texte envoyé tel qu'affiché, avec la provenance « fourni par toi ».";
        return s;
      // --- simulation bench only (not application controls) ---
      case "sim-disconnect":
        goOffline(c);
        return s;
      case "sim-reconnect":
        if (c.connection === "online") return s;
        c.connection = "online";
        c.outbox.push({ type: "SYNC", after: c.cursor, minute: s.sim.minute });
        return s;
      case "sim-mic":
        c.mic = c.mic === "on" ? "off" : "on";
        return s;
      case "sim-lock":
        c.session = c.session === "open" ? "locked" : "open";
        return s;
      case "sim-toast":
        pushToast(s, "decision");
        return s;
      default:
        return s;
    }
  }

  // ---- Notifications (simulated, never decide anything) -------------------------------------

  function maybeToast(state) {
    var m = state.client.mission;
    if (m && m.status === "BLOCKED" && m.proposal.status === "PENDING") pushToast(state, "decision");
  }

  function pushToast(state, kind) {
    var c = state.client;
    if (c.toasts.some(function (t) { return t.kind === kind && !t.dismissed; })) return;
    c.toasts.push({ kind: kind, silenced: c.silence, minute: state.sim.minute });
  }

  function toastText(state, toast) {
    var c = state.client;
    if (c.session !== "open") {
      return { title: "Eidolon", body: "Une décision attend. Déverrouille ta session pour la voir.", action: "Ouvrir pour décider" };
    }
    var m = c.mission;
    return { title: "Eidolon — une action attend ton accord",
      body: m ? m.title + " (" + m.proposal.target + ", simulé)" : "Une décision attend.", action: "Ouvrir pour décider" };
  }

  // ---- Presentation helpers -----------------------------------------------------------------

  function missionLabel(m) {
    if (!m) return { text: "Aucune mission", detail: "" };
    if (m.cancelRequested && (m.status === "BLOCKED" || m.status === "RUNNING")) {
      return { text: "Annulation demandée", detail: "Le serveur n'a pas encore confirmé l'arrêt." };
    }
    switch (m.status) {
      case "NEW": return { text: "Nouvelle", detail: "" };
      case "RUNNING": return { text: "En cours", detail: "Pas encore un succès." };
      case "BLOCKED":
        if (m.proposal.status === "PENDING") return { text: "À décider", detail: "Une décision explicite est nécessaire." };
        if (m.proposal.status === "APPROVED") return { text: "Bloquée — accord enregistré", detail: "Le serveur revérifie avant de lancer." };
        if (m.proposal.status === "REJECTED") return { text: "Bloquée — accord refusé", detail: "Rien n'a été exécuté." };
        if (m.proposal.status === "REVOKED") return { text: "Bloquée — accord révoqué", detail: "Rien ne sera lancé avec cet accord." };
        return { text: "Bloquée", detail: "" };
      case "REVIEW_REQUIRED": return { text: "Revue requise — effet à vérifier", detail: "Pas de nouvel essai automatique." };
      case "SUCCEEDED": return { text: "Réussie — résultat daté", detail: "Ne décrit pas l'état actuel du service." };
      case "FAILED": return { text: "Échouée", detail: "" };
      case "CANCELLED": return { text: "Annulée", detail: "N'établit pas l'absence de tout effet externe." };
      case "ABANDONED": return { text: "Abandonnée", detail: "" };
      default: return { text: m.status, detail: "" };
    }
  }

  var DECISION_LABELS = {
    PENDING: "Accord attendu",
    APPROVED: "Accord enregistré — pas encore exécuté",
    USED: "Accord consommé — ne peut plus être révoqué",
    REJECTED: "Accord refusé",
    REVOKED: "Accord révoqué"
  };

  var EFFECT_LABELS = {
    NOT_STARTED: "Aucune exécution commencée",
    UNKNOWN: "Effet inconnu",
    VERIFIED_PAST_EFFECT: "Effet vérifié à la date indiquée",
    RESULT_UNVERIFIED: "Résultat rapporté, non vérifié",
    NO_EFFECT_REPORTED: "Aucun effet rapporté",
    NOT_AUTHORIZED: "Non autorisé",
    INCONSISTENT_EVIDENCE: "Preuves incohérentes"
  };

  function commandLabel(command) {
    if (!command) return null;
    var what = { approve: "Accord", reject: "Refus", revoke: "Révocation", cancel: "Demande d'annulation" }[command.kind];
    switch (command.phase) {
      case "sending": return what + " : envoi en cours. Pas encore enregistré par le serveur.";
      case "acknowledged": return what + " : enregistré par le serveur (reçu " + command.receipt + ")"
        + (command.viaReceipt ? ", confirmé en consultant le reçu." : ".");
      case "unknown": return what + " : enregistrement à vérifier. L'accusé n'est pas arrivé ; rien n'a été renvoyé.";
      case "checking": return what + " : consultation du reçu en cours.";
      case "not-found": return what + " : reçu introuvable. Ce n'est pas la preuve que rien n'a eu lieu ; rien n'est renvoyé.";
      case "refused": return what + " : refusé par le serveur (proposition changée ou déjà décidée).";
      default: return null;
    }
  }

  // The eye combines what Core says with what this client observes locally.
  function eye(state) {
    var c = state.client, m = c.mission;
    if (c.connection !== "online") return { mode: "offline", label: "Injoignable", detail: "Dernières nouvelles " + clockLabel(c.lastContact) };
    if (c.mic === "on") return { mode: "listen", label: "À l'écoute", detail: "Capture micro locale active (simulée)" };
    if (c.silence) return { mode: "silence", label: "Silence", detail: "Aucune notification ; rien n'est accepté" };
    // Visual attention only: no state change, no sound, no resend.
    var uncertain = c.commands.filter(function (x) { return x.phase === "unknown" || x.phase === "not-found"; }).length;
    if (uncertain) return { mode: "attention", label: "Reçu à vérifier", detail: uncertain + (uncertain > 1 ? " demandes incertaines" : " demande incertaine") };
    if (m && m.status === "BLOCKED" && m.proposal.status === "PENDING") return { mode: "attention", label: "Attend ton accord", detail: "1 décision" };
    if (m && m.status === "REVIEW_REQUIRED") return { mode: "attention", label: "Revue à faire", detail: "Effet d'une tentative inconnu" };
    if (m && m.status === "RUNNING") return { mode: "work", label: "Au travail", detail: "Mission en cours observée" };
    return { mode: "idle", label: "En veille", detail: "Aucune mission active" };
  }

  // Indicators that must stay visible whatever the eye shows.
  function indicators(state) {
    var c = state.client, list = [];
    list.push(c.connection === "online"
      ? { id: "connection", text: "Connecté au serveur Eidolon", tone: "ok" }
      : { id: "connection", text: "Serveur Eidolon injoignable", tone: "warn" });
    if (c.mic === "on") list.push({ id: "mic", text: "Micro actif (local)", tone: "alert" });
    list.push({ id: "camera", text: "Caméra désactivée", tone: "neutral" });
    if (c.silence) list.push({ id: "silence", text: "Silence", tone: "neutral" });
    if (c.session !== "open") list.push({ id: "session", text: "Session verrouillée", tone: "neutral" });
    return list;
  }

  function nextServerStep(state) {
    var c = state.client, sim = state.sim, m = sim.mission;
    if (c.connection !== "online") return "Aucun événement ne peut atteindre ce client (hors ligne).";
    var pending = c.outbox.slice(sim.processed);
    if (pending.length) {
      var t = pending[0].type;
      if (t === "DECIDE" && sim.ackMode === "lost-once" && !sim.ackLost) return "Core enregistre la décision… et la connexion tombe avant l'accusé.";
      return { DECIDE: "Core traite la décision envoyée.", RECEIPT_QUERY: "Core répond à la consultation du reçu.",
        REVOKE: "Core traite la révocation.", CANCEL_REQUEST: "Core enregistre la demande d'annulation.",
        SYNC: "Core rejoue les événements manqués (avec un doublon volontaire).",
        SNAPSHOT_REQUEST: "Core envoie un nouvel état complet.",
        CHAT: "Core reçoit le message (aucune réponse générée dans ce prototype).",
        READ_SUBMIT: "Core reçoit le texte fourni (non traité dans ce prototype)." }[t];
    }
    if (m.proposal.status === "APPROVED" && m.status === "BLOCKED" && !m.cancelRequested) return "Core revérifie la condition et lance l'exécution simulée.";
    if (m.status === "RUNNING" && !m.cancelRequested) return "Core relit l'état du service et vérifie l'effet.";
    if (m.cancelRequested && m.status === "BLOCKED") return "Core clôt la mission annulée.";
    return "Rien à faire côté Core : il attend une décision ou une revue humaine.";
  }

  var api = {
    SCENARIOS: SCENARIOS, initialState: initialState, dispatch: dispatch, serverStep: serverStep,
    applyEvent: applyEvent, eye: eye, indicators: indicators, missionLabel: missionLabel,
    commandLabel: commandLabel, decisionBlocker: decisionBlocker, sendBlocker: sendBlocker,
    receiveReply: receiveReply, unresolvedCommands: function (state, family) { return unresolvedOf(state.client, family); },
    MAX_RESOLVED_COMMANDS: MAX_RESOLVED_COMMANDS,
    nextServerStep: nextServerStep, toastText: toastText, clockLabel: clockLabel,
    syntheticTime: syntheticTime, DECISION_LABELS: DECISION_LABELS, EFFECT_LABELS: EFFECT_LABELS
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonModel = api;
})(typeof window !== "undefined" ? window : this);
