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
const { CORE, ENV, PYTHON, WEB_ROOT, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup, nodeTransport } = require('./helpers.js');

test('service payloads never include client identity, actor or absolute root', () => {
  assert.deepEqual(S.parameters('remember', 'exact text', ''), { text: 'exact text' });
  assert.deepEqual(S.parameters('web.search', 'exact query', ''), { query: 'exact query' });
  assert.deepEqual(S.parameters('file.read', 'note.txt', 'nas'), { root: 'nas', path: 'note.txt' });
});

function prepare(fx) {
  const r = spawnSync(PYTHON, ['-m', 'eidolon_core.conversation_api', '--state', fx.state, 'pair', '--client-id', 'pc-ui', '--actor', 'person'], { cwd: CORE, env: ENV, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const state = path.join(fx.dir, 'services'); fs.mkdirSync(state, {mode:0o700});
  const nas = path.join(fx.dir, 'nas'); fs.mkdirSync(nas);
  fs.writeFileSync(path.join(nas, 'note.txt'), 'Un fichier synthétique <script>non exécuté</script>.');
  const token = path.join(state, 'read-token'); fs.writeFileSync(token, 'r'.repeat(40), {mode:0o600});
  const conf = {schema:'eidolon-beta-runtime/1', state_directory:state, activity_source:'host.eidolon', clients:{'pc-ui':'person'},
    profiles:{person:{memory_port:18765, read_token_file:token, write_token_file:null, web_enabled:false, daily_web_limit:2, file_roots:{nas}}}, searxng_url:null};
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
    await open(); await page.click('#service-receipts'); await page.waitForSelector('#service-output button');
    await page.click('#service-output button'); assert.match(await page.textContent('#service-output'),/Un fichier synthétique/);
    await page.click('#conv-close'); assert.equal(await page.textContent('#service-output'),'');
    assert.deepEqual(errors,[]);
  } finally { await cleanup({browser,servers:[server],dirs:[fx.dir]}); }
});
