/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : startup-g286.test.js
 * Description : Démarrage vocal lié à la conversation, sans boucle double
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const tick=()=>new Promise(r=>setImmediate(r));
function setup(enabled){
 const nodes=new Map();function node(id){if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,checked:true,children:[],listeners:{},addEventListener(k,f){this.listeners[k]=f;},setAttribute(){},appendChild(x){this.children.push(x);},removeChild(){this.children.shift();},get firstChild(){return this.children[0];}});return nodes.get(id);}
 const doc={getElementById:node,createElement:()=>({}),querySelectorAll:()=>[]};let starts=0;const enabledKinds=[];
 const win={EidolonAutoVoice:{create:()=>({start(){starts++;},stop(){},active(){return false;}})}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../src/communication.js'),'utf8'),{window:win,Promise});
 const dev={state:'disabled',devices:[],selected:null,indicator:{text:'off',tone:'off'}};
 const comm={state:()=>({microphone:dev,camera:dev,speaker:dev}),onChange(){},onReset(){},refresh(){},enable:async k=>enabledKinds.push(k)};
 const ui=win.EidolonCommunication.mount(doc,comm,{autoStart:enabled,voiceSend:async()=>''});
 return {ui,starts:()=>starts,enabledKinds};
}
test('paired desktop starts once, repeated phase notifications do not restart after stop',async()=>{
 const f=setup(true);f.ui.conversationChanged('one');await tick();assert.equal(f.starts(),1);assert.deepEqual(f.enabledKinds,['camera']);
 f.ui.conversationChanged('one');await tick();assert.equal(f.starts(),1);
 f.ui.conversationChanged(null);f.ui.conversationChanged('two');await tick();assert.equal(f.starts(),2);
});
test('closed-before-microtask and unpaired browser never start capture',async()=>{
 const a=setup(true);a.ui.conversationChanged('one');a.ui.conversationChanged(null);await tick();assert.equal(a.starts(),0);
 const b=setup(false);b.ui.conversationChanged('one');await tick();assert.equal(b.starts(),0);assert.deepEqual(b.enabledKinds,[]);
});
