// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : probe-command.cjs
// Description : Reproduction de la perte du suivi d'une commande incertaine
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
const assert = require('node:assert/strict');
const M = require('../../../../desktop/prototype/model.js');
const results = [];
for (const intent of ['revoke', 'request-cancel']) {
  let state = M.serverStep(M.dispatch(M.initialState('accuse-perdu'), {type: 'approve'}));
  state = M.serverStep(M.dispatch(state, {type: 'sim-reconnect'}));
  const before = {...state.client.command};
  assert.equal(before.phase, 'unknown');
  state = M.dispatch(state, {type: intent});
  assert.notEqual(state.client.command.key, before.key);
  assert.equal(state.client.command.phase, 'sending');
  assert.equal(state.client.decisionHistory.some(entry => entry.key === before.key), false);
  results.push({intent, before, after: state.client.command, outbox: state.client.outbox.map(x => x.type)});
}
console.log(JSON.stringify({source: 'Claude 111da40', node: process.version,
  scope: 'simulation pure, aucun réseau ni effet réel', results}, null, 2));
