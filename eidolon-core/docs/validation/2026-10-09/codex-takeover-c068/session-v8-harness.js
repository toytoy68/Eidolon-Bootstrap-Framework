/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : session-v8-harness.js
 * Description : Banc V8 des consommateurs de consultation sur transport scripté
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Test-only harness for a V8 isolate without Node. Never used by the application.
async function runScriptedTests(sources, testSource, testPath) {
 const cases=[],cache={};
 const norm=p=>{const out=[];for(const part of p.split("/")){if(part==="..")out.pop();else if(part&&part!==".")out.push(part);}return out.join("/");};
 const sort=v=>v&&typeof v==="object"?(Array.isArray(v)?v.map(sort):Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])]))):v;
 const assert={
  equal(a,b,m){if(a!==b)throw Error(m||("expected "+JSON.stringify(b)+" got "+JSON.stringify(a)));},
  deepEqual(a,b,m){if(JSON.stringify(sort(a))!==JSON.stringify(sort(b)))throw Error(m||("expected "+JSON.stringify(b)+" got "+JSON.stringify(a)));},
  ok(a,m){if(!a)throw Error(m||"expected truthy");},
  match(a,re,m){if(!re.test(a))throw Error(m||("no match "+re+": "+a));},
  doesNotMatch(a,re,m){if(re.test(a))throw Error(m||("unexpected match "+re+": "+a));},
  throws(fn,re){let err;try{fn();}catch(e){err=e;}if(!err)throw Error("expected throw");if(re&&!re.test(String(err)))throw err;}
 };
 function requireFrom(n,base){
  if(n==="node:test")return (name,fn)=>cases.push({name,fn});
  if(n==="node:assert/strict")return assert;
  if(!n.startsWith("."))throw Error("unsupported import "+n);
  const path=norm(base.split("/").slice(0,-1).join("/")+"/"+n);
  if(cache[path])return cache[path].exports;
  if(!sources[path])throw Error("missing module "+path);
  const mod={exports:{}};cache[path]=mod;
  new Function("module","require",sources[path])(mod,n=>requireFrom(n,path));
  return mod.exports;
 }
 new Function("require",testSource)(n=>requireFrom(n,testPath));
 const results=[];
 for(const t of cases){try{await t.fn();results.push({name:t.name,status:"PASS"});}catch(e){results.push({name:t.name,status:"FAIL",error:String(e)});}}
 return {runtime:"V8 isolate; minimal node:test/assert module loader; scripted transports, no Node or browser",passed:results.filter(x=>x.status==="PASS").length,failed:results.filter(x=>x.status==="FAIL").length,results};
}
if (typeof module === 'object') module.exports = runScriptedTests;
