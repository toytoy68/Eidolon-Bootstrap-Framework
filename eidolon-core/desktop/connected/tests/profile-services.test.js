/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : profile-services.test.js
 * Description : Explicit service actions on the real paired API and browser
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const S = require('../src/profile-services.js');
const { CORE, ENV, PYTHON, WEB_ROOT, chromium, chromiumUnavailable, noPython, makeFixture, startServer, openDisclosure, cleanup, nodeTransport } = require('./helpers.js');

test('service payloads never include client identity, actor or absolute root', () => {
  assert.deepEqual(S.parameters('remember', 'exact text', ''), { text: 'exact text' });
  assert.deepEqual(S.parameters('web.search', 'exact query', ''), { query: 'exact query' });
  assert.deepEqual(S.parameters('file.read', 'note.txt', 'nas'), { root: 'nas', path: 'note.txt' });
});

function prepare(fx, identity) {
  const r = spawnSync(PYTHON, ['-m', 'eidolon_core.conversation_api', '--state', fx.state, 'pair', '--client-id', 'pc-ui', '--actor', 'person'], { cwd: CORE, env: ENV, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const state = path.join(fx.dir, 'services'); fs.mkdirSync(state, {mode:0o700});
  const nas = path.join(fx.dir, 'nas'); fs.mkdirSync(nas);
  fs.writeFileSync(path.join(nas, 'note.txt'), 'Un fichier synthétique <script>non exécuté</script>.');
  const token = path.join(state, 'read-token'); fs.writeFileSync(token, 'r'.repeat(40), {mode:0o600});
  const conf = {schema:'eidolon-beta-runtime/1', state_directory:state, activity_source:'host.eidolon', clients:{'pc-ui':'person'},
    profiles:{person:{memory_port:18765, read_token_file:token, write_token_file:null, web_enabled:false, daily_web_limit:2, file_roots:{nas}}}, searxng_url:null};
  if (identity) {
    const identityConfig=path.join(state,'identity.json');
    fs.writeFileSync(identityConfig,JSON.stringify({schema:'eidolon-identity-runtime/1',modalities:{face:{samples:1,
      model:{path:'/synthetic/model.onnx',sha256:'a'.repeat(64)},detector:{path:'/synthetic/detector.onnx',sha256:'b'.repeat(64)},calibration:null}}}),{mode:0o600});
    conf.identity_config=identityConfig;
  }
  const config = path.join(state,'runtime.json'); fs.writeFileSync(config, JSON.stringify(conf), {mode:0o600});
  return {key:JSON.parse(r.stdout).token, config};
}

test('paired production routes expose profile and a durable file receipt; read token cannot commit', {skip:noPython}, async () => {
  const fx = makeFixture(); let server;
  try {
    const cfg = prepare(fx);
    server = await startServer(fx, WEB_ROOT, {spawnServer:(cmd,args,opts)=>spawn(cmd,args.concat(['--conversations','simulated','--beta-runtime',cfg.config]),opts)});
    const call = nodeTransport(server.base);
    const opened = await call('POST','/v1/conversations/open',{client_key:'page'},cfg.key);
    assert.equal(opened.json.services.profile_id,'person');
    const a = await call('POST','/v1/conversations/action_preview',{request_key:'file',action:'file.read',parameters:{root:'nas',path:'note.txt'}},cfg.key);
    assert.equal(a.json.state,'PREVIEW');
    const commit = {id:a.json.proposal.id,sha256:a.json.sha256};
    assert.equal((await call('POST','/v1/conversations/action_commit',commit,fx.token)).status,403);
    assert.equal((await call('POST','/v1/conversations/action_commit',commit,cfg.key)).json.state,'COMMITTED');
    const activity = await call('GET','/v1/activity',undefined,fx.token);
    assert.equal(activity.json.schema,'eidolon-activity-receipt/1');
    assert.equal((await call('GET','/v1/activity',undefined,cfg.key)).status,401);
  } finally { await cleanup({servers:[server],dirs:[fx.dir]}); }
});

test('Chromium: selected PC document is only uploaded on request, confirmed and analysed', {skip:noPython || chromiumUnavailable}, async()=>{
  const fx=makeFixture();let server,browser;
  try{
    const cfg=prepare(fx);
    server=await startServer(fx,WEB_ROOT,{spawnServer:(cmd,args,opts)=>spawn(cmd,args.concat(['--conversations','simulated','--beta-runtime',cfg.config]),opts)});
    browser=await chromium.launch();const page=await browser.newPage();const uploaded=[];
    page.on('request',r=>{if(r.url().endsWith('/document_preview'))uploaded.push(r);});
    await page.goto(server.base+'/');await page.fill('#conv-key',cfg.key);await page.press('#conv-key','Enter');
    await page.waitForSelector('#profile-services:not([hidden])');await page.click('#profile-services summary');
    await page.setInputFiles('#service-upload',{name:'note.txt',mimeType:'text/plain',buffer:Buffer.from('Document local <script>sans exécution</script>.')});
    assert.equal(uploaded.length,0);assert.match(await page.textContent('#service-output'),/Aucun envoi/);
    await page.click('#service-document');await page.waitForSelector('#service-confirm:not([hidden])');
    assert.equal(uploaded.length,1);assert.match(await page.textContent('#service-output'),/aucune mémorisation automatique/);
    assert.equal(await page.locator('#service-output script').count(),0);
    await page.click('#service-confirm');await page.waitForSelector('#service-discuss:not([hidden])');
    const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/turn')),page.click('#service-discuss')]);
    assert.equal((await response.json()).reply.context.observations_sent,1);
    await page.fill('#conv-text','Brouillon privé');await openDisclosure(page, ".conv-options"); await page.click('#conv-close');
    assert.equal(await page.inputValue('#conv-text'),'');assert.equal(await page.textContent('#service-output'),'');
  }finally{await cleanup({browser,servers:[server],dirs:[fx.dir]});}
});

test('Chromium: voluntary enrolment uses real paired routes with synthetic encoder and fake camera', {skip:noPython || chromiumUnavailable}, async()=>{
  const fx=makeFixture();let server,browser;
  try{
    const cfg=prepare(fx,true);
    const bootstrap="import sys\nfrom datetime import datetime,timezone\nimport eidolon_core.identity_runtime as ir\nfrom eidolon_core.identity_proposal import Observation\ndef observe(cfg,modality,raw):\n return Observation(modality,datetime.now(timezone.utc),ir.engine(cfg,modality),faces=1,embedding=(1.0,0.1))\nir.observe_isolated=observe\nfrom eidolon_core.http_api import main\nraise SystemExit(main(sys.argv[1:]))";
    server=await startServer(fx,WEB_ROOT,{spawnServer:(cmd,args,opts)=>spawn(cmd,['-c',bootstrap,...args.slice(2),'--conversations','simulated','--beta-runtime',cfg.config],opts)});
    browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']});
    const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(server.base+'/');await page.fill('#conv-key',cfg.key);await page.press('#conv-key','Enter');
    await page.waitForSelector('#identity-panel:not([hidden])');await page.click('#identity-panel summary');
    await page.waitForFunction(()=>!document.getElementById('identity-begin').disabled);
    await page.click('#identity-begin');assert.match(await page.textContent('#identity-output'),/Confirmez votre présence/);
    await page.check('#identity-present');await page.check('#identity-consent');await page.click('#identity-begin');
    await page.waitForFunction(()=>!document.getElementById('identity-capture').disabled);await page.click('#identity-capture');
    await page.waitForSelector('#identity-confirm:not([hidden])');assert.match(await page.textContent('#identity-indicator'),/arrêtés/);
    await page.click('#identity-confirm');await page.waitForFunction(()=>!document.getElementById('identity-probe').disabled);
    await page.click('#identity-probe');await page.waitForFunction(()=>document.getElementById('identity-output').textContent.includes('uncalibrated'));
    await page.click('#identity-delete');await page.click('#identity-delete-confirm');
    await page.waitForFunction(()=>document.getElementById('identity-output').textContent.includes('retirés du registre actif'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    await openDisclosure(page, ".conv-options"); await page.click('#conv-close');assert.equal(await page.textContent('#identity-output'),'');
    assert.equal(await page.isChecked('#identity-consent'),false);assert.deepEqual(errors,[]);
  }finally{await cleanup({browser,servers:[server],dirs:[fx.dir]});}
});

test('Chromium: prepare, confirm, reload receipts and close clears profile data', {skip:noPython || chromiumUnavailable}, async () => {
  const fx=makeFixture(); let server,browser;
  try {
    const cfg=prepare(fx);
    server=await startServer(fx,WEB_ROOT,{spawnServer:(cmd,args,opts)=>spawn(cmd,args.concat(['--conversations','simulated','--beta-runtime',cfg.config]),opts)});
    browser=await chromium.launch(); const page=await browser.newPage(); const errors=[];
    page.on('pageerror', e=>errors.push(String(e)));
    async function open() {
      await page.goto(server.base+'/'); await page.fill('#conv-key',cfg.key); await page.press('#conv-key','Enter');
      await page.waitForSelector('#profile-services:not([hidden])'); await page.click('#profile-services summary');
    }
    await open(); await page.selectOption('#service-action','file.read'); await page.fill('#service-root','nas'); await page.fill('#service-value','note.txt');
    await page.click('#service-preview'); await page.waitForSelector('#service-confirm:not([hidden])');
    assert.match(await page.textContent('#service-output'),/note.txt/);
    await page.click('#service-confirm'); await page.waitForFunction(()=>document.getElementById('service-output').textContent.includes('Un fichier synthétique'));
    assert.equal(await page.locator('#service-output script').count(),0);
    const [turnResponse] = await Promise.all([
      page.waitForResponse(r=>r.url().endsWith('/v1/conversations/turn')),
      page.click('#service-discuss')
    ]);
    const turn = await turnResponse.json();
    assert.equal(turn.reply.context.observations_sent,1);
    assert.match(turnResponse.request().postDataJSON().source_action,/^[0-9a-f]{32}$/);
    await open(); await page.click('#service-receipts'); await page.waitForSelector('#service-output button');
    await page.click('#service-output button'); assert.match(await page.textContent('#service-output'),/Un fichier synthétique/);
    await openDisclosure(page, ".conv-options"); await page.click('#conv-close'); assert.equal(await page.textContent('#service-output'),'');
    assert.deepEqual(errors,[]);
  } finally { await cleanup({browser,servers:[server],dirs:[fx.dir]}); }
});

test('G273 Chromium: synchronized library, session locking and explicit key revocation', {skip:noPython || chromiumUnavailable}, async()=>{
  const fx=makeFixture();let server,browser;
  try{
    const cfg=prepare(fx), conf=JSON.parse(fs.readFileSync(cfg.config,'utf8'));
    fs.writeFileSync(path.join(conf.profiles.person.file_roots.nas,'empty.txt'),'');
    const sync=spawnSync(PYTHON,['-m','eidolon_core.library_sync','--config',cfg.config,'--directory',conf.state_directory,'--client','pc-ui','--root','nas','--sync'],{cwd:CORE,env:ENV,encoding:'utf8'});
    assert.equal(sync.status,0,sync.stderr+sync.stdout);
    server=await startServer(fx,WEB_ROOT,{spawnServer:(cmd,args,opts)=>spawn(cmd,args.concat(['--conversations','simulated','--beta-runtime',cfg.config]),opts)});
    browser=await chromium.launch();const page=await browser.newPage();
    await page.goto(server.base+'/');await page.fill('#conv-key',cfg.key);await page.press('#conv-key','Enter');
    await page.waitForSelector('#profile-services:not([hidden])');await page.click('#profile-services summary');
    await page.fill('#service-root','nas');await page.click('#service-library');
    await page.waitForSelector('#service-library-list button');assert.match(await page.textContent('#service-library-list'),/note.txt/);
    assert.match(await page.textContent('#service-library-list'),/empty.txt.*sans extrait.*DOCUMENT_SIZE_INVALID/);
    await page.locator('#service-library-list button').filter({hasText:'note.txt'}).click();assert.equal(await page.inputValue('#service-value'),'note.txt');
    await openDisclosure(page, ".conv-options"); await page.click('#conv-close');assert.equal(await page.textContent('#service-library-list'),'');
    await page.fill('#conv-key',cfg.key);await page.press('#conv-key','Enter');await page.waitForSelector('#conv-revoke:not([hidden])');
    await page.click('#conv-revoke');await page.waitForSelector('#conv-revoke-confirm:not([hidden])');
    const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/session_revoke')),page.click('#conv-revoke-confirm')]);
    assert.equal(response.status(),200);await page.waitForSelector('#conv-key:visible');
    await page.fill('#conv-key',cfg.key);await page.press('#conv-key','Enter');
    await page.waitForFunction(()=>document.querySelector('#conv-close').hidden);
    assert.equal(await page.textContent('#service-library-list'),'');
  }finally{await cleanup({browser,servers:[server],dirs:[fx.dir]});}
});
