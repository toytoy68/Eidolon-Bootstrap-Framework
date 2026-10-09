/* Eidolon Core — ECT. Revue Codex de la réponse d'annulation tardive, transport synthétique. */
'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const C = require(path.resolve(__dirname, '../../../../desktop/connected/src/conversation.js'));
const ids = { a: 'm-' + '1'.repeat(32), b: 'm-' + '2'.repeat(32) };
const ok = json => ({status:200,json});
let release;
const oldResponse = new Promise(resolve => { release = resolve; });
const transport = async (_method, route, data) => {
  if (route.endsWith('/open')) return ok({conversation_id:'c-'+'3'.repeat(32),client_id:'fixture',actor:'fixture',store_id:'s-'+'4'.repeat(32)});
  if (route.endsWith('/recent')) return ok({conversations:[]});
  if (route.endsWith('/cancel_proposal')) {
    const proposal = {mission_id: data.mission_id};
    return ok({kind:'PROPOSAL', proposal, proposal_sha256:await C.digest(proposal), mission_status:'RUNNING'});
  }
  if (route.endsWith('/cancel')) return oldResponse;
  throw Error(route);
};
(async () => {
  const conversation = C.createConversation({transport});
  await conversation.open('ecc_' + 'A'.repeat(43));
  await conversation.cancelPropose(ids.a);
  const pending = conversation.cancelSubmit('Arrêter A');
  await conversation.cancelPropose(ids.b);
  assert.equal(conversation.state().cancel.proposal.mission_id, ids.b);
  release(ok({mission_id:ids.a,stage:'effect_observed',mission_status:'CANCELLED'}));
  await pending;
  const state=conversation.state().cancel;
  assert.equal(state.proposal.mission_id, ids.b);
  assert.equal(state.receipt.mission_id, ids.a);
  assert.equal(state.stage,'effect_observed');
  console.log(JSON.stringify({status:'FINDING_REPRODUCED',source:'C122/0a3a2e5',id:'G124-R1',
    displayed_target:state.proposal.mission_id,receipt_target:state.receipt.mission_id,
    displayed_status:C.cancelStatusText(state),real_server:false,mission_changed:false},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
