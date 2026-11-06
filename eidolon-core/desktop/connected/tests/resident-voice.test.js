/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : resident-voice.test.js
 * Description : Courses d'arrêt, propriété du micro et absence de rejeu vocal
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
const test = require('node:test');
const assert = require('node:assert/strict');
const {create} = require('../src/resident-voice.js');
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; }
function fixture(options={}) {
  const wakes=[], sessions=[], states=[];
  const deps={qualified:true,connected:()=>true,change:s=>states.push(s),
    waitWake:signal=>{ const d=deferred(); wakes.push({...d,signal}); return d.promise; },
    runSession:signal=>{ const d=deferred(); sessions.push({...d,signal}); return d.promise; }, ...options};
  const voice=create(deps); voice.consent(true);
  return {voice,wakes,sessions,states};
}
test('no consent or unqualified model never opens a microphone', async()=>{
  for (const qualified of [true,false]) {
    const f=fixture({qualified}); if(qualified) f.voice.consent(false);
    assert.equal(f.voice.start(),false); await tick(); assert.equal(f.wakes.length,0);
  }
});
test('wake starts one session; completion returns to local detection', async()=>{
  const f=fixture(); f.voice.start(); f.voice.start(); await tick();
  assert.equal(f.wakes.length,1); assert.equal(f.sessions.length,0);
  f.wakes[0].resolve(true); await tick(); assert.equal(f.sessions.length,1);
  assert.equal(f.voice.state(),'conversation');
  f.sessions[0].resolve(); await tick(); assert.equal(f.wakes.length,2);
  f.voice.stop(); f.wakes[1].resolve(true); await f.voice.settled();
  assert.equal(f.sessions.length,1); assert.equal(f.voice.state(),'off');
});
test('mute ignores a detection that arrives after cancellation', async()=>{
  const f=fixture(); f.voice.start(); await tick(); f.voice.stop();
  assert.equal(f.wakes[0].signal.aborted,true); assert.equal(f.voice.state(),'stopping');
  f.wakes[0].resolve(true); await f.voice.settled();
  assert.equal(f.sessions.length,0); assert.equal(f.voice.state(),'off');
});
test('rapid stop/start waits for old microphone release before reacquiring', async()=>{
  const f=fixture(); f.voice.start(); await tick(); f.voice.stop(); f.voice.start(); await tick();
  assert.equal(f.wakes.length,1); // old adapter has not released ownership yet
  f.wakes[0].resolve(true); await tick(); assert.equal(f.sessions.length,0); assert.equal(f.wakes.length,2);
  f.voice.stop(); f.wakes[1].resolve(true); await f.voice.settled();
});
test('network absence does not start or queue a voice conversation', async()=>{
  const f=fixture({connected:()=>false}); f.voice.start(); await tick(); f.wakes[0].resolve(true);
  await f.voice.settled(); assert.equal(f.sessions.length,0); assert.equal(f.voice.state(),'offline');
});
test('uncertain failed session is not replayed and does not reopen microphone', async()=>{
  const f=fixture(); f.voice.start(); await tick(); f.wakes[0].resolve(true); await tick();
  f.sessions[0].reject(new Error('private transcript must not enter diagnostics'));
  await f.voice.settled(); assert.equal(f.sessions.length,1); assert.equal(f.wakes.length,1);
  assert.equal(f.voice.state(),'error'); assert(!JSON.stringify(f.states).includes('private transcript'));
});
test('revoking consent aborts an active conversation and prevents another wake', async()=>{
  const f=fixture(); f.voice.start(); await tick(); f.wakes[0].resolve(true); await tick();
  f.voice.consent(false); assert.equal(f.sessions[0].signal.aborted,true);
  assert.equal(f.voice.start(),false); assert.equal(f.voice.state(),'stopping');
  f.sessions[0].resolve(); await f.voice.settled();
  assert.equal(f.voice.state(),'off'); assert.equal(f.voice.start(),false); assert.equal(f.wakes.length,1);
});
