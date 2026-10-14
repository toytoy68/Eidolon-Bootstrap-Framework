/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : enrolment.js
 * Description : Parcours simulés G170-E : enrôlement voix/visage, effacement, réenregistrement, affichage des propositions
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// SIMULATION ONLY (G183, C156-Q3). No microphone, camera, network, route or server storage is used or announced:
// a "sample" is a scripted description { duration_s, quality }, never audio or an image. Nothing here grants a
// right: every view carries simulated: true and grants: []. A recognition is shown as a SUGGESTION; switching
// profile stays the manual connection (G170-B, Codex).
(function (root) {
  "use strict";
  var MODALITIES = { voice: "voix", face: "visage" };
  var SAMPLES = 3;                                     // proposal of G170-C/D §4, to be confirmed by G170-F
  var VOICE_SECONDS = [5, 8];
  var PROMPTS = {
    voice: ["Lis à voix normale : « Bonjour Eidolon, voici ma première phrase d'enregistrement. »",
      "Lis : « Le chat dort près de la fenêtre pendant que la pluie tombe. »",
      "Lis : « Je compte jusqu'à dix : un, deux, trois, quatre, cinq, six, sept, huit, neuf, dix. »"],
    face: ["Regarde la caméra, de face, éclairage normal.", "Toujours de face, à une distance un peu plus grande.",
      "De face, sans lunettes de soleil ni masque."]
  };
  var QUALITY = {
    ok: null,
    too_short: "Prise trop courte : il faut entre 5 et 8 secondes de parole.",
    too_long: "Prise trop longue : il faut entre 5 et 8 secondes de parole.",
    silence: "Rien n'a été entendu (estimation par le volume). Recommence.",
    several_people: "Plusieurs personnes détectées : une seule personne à la fois.",
    no_face: "Aucun visage détecté. Place-toi face à la caméra.",
    blurred: "Image floue ou trop sombre. Recommence."
  };
  var PROPOSAL_TEXT = {
    known: null,
    ambiguous: "Doute entre plusieurs profils : aucune suggestion.",
    unknown: "Personne non reconnue : aucune suggestion.",
    uncalibrated: "Reconnaissance non calibrée : aucune suggestion tant que les seuils ne sont pas mesurés.",
    stale: "Observation périmée : aucune suggestion.",
    unavailable: "Reconnaissance indisponible.",
    not_enrolled: "Aucun profil enregistré pour cette modalité.",
    too_short: "Pas assez de parole pour reconnaître.",
    silence: "Rien n'a été entendu.",
    several_people: "Plusieurs personnes : aucune suggestion.",
    no_face: "Aucun visage visible."
  };

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function profile(p) {
    return { profile_id: p.profile_id, display_name: p.display_name, confirmed: p.confirmed === true,
      voice: "not_enrolled", face: "not_enrolled" };
  }

  // Simulated profiles: invented, confirmed only when the fixture says so (G170-A is Codex's server).
  function create(profiles) {
    return { simulated: true, grants: [], profiles: (profiles || []).map(profile), flow: { step: "idle" }, log: [] };
  }

  function find(state, id) {
    for (var i = 0; i < state.profiles.length; i++) if (state.profiles[i].profile_id === id) return state.profiles[i];
    return null;
  }

  function refuse(state, code) {
    var next = clone(state);
    next.flow = Object.assign({}, state.flow, { error: code });
    return next;
  }

  // Every transition returns a NEW state; an invalid action is refused with a code, never applied.
  function act(state, action) {
    var next = clone(state), flow = state.flow, p;
    delete next.flow.error;
    switch (action.type) {
      case "begin":                                      // choose a profile and a modality
        if (flow.step !== "idle") return refuse(state, "FLOW_BUSY");
        p = find(next, action.profile_id);
        if (!p) return refuse(state, "PROFILE_UNKNOWN");
        if (!p.confirmed) return refuse(state, "PROFILE_NOT_CONFIRMED");
        if (!MODALITIES[action.modality]) return refuse(state, "MODALITY_UNKNOWN");
        if (p[action.modality] === "enrolled") return refuse(state, "ALREADY_ENROLLED_DELETE_FIRST");
        next.flow = { step: "consent", profile_id: p.profile_id, modality: action.modality, accepted: false, samples: [] };
        return next;
      case "consent":
        if (flow.step !== "consent") return refuse(state, "NOT_IN_CONSENT");
        if (action.present !== true || action.agree !== true) return refuse(state, "CONSENT_INCOMPLETE");
        next.flow.step = "ready";
        next.flow.accepted = true;
        return next;
      case "start":
        if (flow.step !== "ready") return refuse(state, "NOT_READY");
        next.flow.step = "capturing";                    // the indicator is ON only in this step
        return next;
      case "finish":                                     // a scripted sample: { duration_s, quality }
        if (flow.step !== "capturing") return refuse(state, "NOT_CAPTURING");
        var sample = action.sample || {};
        var quality = sample.quality || "ok";
        if (!(quality in QUALITY)) return refuse(state, "QUALITY_UNKNOWN");
        if (flow.modality === "voice" && quality === "ok") {
          var d = sample.duration_s;
          if (typeof d !== "number" || !isFinite(d)) quality = "too_short";
          else if (d < VOICE_SECONDS[0]) quality = "too_short";
          else if (d > VOICE_SECONDS[1]) quality = "too_long";
        }
        if ((flow.modality === "voice" && (quality === "no_face" || quality === "blurred"))
            || (flow.modality === "face" && (quality === "silence" || quality === "too_short" || quality === "too_long"))) {
          return refuse(state, "QUALITY_NOT_FOR_MODALITY");
        }
        if (quality !== "ok") { next.flow.step = "ready"; next.flow.retry = quality; return next; }
        delete next.flow.retry;
        next.flow.samples.push({ index: flow.samples.length + 1, simulated: true });   // metadata only
        next.flow.step = next.flow.samples.length >= SAMPLES ? "review" : "ready";
        return next;
      case "stop":                                       // always available while a flow is open
      case "cancel":
        if (flow.step === "idle") return refuse(state, "NOTHING_TO_CANCEL");
        if (flow.step === "confirm_delete") {
          next.flow = { step: "idle", notice: "Effacement annulé : rien n'a changé." };
          return next;
        }
        next.log.push({ event: "cancelled", modality: flow.modality, discarded: flow.samples.length });
        next.flow = { step: "idle", notice: "Annulé : les prises de cette séance sont effacées (simulation)." };
        return next;
      case "confirm":
        if (flow.step !== "review") return refuse(state, "NOT_IN_REVIEW");
        p = find(next, flow.profile_id);
        p[flow.modality] = "enrolled";
        next.log.push({ event: "enrolled", modality: flow.modality, discarded: flow.samples.length });
        next.flow = { step: "idle", notice: "Enregistré (simulation) : le serveur calculerait les gabarits puis "
          + "effacerait les prises. Aucun droit n'est donné." };
        return next;
      case "ask_delete":
        if (flow.step !== "idle") return refuse(state, "FLOW_BUSY");
        p = find(next, action.profile_id);
        if (!p || !MODALITIES[action.modality]) return refuse(state, "PROFILE_UNKNOWN");
        if (p[action.modality] !== "enrolled") return refuse(state, "NOTHING_TO_DELETE");
        next.flow = { step: "confirm_delete", profile_id: p.profile_id, modality: action.modality };
        return next;
      case "delete":
        if (flow.step !== "confirm_delete") return refuse(state, "NOT_CONFIRMING_DELETE");
        find(next, flow.profile_id)[flow.modality] = "not_enrolled";
        next.log.push({ event: "deleted", modality: flow.modality });
        next.flow = { step: "idle", notice: "Effacé (simulation). Un serveur réel devra prouver l'effacement." };
        return next;
      default:
        return refuse(state, "ACTION_UNKNOWN");
    }
  }

  // What the screen shows for the current flow; the capture indicator follows the step, never a promise.
  function view(state) {
    var flow = state.flow, p = flow.profile_id ? find(state, flow.profile_id) : null;
    var m = flow.modality, out = { simulated: true, grants: [], step: flow.step, indicator: flow.step === "capturing",
      stop_available: flow.step !== "idle", title: "", text: "", actions: [] };
    if (flow.step === "idle") {
      out.title = "Enregistrement (simulation)";
      out.text = flow.notice || "Choisis un profil confirmé et une modalité.";
      out.actions = ["begin", "ask_delete"];
    } else if (flow.step === "consent") {
      out.title = "Enregistrer la " + MODALITIES[m] + " de " + p.display_name;
      out.text = "La personne doit être présente et d'accord. " + SAMPLES + " prises "
        + (m === "voice" ? "de 5 à 8 secondes" : "de face") + ". Seuls des gabarits seraient gardés ; les prises "
        + "brutes seraient effacées. L'enregistrement ne donne aucun droit et peut être effacé.";
      out.actions = ["consent", "cancel"];
    } else if (flow.step === "ready") {
      out.title = "Prise " + (flow.samples.length + 1) + " sur " + SAMPLES;
      out.text = (flow.retry ? QUALITY[flow.retry] + " " : "") + PROMPTS[m][flow.samples.length];
      out.actions = ["start", "cancel"];
    } else if (flow.step === "capturing") {
      out.title = (m === "voice" ? "Micro actif" : "Caméra active") + " (simulation)";
      out.text = "Capture en cours. « Arrêter » efface les prises de cette séance.";
      out.actions = ["finish", "stop"];
    } else if (flow.step === "review") {
      out.title = SAMPLES + " prises valides";
      out.text = "Confirmer l'enregistrement de la " + MODALITIES[m] + " de " + p.display_name + " ?";
      out.actions = ["confirm", "cancel"];
    } else if (flow.step === "confirm_delete") {
      out.title = "Effacer la " + MODALITIES[m] + " de " + p.display_name + " ?";
      out.text = "Les gabarits seraient supprimés. Il faudra réenregistrer pour une nouvelle suggestion.";
      out.actions = ["delete", "cancel"];
    }
    if (flow.error) out.error = flow.error;
    return out;
  }

  // An eidolon-identity-proposal/1 (or fused) result shown as a suggestion. Candidates are never listed.
  function proposalView(proposal, profiles) {
    var state = proposal && proposal.state;
    var base = { simulated: true, grants: [], suggestion: null, switch_profile: "manual_connection_only" };
    if (!proposal || proposal.schema !== "eidolon-identity-proposal/1" || !(state in PROPOSAL_TEXT)
        || proposal.authorizes_execution !== false || !Array.isArray(proposal.grants) || proposal.grants.length) {
      return Object.assign(base, { text: "Proposition illisible : ignorée." });
    }
    if (state === "known") {
      var p = null;
      (profiles || []).forEach(function (q) { if (q.profile_id === proposal.profile_id && q.confirmed) p = q; });
      if (!p) return Object.assign(base, { text: "Profil suggéré inconnu ou non confirmé : ignoré." });
      var basis = proposal.modality === "fused" ? (proposal.basis || []).map(function (b) { return MODALITIES[b]; })
        : [MODALITIES[proposal.modality]];
      return Object.assign(base, { suggestion: p.display_name,
        text: "Suggestion : " + p.display_name + " (" + basis.join(" et ") + ", non vérifié). "
          + "Pour changer de profil, utilise la connexion manuelle." });
    }
    return Object.assign(base, { text: PROPOSAL_TEXT[state] });
  }

  var api = { create: create, act: act, view: view, proposalView: proposalView, SAMPLES: SAMPLES,
    MODALITIES: MODALITIES };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EidolonEnrolmentSim = api;
})(typeof window !== "undefined" ? window : this);
