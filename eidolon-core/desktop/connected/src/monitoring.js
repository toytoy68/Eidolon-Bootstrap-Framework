/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : monitoring.js
 * Description : Tableau de bord machines : badge DARME avec périmètre et fraîcheur, cartes, suivi borné (G156, G158)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Reads GET /v1/monitor/status (Core relays it to eidolon-monitor) with the paired conversation key.
// Rules (docs/DASHBOARD-DEPLOYMENT.md §5): grey is never shown as secure, gold only means "every declared
// source answered" within a stated scope; freshness is always visible and stale data loses its colour;
// metrics follow eidolon-machine/1 (G161); absent ones are shown as absent, never invented (no GPU value);
// nothing is read before the user asks; one request at a time, every POLL_MS at most, paused while the tab is hidden, stopped after
// MAX_FAILURES failures in a row and at once when the conversation closes. The page text stays usable.
(function (root) {
  "use strict";
  var PROTOCOL = "eidolon-monitor/1";
  var POLL_MS = 10000, MAX_FAILURES = 3;
  var BADGES = {
    gold: { label: "Or", text: "Toutes les sources déclarées répondent. Périmètre limité : ce n'est pas une garantie de sécurité." },
    grey: { label: "Gris", text: "Visibilité partielle : des sources manquent. Ce n'est PAS un état sécurisé." },
    red: { label: "Rouge", text: "Alerte non acquittée." },
    blue: { label: "Bleu", text: "Intervention en cours." }
  };
  var STATES = { unavailable: "Indisponible", invalid: "Réponse invalide", stale: "Statut périmé" };
  var ERRORS = { UNAVAILABLE: "service DARME absent ou arrêté", PERMISSION_DENIED: "accès au statut refusé",
    TIMEOUT: "pas de réponse à temps", INVALID_REPLY: "réponse non reconnue", REPLY_TOO_LARGE: "réponse trop grande",
    CLOCK_SKEW: "horloge en avance : statut non fiable" };
  var SCOPES = { local_service_availability_and_journal_disk: "services locaux (systemd actif) et disque du journal" };

  function bytes(n) {
    var units = ["o", "Kio", "Mio", "Gio", "Tio"], i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
    return (i ? n.toFixed(1) : String(n)) + " " + units[i];
  }

  // One metric value as text; null is "indisponible", never zero.
  function metric(key, value) {
    if (value === null || value === undefined) return "indisponible";
    if (typeof value === "boolean") return value ? "oui" : "non";
    if (typeof value === "string") return value;
    if (/_bytes$/.test(key)) return bytes(value);
    if (/_percent$/.test(key)) return value.toFixed(1) + " %";
    return String(Math.round(value * 100) / 100);
  }

  function age(seconds) {
    if (seconds < 60) return seconds + " s";
    if (seconds < 3600) return Math.floor(seconds / 60) + " min";
    return Math.floor(seconds / 3600) + " h";
  }

  // Pure view model of one machine (tested without DOM).
  function describe(machine) {
    var d = machine.darme, out = { id: machine.id, label: machine.label, cls: "unknown", badge: "?", text: "",
      scope: null, freshness: null, services: [], metrics: [], metricsNote: null, measured: null };
    if (!d) {
      out.cls = "unknown"; out.badge = STATES[machine.state] || "Inconnu";
      out.text = ERRORS[machine.error] || "état inconnu";
      return out;
    }
    var b = BADGES[d.badge];
    out.scope = SCOPES[d.scope] || (d.scope ? d.scope : "périmètre non déclaré");
    out.freshness = "il y a " + age(d.age_seconds) + " (validité " + d.health_ttl_seconds + " s)";
    if (machine.state === "stale") {
      out.cls = "stale"; out.badge = STATES.stale;          // stale data loses its colour
      out.text = "Dernier badge connu : " + b.label + ". Il n'est plus à jour.";
    } else {
      out.cls = d.badge; out.badge = b.label; out.text = b.text;
      if (d.badge === "red" && d.unacknowledged_alerts !== null) out.text = d.unacknowledged_alerts + " alerte(s) non acquittée(s).";
    }
    if (!d.security_telemetry_installed) out.text += " Aucun collecteur de sécurité installé.";
    if (d.ingestion_paused) out.text += " Collecte suspendue.";
    Object.keys(d.sources).forEach(function (name) {
      var absent = name === "security-telemetry" && !d.security_telemetry_installed;
      out.services.push({ name: name, ok: d.sources[name], text: d.sources[name] ? "répond" : absent ? "non installé" : "ne répond pas" });
    });
    if (d.machine_error) out.metricsNote = "Mesures machine refusées (" + d.machine_error + ") : rien n'est affiché.";
    var m = machine.machine;
    if (m) {
      out.measured = "Mesures " + (m.stale ? "PÉRIMÉES, " : "") + "il y a " + age(m.age_seconds) + ".";
      out.metrics.push({ name: "CPU", text: m.cpu_percent === null ? "indisponible (premier sondage)" : metric("cpu_percent", m.cpu_percent) + " de " + m.cpu_count + " vCPU" });
      out.metrics.push({ name: "Charge 1/5/15 min", text: m.load_1_5_15 ? m.load_1_5_15.map(function (x) { return metric("load", x); }).join(" / ") : "indisponible" });
      out.metrics.push({ name: "Mémoire", text: m.memory ? bytes(m.memory.used_bytes) + " utilisés sur " + bytes(m.memory.total_bytes) : "indisponible" });
      out.metrics.push({ name: "Swap", text: m.swap ? (m.swap.total_bytes ? bytes(m.swap.used_bytes) + " utilisés sur " + bytes(m.swap.total_bytes) : "aucun") : "indisponible" });
      out.metrics.push({ name: "Disque du journal", text: m.disk ? bytes(m.disk.free_bytes) + " libres sur " + bytes(m.disk.total_bytes) : "indisponible" });
      out.metrics.push({ name: "GPU", text: "non sondé sur cette machine" });
      if (m.errors.length) out.metricsNote = "Mesures manquantes : " + m.errors.join(", ") + ".";
    } else if (!out.metricsNote) out.metricsNote = "Mesures CPU, charge, mémoire, swap et disque : pas publiées par DARME sur cette machine.";
    return out;
  }

  function createMonitoring(deps) {
    var timers = deps.timers || { set: setTimeout, clear: clearTimeout };
    var onChange = deps.onChange || function () {};
    var state = { phase: "off", error: null, data: null, failures: 0, polling: false };
    var timer = null, inFlight = false, epoch = 0, hidden = false;

    function emit() { onChange(JSON.parse(JSON.stringify(state))); }
    function cancelTimer() { if (timer !== null) { timers.clear(timer); timer = null; } }
    function schedule() {
      cancelTimer();
      if (state.polling && !hidden && state.phase !== "off") timer = timers.set(tick, POLL_MS);
    }

    function fail(code) {
      state.failures += 1; state.error = code;
      state.phase = state.data ? "ok" : "error";             // keep the last data, marked by the error line
      if (state.failures >= MAX_FAILURES) { state.polling = false; state.error = code + "_STOPPED"; }
    }

    function tick() {
      timer = null;
      var key = deps.key();
      if (!key) { stop(); return Promise.resolve(false); }
      if (inFlight) return Promise.resolve(false);
      inFlight = true;
      var mine = epoch;
      if (!state.data) { state.phase = "loading"; emit(); }
      return deps.transport("GET", "/v1/monitor/status", undefined, key).then(function (r) {
        if (mine !== epoch) return false;
        var json = r && r.json;
        if (!json || json.protocol !== PROTOCOL) {           // Core without --monitor-port
          state.phase = "not_enabled"; state.polling = false; state.data = null; state.error = null;
        } else if (r.status !== 200) {
          fail(json.error || "HTTP_" + r.status);
          if (r.status === 401 || r.status === 403) { state.polling = false; state.data = null; state.phase = "error"; }
        } else {
          state.phase = "ok"; state.error = null; state.failures = 0; state.data = json;
        }
        return true;
      }, function () {
        if (mine !== epoch) return false;
        fail("MONITOR_UNREACHABLE");
        return true;
      }).then(function (changed) {
        if (mine !== epoch) return false;
        inFlight = false;
        emit(); schedule();
        return changed;
      });
    }

    // Conversation opened: the panel appears, nothing is read until the user asks (no request at load).
    function ready() {
      if (!deps.key() || state.phase !== "off") return false;
      state.phase = "idle"; emit();
      return true;
    }

    function start() {
      if (!deps.key()) return false;
      epoch += 1; inFlight = false; cancelTimer();
      state.phase = state.data ? "ok" : "loading"; state.polling = true; state.failures = 0; state.error = null;
      tick();
      return true;
    }

    // Conversation closed or page left: nothing kept, nothing pending.
    function stop() {
      epoch += 1; inFlight = false; cancelTimer();
      state = { phase: "off", error: null, data: null, failures: 0, polling: false };
      emit();
    }

    function pause(polling) {
      if (polling) return start();
      state.polling = false; cancelTimer(); emit();
      return true;
    }

    function visibility(isHidden) {
      hidden = !!isHidden;
      if (hidden) cancelTimer();
      else if (state.polling && timer === null && !inFlight) tick();
    }

    return { ready: ready, start: start, stop: stop, pause: pause, refresh: function () {
      if (!deps.key()) return Promise.resolve(false);
      if (state.phase === "not_enabled" || state.phase === "off" || state.phase === "idle") state.failures = 0;
      cancelTimer(); return tick();
    },
      visibility: visibility, state: function () { return JSON.parse(JSON.stringify(state)); } };
  }

  function el(doc, tag, cls, text) {
    var node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render(doc, st) {
    var section = doc.getElementById("monitor");
    if (!section) return;
    section.hidden = st.phase === "off";
    var status = doc.getElementById("monitor-status"), list = doc.getElementById("monitor-machines");
    doc.getElementById("monitor-auto").checked = st.polling;
    doc.getElementById("monitor-refresh").textContent = st.data ? "Actualiser" : "Afficher l'état des machines";
    var line = st.phase === "idle" ? "Rien n'est lu tant que vous ne le demandez pas." :
      st.phase === "loading" ? "Lecture de l'état des machines…" :
      st.phase === "not_enabled" ? "Surveillance non activée sur ce serveur (Core sans --monitor-port). La conversation reste utilisable." :
      st.phase === "error" ? "État des machines indisponible (" + (st.error || "erreur") + "). La conversation reste utilisable." :
      st.phase === "ok" ? (st.error ? "Dernière lecture en échec (" + st.error + ") : données affichées possiblement anciennes." :
        "Lu à " + new Date(st.data.generated_at).toLocaleTimeString("fr-FR") + (st.polling ? ", actualisé toutes les 10 s." : ", actualisation en pause.")) : "";
    status.textContent = line;
    while (list.firstChild) list.removeChild(list.firstChild);
    if (!st.data) return;
    st.data.machines.forEach(function (machine) {
      var v = describe(machine), card = el(doc, "li", "monitor-card");
      var head = el(doc, "div", "monitor-head");
      head.appendChild(el(doc, "h3", null, v.label));
      head.appendChild(el(doc, "span", "monitor-badge badge-" + v.cls, v.badge));
      card.appendChild(head);
      card.appendChild(el(doc, "p", "monitor-text", v.text));
      if (v.scope) card.appendChild(el(doc, "p", "help", "Périmètre : " + v.scope + "."));
      if (v.freshness) card.appendChild(el(doc, "p", "help", "Statut DARME " + v.freshness + "."));
      if (v.services.length) {
        var services = el(doc, "ul", "monitor-services");
        v.services.forEach(function (s) { services.appendChild(el(doc, "li", s.ok ? "ok" : "ko", s.name + " : " + s.text)); });
        card.appendChild(services);
      }
      if (v.measured) card.appendChild(el(doc, "p", "help", v.measured));
      if (v.metrics.length) {
        var metrics = el(doc, "dl", "monitor-metrics");
        v.metrics.forEach(function (m) { metrics.appendChild(el(doc, "dt", null, m.name)); metrics.appendChild(el(doc, "dd", null, m.text)); });
        card.appendChild(metrics);
      } else if (v.metricsNote) card.appendChild(el(doc, "p", "help", v.metricsNote));
      list.appendChild(card);
    });
    st.data.not_covered.forEach(function (name) {
      var card = el(doc, "li", "monitor-card");
      var head = el(doc, "div", "monitor-head");
      head.appendChild(el(doc, "h3", null, name));
      head.appendChild(el(doc, "span", "monitor-badge badge-unknown", "Non surveillé"));
      card.appendChild(head);
      card.appendChild(el(doc, "p", "help", "Aucune sonde sur cette machine depuis ce tableau de bord : aucune mesure affichée."));
      list.appendChild(card);
    });
  }

  function mount(doc, monitoring) {
    doc.getElementById("monitor-refresh").addEventListener("click", function () { monitoring.refresh(); });
    doc.getElementById("monitor-auto").addEventListener("change", function (event) { monitoring.pause(event.target.checked); });
    render(doc, monitoring.state());
    return { render: function (st) { render(doc, st); } };
  }

  var api = { createMonitoring: createMonitoring, describe: describe, metric: metric, render: render, mount: mount,
    BADGES: BADGES, POLL_MS: POLL_MS, MAX_FAILURES: MAX_FAILURES };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonMonitoring = api;
})(typeof window !== "undefined" ? window : this);
