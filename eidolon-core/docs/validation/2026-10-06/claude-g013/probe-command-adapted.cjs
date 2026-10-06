// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : probe-command-adapted.cjs
// Description : Sonde Codex G013 rejouée sur la structure client.commands (C-TASK-G013)
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
// Same scenario as ../codex-g009-review/probe-command.cjs (unchanged), but the
// single client.command became client.commands (one entry per key), and the
// assertions now state the CORRECTED behaviour instead of the defect.
const assert = require('node:assert/strict');
const M = require('../../../../desktop/prototype/model.js');
const results = [];
for (const intent of ['revoke', 'request-cancel']) {
  let state = M.serverStep(M.dispatch(M.initialState('accuse-perdu'), {type: 'approve'}));
  state = M.serverStep(M.dispatch(state, {type: 'sim-reconnect'}));
  const before = {...state.client.commands.find(c => c.kind === 'approve')};
  assert.equal(before.phase, 'unknown');
  state = M.dispatch(state, {type: intent});
  const tracked = state.client.commands.find(c => c.key === before.key);
  assert.equal(tracked.phase, 'unknown', 'the uncertain approval is still tracked');
  assert.equal(state.client.commands.length, 2);
  state = M.serverStep(M.dispatch(M.serverStep(state), {type: 'check-receipt', key: before.key}));
  assert.equal(state.client.commands.find(c => c.key === before.key).phase, 'acknowledged');
  assert.equal(state.client.outbox.filter(x => x.type === 'DECIDE').length, 1);
  results.push({intent, commands: state.client.commands.map(c => ({kind: c.kind, key: c.key, phase: c.phase})),
    outbox: state.client.outbox.map(x => x.type)});
}
console.log(JSON.stringify({node: process.version, scope: 'simulation pure, aucun réseau ni effet réel', results}, null, 2));
