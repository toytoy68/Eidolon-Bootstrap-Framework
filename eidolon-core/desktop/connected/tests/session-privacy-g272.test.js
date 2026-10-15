/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : session-privacy-g272.test.js
 * Description : Captures et réponses tardives lors de fermeture de profil
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
const test=require('node:test'), assert=require('node:assert/strict');
const M=require('../src/communication.js');
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};}
function fixture(){
  const sent=[],tracks=[], gate={};
  let key='old-key';
  const deps={key:()=>key,media:{enumerateDevices:async()=>[{kind:'audioinput',deviceId:'mic'},{kind:'videoinput',deviceId:'cam'}],
    getUserMedia:async()=>{if(gate.permission)await gate.permission.promise;const t={stopped:false,stop(){this.stopped=true;}};tracks.push(t);return {getTracks:()=>[t]};}},
    recorder:()=>({cancel(){},stop:async()=>{if(gate.audio)await gate.audio.promise;return {samples:new Float32Array(16000),rate:16000};}}),
    grabFrame:async()=>{if(gate.frame)await gate.frame.promise;return new Uint8Array([1,2,3]);},
    transport:async(method,path,body,token)=>{sent.push({method,path,token});if(gate.response)await gate.response.promise;return {status:200,json:{text:'private',present:true,wav_base64:'x',index:0,chunks:1}};},
    player:()=>({done:Promise.resolve(),stop(){}}),setTimeout:()=>1,clearTimeout(){}};
  return {comm:M.createCommunication(deps),sent,tracks,gate,changeKey(){key='new-key';}};
}
test('pending permission cannot reactivate a closed microphone',async()=>{
  const f=fixture();await f.comm.refresh();f.gate.permission=deferred();
  const pending=f.comm.enable('microphone');f.comm.reset();f.changeKey();f.gate.permission.resolve();await pending;
  assert.equal(f.comm.state().microphone.state,'disabled');assert.ok(f.tracks.every(t=>t.stopped));
});
test('pending microphone acquisition is dropped on session reset',async()=>{
  const f=fixture();await f.comm.refresh();await f.comm.enable('microphone');f.gate.permission=deferred();
  const pending=f.comm.startTalk();f.comm.reset();f.gate.permission.resolve();assert.equal(await pending,false);
  assert.ok(f.tracks.every(t=>t.stopped));assert.equal(f.sent.length,0);
});
test('encoded microphone audio never goes out under the replacement key',async()=>{
  const f=fixture();await f.comm.refresh();await f.comm.enable('microphone');await f.comm.startTalk();f.gate.audio=deferred();
  const pending=f.comm.stopTalk();f.comm.reset();f.changeKey();f.gate.audio.resolve();assert.equal(await pending,null);
  assert.equal(f.sent.length,0);assert.ok(f.tracks.every(t=>t.stopped));
});
test('camera frame pending at close is discarded without upload',async()=>{
  const f=fixture();await f.comm.refresh();await f.comm.enable('camera');f.gate.frame=deferred();
  const pending=f.comm.snapshot('scene');await Promise.resolve();f.comm.reset();f.changeKey();
  assert.ok(f.tracks.every(t=>t.stopped));f.gate.frame.resolve();assert.equal(await pending,null);
  assert.equal(f.sent.length,0);assert.equal(f.comm.state().camera.state,'disabled');
});
test('late vision result cannot appear in a new profile',async()=>{
  const f=fixture();await f.comm.refresh();await f.comm.enable('camera');f.gate.response=deferred();
  const pending=f.comm.snapshot('scene');await Promise.resolve();await Promise.resolve();await Promise.resolve();
  f.comm.reset();f.changeKey();f.gate.response.resolve();assert.equal(await pending,null);
  assert.ok(f.sent.every(r=>r.token==='old-key'));assert.equal(f.comm.state().camera.state,'disabled');
});
