/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : pairing.test.js
 * Description : Auto-open origin, frame and transient key lifecycle tests
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../src/pairing.rs'),'utf8');
const key='ecc_'+'A'.repeat(43);
const code=source.match(/const AUTO_OPEN: &str = r#"([\s\S]*?)"#;/)[1].replaceAll('__KEY__',key).replaceAll('__PORT__','8767');
function run({origin='http://127.0.0.1:8767',pathname='/',frame=false,ready='loading',throws=false}={}) {
  const input={value:''}, seen=[],listeners=[];
  const window={location:{origin,pathname},addEventListener:(name,fn,opts)=>listeners.push({name,fn,opts})};
  window.top=frame?{}:window;
  const doc={readyState:ready,getElementById:id=>id==='conv-key'?input:{dispatchEvent:()=>{seen.push(input.value);input.value='';if(throws)throw Error('fixture');}}};
  const context={window,document:doc,Event:class{}};
  vm.runInNewContext(code,context);
  return {input,seen,listeners,context};
}
test('G279: opens only after page handlers are ready, clears the key, does not export it',()=>{
 const h=run();assert.equal(h.seen.length,0);assert.equal(h.listeners[0].name,'load');assert.equal(h.listeners[0].opts.once,true);
 h.listeners[0].fn();assert.deepEqual(h.seen,[key]);assert.equal(h.input.value,'');
 h.listeners[0].fn();assert.equal(h.seen.length,1);assert.equal(h.context.key,undefined);
});
test('G279: another origin, port, path and subframe receive no auto-open',()=>{
 for(const options of [{origin:'https://example.test'},{origin:'http://127.0.0.1:9999'},{origin:'http://localhost:8767'},{pathname:'/app.js'},{frame:true}]){
  const h=run(options);assert.equal(h.listeners.length,0);assert.equal(h.seen.length,0);assert.equal(h.input.value,'');
 }
});
test('G279: submit failure still clears the transient input and consumes the key',()=>{
 const h=run({throws:true});assert.throws(()=>h.listeners[0].fn(),/fixture/);assert.equal(h.input.value,'');
 h.listeners[0].fn();assert.equal(h.seen.length,1);
});
