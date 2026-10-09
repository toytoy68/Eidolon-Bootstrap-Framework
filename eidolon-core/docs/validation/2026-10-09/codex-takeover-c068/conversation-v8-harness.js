/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : conversation-v8-harness.js
 * Description : Banc V8 de logique conversation, substituts Node réservés aux tests
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Test-only harness for a V8 isolate without Node. Never used by the application.
function runConversationTests(source, testsSource, fixture) {
  const failures = [], cases = [];
  const encoder = class { encode(s) {
    const raw = unescape(encodeURIComponent(s));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  }};
  function sha256(bytes) {
    const k = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const n = bytes.length, data = new Uint8Array(Math.ceil((n+9)/64)*64);
    data.set(bytes); data[n]=128;
    const v=new DataView(data.buffer);v.setUint32(data.length-8, Math.floor(n/0x20000000));v.setUint32(data.length-4,n*8);
    const rr=(x,s)=>(x>>>s)|(x<<(32-s));
    for(let off=0;off<data.length;off+=64){
      const w=new Uint32Array(64);
      for(let i=0;i<16;i++)w[i]=v.getUint32(off+i*4);
      for(let i=16;i<64;i++){
        const a=w[i-15],b=w[i-2];
        w[i]=(rr(a,7)^rr(a,18)^(a>>>3))+w[i-16]+(rr(b,17)^rr(b,19)^(b>>>10))+w[i-7];
      }
      let [a,b,c,d,e,f,g,z]=h;
      for(let i=0;i<64;i++){
        const t1=(z+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^(~e&g))+k[i]+w[i])|0;
        const t2=((rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c)))|0;
        z=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;
      }
      [a,b,c,d,e,f,g,z].forEach((x,i)=>h[i]=(h[i]+x)|0);
    }
    const out=new Uint8Array(32),ov=new DataView(out.buffer);h.forEach((x,i)=>ov.setUint32(i*4,x));return out.buffer;
  }
  const hex=b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,"0")).join("");
  if(hex(sha256(new encoder().encode("abc")))!=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    throw Error("SHA test vector");
  let randomCounter=0;
  const webcrypto={getRandomValues(a){let n=++randomCounter;for(let i=0;i<a.length;i++){a[i]=n&255;n=Math.floor(n/256);}return a;},
    subtle:{digest:async(algorithm,bytes)=>{if(algorithm!=="SHA-256")throw Error("algorithm");return sha256(bytes);}}};
  const canonical=v=>v&&typeof v==="object"?(Array.isArray(v)?v.map(canonical):Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]))):v;
  const assert={
    equal(a,b,msg){if(a!==b)throw Error(msg||("expected "+JSON.stringify(b)+", got "+JSON.stringify(a)));},
    deepEqual(a,b,msg){if(JSON.stringify(canonical(a))!==JSON.stringify(canonical(b)))throw Error(msg||("expected "+JSON.stringify(b)+", got "+JSON.stringify(a)));},
    ok(a,msg){if(!a)throw Error(msg||"expected truthy");},
    match(a,b,msg){if(!b.test(a))throw Error(msg||("did not match "+b+": "+a));},
    notEqual(a,b,msg){if(a===b)throw Error(msg||"expected unequal");}
  };
  const mod={exports:{}};
  new Function("module","require","TextEncoder",source).call({},mod,n=>{if(n==="node:crypto")return {webcrypto};throw Error(n);},encoder);
  const req=n=>{
    if(n==="node:test")return (name,fn)=>cases.push({name,fn});
    if(n==="node:assert/strict")return assert;
    if(n==="node:fs")return {readFileSync:()=>fixture};
    if(n==="node:path")return {resolve:(...a)=>a.join("/"),join:(...a)=>a.join("/")};
    if(n==="../src/conversation.js")return mod.exports;
    throw Error("unsupported import "+n);
  };
  new Function("require","__dirname","setImmediate",testsSource)(req,"/virtual/tests",cb=>Promise.resolve().then(cb));
  return (async()=>{
    const results=[];
    for(const t of cases){try{await t.fn();results.push({name:t.name,status:"PASS"});}catch(e){failures.push({name:t.name,error:String(e)});results.push({name:t.name,status:"FAIL",error:String(e)});}}
    return {runtime:"V8 isolate with minimal node:test/assert/fs/path shims; JS SHA-256; deterministic test-only random IDs; no Node/DOM/HTTP server",passed:cases.length-failures.length,failed:failures.length,results};
  })();
}
if (typeof module === 'object') module.exports = runConversationTests;
