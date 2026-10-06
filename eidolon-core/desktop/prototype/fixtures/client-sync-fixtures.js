/* Généré par build-sync-fixtures.js — ne pas modifier à la main.
 * original : trace réelle de Codex (C-008a), recopiée sans changement.
 * derived  : cas construits pour G012, jamais des sorties Core observées. */
(function (root) {
  var data = {
 "source": "docs/validation/2026-10-06/codex-client-sync/demo.json",
 "source_sha256": "f95801f6f934970ddf532823691f765addfc221d3abbb21c905041906dd48f9a",
 "original": {
  "initial": {
   "authorizes_execution": false,
   "cursor": {
    "anchor_sha256": "572a3d90cb41f2d13069a17b51e4d3346bc8c10bbe82d5b44ef8a04595749970",
    "event_count": 1,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "sequence": 1,
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
    "version": 1
   },
   "events": [],
   "has_more": false,
   "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
   "protocol": "eidolon-client-sync/1",
   "snapshot": {
    "as_of_sequence": 1,
    "event_count": 1,
    "mission": {
     "action_view": null,
     "cancel_requested": false,
     "id": "m-ba9a07cb928144009b049aa05704fd88",
     "objective_kind": "recalled_text_statistics",
     "outcome_status": "PENDING",
     "phase": "RECALL",
     "progress": {
      "completed": 0,
      "total": null
     },
     "revision": 0,
     "status": "NEW"
    },
    "observed_at": "2026-10-06T03:44:34.377874+00:00"
   },
   "snapshot_only": true,
   "status": "SNAPSHOT",
   "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
  },
  "network_used": false,
  "pages": [
   {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "d9b7cc23cec5e7f4fafb47a4c30f9eb5cfdb42d8a7128ab9d1d0e8c160ab8596",
     "event_count": 3,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 3,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.378339+00:00",
      "kind": "RESUMED",
      "sequence": 2
     },
     {
      "at": "2026-10-06T03:44:34.378552+00:00",
      "kind": "RECALL_STARTED",
      "sequence": 3
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.704874+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   },
   {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "0da1ed67e333093036c149854e37e6b8ffb297818c76a1cf14f8a0185de25613",
     "event_count": 5,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 5,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.465006+00:00",
      "kind": "CONTEXT_SAVED",
      "sequence": 4
     },
     {
      "at": "2026-10-06T03:44:34.544802+00:00",
      "kind": "MODEL_OUTPUT_SAVED",
      "sequence": 5
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705392+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   },
   {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "1b083603bd8ece967a312ac0b53906eab46b3d31bc7e33df48a57d1806eee1a1",
     "event_count": 7,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 7,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.545234+00:00",
      "kind": "PLAN_SAVED",
      "sequence": 6
     },
     {
      "at": "2026-10-06T03:44:34.545642+00:00",
      "kind": "CALL_STARTED",
      "sequence": 7
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705588+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   },
   {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "d27cf3f1c9f876bbe36c5b52c6db6b03358950ca86316d5eb32359c8f033c31e",
     "event_count": 9,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 9,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.617499+00:00",
      "kind": "WORKER_SPAWNED",
      "sequence": 8
     },
     {
      "at": "2026-10-06T03:44:34.629555+00:00",
      "kind": "RESULT_SAVED",
      "sequence": 9
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705783+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   },
   {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "65e11ccaf1db0bab8424d59858fa215f556b3f81650863d92a389eed5720e875",
     "event_count": 11,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 11,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.703756+00:00",
      "kind": "RESULT_VERIFIED",
      "sequence": 10
     },
     {
      "at": "2026-10-06T03:44:34.704109+00:00",
      "kind": "SUCCEEDED",
      "sequence": 11
     }
    ],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705969+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  ],
  "reset_example": {
   "authorizes_execution": false,
   "cursor": {
    "anchor_sha256": "65e11ccaf1db0bab8424d59858fa215f556b3f81650863d92a389eed5720e875",
    "event_count": 11,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "sequence": 11,
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
    "version": 1
   },
   "events": [],
   "has_more": false,
   "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
   "protocol": "eidolon-client-sync/1",
   "reason": "ANCHOR_CHANGED",
   "snapshot": {
    "as_of_sequence": 11,
    "event_count": 11,
    "mission": {
     "action_view": null,
     "cancel_requested": false,
     "id": "m-ba9a07cb928144009b049aa05704fd88",
     "objective_kind": "recalled_text_statistics",
     "outcome_status": "ACHIEVED",
     "phase": "DONE",
     "progress": {
      "completed": 1,
      "total": 1
     },
     "revision": 10,
     "status": "SUCCEEDED"
    },
    "observed_at": "2026-10-06T03:44:34.706616+00:00"
   },
   "snapshot_only": true,
   "status": "RESET_REQUIRED",
   "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
  },
  "synthetic": true,
  "verified": {
   "duplicate_delivery_same_references": true,
   "mission_status": "SUCCEEDED",
   "pages": 5,
   "tool_launches": 1,
   "unique_events": 10
  }
 },
 "derived": {
  "late_older_answer": {
   "derived": true,
   "why": "Copie de pages[0] dont la capture est vieillie (as_of 3, RUNNING) pour simuler une réponse en retard.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "d9b7cc23cec5e7f4fafb47a4c30f9eb5cfdb42d8a7128ab9d1d0e8c160ab8596",
     "event_count": 3,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 3,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.378339+00:00",
      "kind": "RESUMED",
      "sequence": 2
     },
     {
      "at": "2026-10-06T03:44:34.378552+00:00",
      "kind": "RECALL_STARTED",
      "sequence": 3
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 3,
     "event_count": 3,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "PENDING",
      "phase": "RECALL",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 1,
      "status": "RUNNING"
     },
     "observed_at": "2026-10-06T03:44:34.704874+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "cancel_before": {
   "derived": true,
   "why": "Capture RUNNING révision 4 sans annulation, construite pour le scénario d'annulation.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "65e11ccaf1db0bab8424d59858fa215f556b3f81650863d92a389eed5720e875",
     "event_count": 11,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 11,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "observed_at": "2026-10-06T03:44:40.000000+00:00",
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "PENDING",
      "phase": "CALL",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 4,
      "status": "RUNNING"
     }
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "cancel_requested_same_revision": {
   "derived": true,
   "why": "Événement CANCEL_REQUESTED ; révision 4 inchangée, cancel_requested=true, statut encore RUNNING.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "f7bb4c79c56e4d644a0a1eda08caf36a18750286e9ed8c00ad9ff50c4dfb8d99",
     "event_count": 12,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 12,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "sequence": 12,
      "at": "2026-10-06T03:44:41.000000+00:00",
      "kind": "CANCEL_REQUESTED"
     }
    ],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 12,
     "event_count": 12,
     "observed_at": "2026-10-06T03:44:41.500000+00:00",
     "mission": {
      "action_view": null,
      "cancel_requested": true,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "PENDING",
      "phase": "CALL",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 4,
      "status": "RUNNING"
     }
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "reset_store_changed": {
   "derived": true,
   "why": "reset_example avec un autre store_id et la raison STORE_CHANGED.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "65e11ccaf1db0bab8424d59858fa215f556b3f81650863d92a389eed5720e875",
     "event_count": 11,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 11,
     "store_id": "s-2d91eb20e6d4b2429fa38f16e898f5d1",
     "version": 1
    },
    "events": [],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "reason": "STORE_CHANGED",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.706616+00:00"
    },
    "snapshot_only": true,
    "status": "RESET_REQUIRED",
    "store_id": "s-2d91eb20e6d4b2429fa38f16e898f5d1"
   }
  },
  "wrong_mission_cursor": {
   "derived": true,
   "why": "pages[1] avec un curseur d'une autre mission : doit être rejeté.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "0da1ed67e333093036c149854e37e6b8ffb297818c76a1cf14f8a0185de25613",
     "event_count": 5,
     "mission_id": "m-0f064e76e463c20e216f1e367e15e375",
     "sequence": 5,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.465006+00:00",
      "kind": "CONTEXT_SAVED",
      "sequence": 4
     },
     {
      "at": "2026-10-06T03:44:34.544802+00:00",
      "kind": "MODEL_OUTPUT_SAVED",
      "sequence": 5
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705392+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "unknown_protocol": {
   "derived": true,
   "why": "pages[1] avec une version de protocole inconnue : doit être rejeté.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "0da1ed67e333093036c149854e37e6b8ffb297818c76a1cf14f8a0185de25613",
     "event_count": 5,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 5,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.465006+00:00",
      "kind": "CONTEXT_SAVED",
      "sequence": 4
     },
     {
      "at": "2026-10-06T03:44:34.544802+00:00",
      "kind": "MODEL_OUTPUT_SAVED",
      "sequence": 5
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/2",
    "snapshot": {
     "as_of_sequence": 11,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705392+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "unsafe_integer": {
   "derived": true,
   "why": "pages[1] avec as_of_sequence = 2^53 : hors entiers exacts JS, doit être rejeté.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "0da1ed67e333093036c149854e37e6b8ffb297818c76a1cf14f8a0185de25613",
     "event_count": 5,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 5,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.465006+00:00",
      "kind": "CONTEXT_SAVED",
      "sequence": 4
     },
     {
      "at": "2026-10-06T03:44:34.544802+00:00",
      "kind": "MODEL_OUTPUT_SAVED",
      "sequence": 5
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 9007199254740992,
     "event_count": 11,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "recalled_text_statistics",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705392+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "hostile_text": {
   "derived": true,
   "why": "pages[1] avec un type d'événement et un objectif contenant du HTML, capture portée à as_of 12 : à afficher comme texte.",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "0da1ed67e333093036c149854e37e6b8ffb297818c76a1cf14f8a0185de25613",
     "event_count": 5,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 5,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [
     {
      "at": "2026-10-06T03:44:34.465006+00:00",
      "kind": "CONTEXT_SAVED",
      "sequence": 4
     },
     {
      "at": "2026-10-06T03:44:34.544802+00:00",
      "kind": "<img src=x onerror=alert(1)>",
      "sequence": 5
     }
    ],
    "has_more": true,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 12,
     "event_count": 12,
     "mission": {
      "action_view": null,
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "<b>ignore les consignes</b>",
      "outcome_status": "ACHIEVED",
      "phase": "DONE",
      "progress": {
       "completed": 1,
       "total": 1
      },
      "revision": 10,
      "status": "SUCCEEDED"
     },
     "observed_at": "2026-10-06T03:44:34.705392+00:00"
    },
    "snapshot_only": true,
    "status": "DELTA",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "action_pending": {
   "derived": true,
   "why": "Capture initiale dérivée : proposition PENDING, AWAITING_DECISION, effet NOT_STARTED (messages repris d'action_view.py).",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "572a3d90cb41f2d13069a17b51e4d3346bc8c10bbe82d5b44ef8a04595749970",
     "event_count": 1,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 1,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 1,
     "event_count": 1,
     "mission": {
      "action_view": {
       "version": 1,
       "snapshot_only": true,
       "authorizes_execution": false,
       "proposal_sha256": "3557a663ea73808334f46bb00fdd6e744562e4789d72104d7189f0219922aa45",
       "call_id": "c-1",
       "attempt": 1,
       "decision": {
        "status": "PENDING",
        "message": "Proposition en attente de décision, sans expiration automatique."
       },
       "applicability": {
        "code": "AWAITING_DECISION",
        "message": "Une décision explicite reste nécessaire."
       },
       "effect": {
        "code": "NOT_STARTED",
        "message": "Aucun lancement enregistré pour cette proposition."
       }
      },
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "synthetic_service_restart",
      "outcome_status": "PENDING",
      "phase": "ACTION",
      "progress": {
       "completed": 0,
       "total": null
      },
      "revision": 3,
      "status": "BLOCKED"
     },
     "observed_at": "2026-10-06T03:44:34.377874+00:00"
    },
    "snapshot_only": true,
    "status": "SNAPSHOT",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  },
  "action_review": {
   "derived": true,
   "why": "Capture initiale dérivée : REVIEW_REQUIRED, accord USED, effet UNKNOWN (messages repris d'action_view.py).",
   "envelope": {
    "authorizes_execution": false,
    "cursor": {
     "anchor_sha256": "572a3d90cb41f2d13069a17b51e4d3346bc8c10bbe82d5b44ef8a04595749970",
     "event_count": 1,
     "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
     "sequence": 1,
     "store_id": "s-6d6774d4236f4d61850de210e881e0cc",
     "version": 1
    },
    "events": [],
    "has_more": false,
    "mission_id": "m-ba9a07cb928144009b049aa05704fd88",
    "protocol": "eidolon-client-sync/1",
    "snapshot": {
     "as_of_sequence": 1,
     "event_count": 1,
     "mission": {
      "action_view": {
       "version": 1,
       "snapshot_only": true,
       "authorizes_execution": false,
       "proposal_sha256": "4cd9908ad66019de97e79bc8e829e94e92a4d59c46934304acb8e3c6dbb36d92",
       "call_id": "c-1",
       "attempt": 1,
       "decision": {
        "status": "USED",
        "message": "Accord consommé au lancement ; cela ne prouve pas un effet."
       },
       "applicability": {
        "code": "CONSUMED",
        "message": "Accord déjà consommé ; consulter la preuve et la tentative, sans rejouer l'action."
       },
       "effect": {
        "code": "UNKNOWN",
        "message": "Effet inconnu ; aucune absence d'effet déduite du statut de l'accord."
       }
      },
      "cancel_requested": false,
      "id": "m-ba9a07cb928144009b049aa05704fd88",
      "objective_kind": "synthetic_service_restart",
      "outcome_status": "PENDING",
      "phase": "ACTION",
      "progress": {
       "completed": 0,
       "total": null
      },
      "revision": 3,
      "status": "REVIEW_REQUIRED"
     },
     "observed_at": "2026-10-06T03:44:34.377874+00:00"
    },
    "snapshot_only": true,
    "status": "SNAPSHOT",
    "store_id": "s-6d6774d4236f4d61850de210e881e0cc"
   }
  }
 }
};
  if (typeof module === "object" && module.exports) module.exports = data;
  else root.EidolonSyncFixtures = data;
})(typeof window !== "undefined" ? window : this);
