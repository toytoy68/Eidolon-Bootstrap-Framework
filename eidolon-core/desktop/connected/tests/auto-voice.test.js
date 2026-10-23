/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : auto-voice.test.js
 * Description : Appels vocaux, segmentation et annulation des réponses tardives
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
const test = require('node:test'), assert = require('node:assert/strict');
const A = require('../src/auto-voice.js');
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture(segments, overrides={}) {
  const sent=[], spoken=[], states=[]; let auto, reads=0;
  const deps={prepare:async()=>{}, pause:async()=>{}, cancel:()=>{},
    change:(s,n)=>states.push([s,n]),
    listen:async()=>{reads++;if(!segments.length){auto.stop();return null;} return segments.shift();},
    speak:async t=>{spoken.push(t);return true;}, send:async t=>{sent.push(t);return 'Réponse';}, ...overrides};
  auto=A.create(deps);return {auto,sent,spoken,states,reads:()=>reads};
}
const phrase=text=>({text,empty:false});
test('single wake word Eidolon must lead the phrase',()=>{
 assert.equal(A.wake('Eidolon !'),'');assert.equal(A.wake('« Eidolon », quelle heure ?'),'quelle heure ?');
 assert.equal(A.wake('Eidolonique'),null);assert.equal(A.wake('je parle à Eidolon'),null);
});
test('G296 operator decision: « dis-moi » and its variants never wake Eidolon',()=>{
 for(const t of ['Dis-moi ?','Dis-moi ? quelle heure ?','dit moi, bonjour','dis moi Eidolon','DIS-MOI'])assert.equal(A.wake(t),null,t);
});
test('a « Dis-moi » command in standby is ignored, never sent',async()=>{
 const f=fixture([phrase('Dis-moi, quelle heure est-il ?'),phrase('dit moi bonjour')]);await f.auto.start();
 assert.deepEqual(f.sent,[]);assert.deepEqual(f.spoken,[]);
});
test('unrelated speech is ignored; greeting then command then standby, no repeat',async()=>{
 const f=fixture([phrase('bonjour personne'),phrase('Eidolon !'),phrase('Comment vas-tu ?')]);await f.auto.start();
 assert.deepEqual(f.sent,['Comment vas-tu ?']);assert.deepEqual(f.spoken,['Oui ?','Réponse']);assert.equal(f.auto.active(),false);
});
test('joined wake and command skips greeting and keeps full command',async()=>{
 const f=fixture([phrase('Eidolon, décris tes fonctionnalités')]);await f.auto.start();
 assert.deepEqual(f.sent,['décris tes fonctionnalités']);assert.deepEqual(f.spoken,['Réponse']);
});
test('silence after wake expires the armed state',async()=>{
 const f=fixture([phrase('Eidolon'),{empty:true,text:''},phrase('phrase sans appel')]);await f.auto.start();assert.deepEqual(f.sent,[]);
});
test('stop during recognition discards the late transcript',async()=>{
 let resolve;const f=fixture([], {listen:()=>new Promise(r=>resolve=r)});const run=f.auto.start();await tick();f.auto.stop();resolve(phrase('Eidolon, test'));await run;assert.deepEqual(f.sent,[]);
});
test('uncertain send stops the loop and is never retried',async()=>{
 let count=0;const f=fixture([phrase('Eidolon, test')],{send:async()=>{count++;throw Error('Envoi non confirmé');}});await f.auto.start();assert.equal(count,1);assert.equal(f.auto.active(),false);assert.match(f.states.at(-1)[1],/non confirmé/);
});
test('stop during reply discards speech and never reopens microphone',async()=>{
 let resolve;const f=fixture([phrase('Eidolon, test')],{send:()=>new Promise(r=>resolve=r)});const run=f.auto.start();await tick();f.auto.stop();resolve('late');await run;assert.deepEqual(f.spoken,[]);assert.equal(f.reads(),1);
});
test('double start does not create two listening loops',async()=>{
 let resolve;const f=fixture([],{listen:()=>new Promise(r=>resolve=r)});const run=f.auto.start();await tick();await f.auto.start();assert.equal(f.auto.active(),true);f.auto.stop();resolve(null);await run;
});
test('energy gate ignores silence and limits continuous speech without sending partial commands',()=>{
 const silent=new Float32Array(1600), voice=new Float32Array(1600).fill(.1);
 let g=A.createGate(), result;for(let i=0;i<100;i++)result=g.feed(silent,16000);assert.equal(result,'silence');
 g=A.createGate();for(let i=0;i<3;i++)g.feed(voice,16000);for(let i=0;i<14;i++)assert.equal(g.feed(silent,16000),null);assert.equal(g.feed(silent,16000),'speech');
 g=A.createGate();for(let i=0;i<280;i++)result=g.feed(voice,16000);assert.equal(result,'silence');
});


test('microphone stays closed while greeting is playing, then listens to the command', async()=>{
 let finish;const f=fixture([phrase('Eidolon')],{speak:()=>new Promise(r=>finish=r)});
 const run=f.auto.start();await tick();assert.equal(f.reads(),1);await tick();assert.equal(f.reads(),1);
 finish(true);await run;assert.equal(f.reads(),2);
});
