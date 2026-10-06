/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : probe-list.js
 * Description : Sonde indépendante de fin de pagination incohérente G018
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
const L = require('../../../../desktop/prototype/mission-list-state.js');
const F = require('../../../../desktop/prototype/fixtures/mission-list-fixtures.js');
const page = JSON.parse(JSON.stringify(F.observed.trace.fresh_pages[0]));
page.has_more = false;
page.next_cursor = null;
const state = L.receivePage(L.createState(), page, {epoch: 0, cursor: null});
console.log(JSON.stringify({case: 'terminal-page-shorter-than-announced',
  announced: page.generation.mission_count, received: state.items.length,
  complete: state.complete, summary: L.summary(state).status}));
