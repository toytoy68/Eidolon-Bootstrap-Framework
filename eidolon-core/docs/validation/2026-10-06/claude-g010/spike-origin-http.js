const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  const errs = [], reqs = [];
  p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('request', r => reqs.push(r.url()));
  await p.goto(process.argv[2] + '/index.html');
  await p.click('#approve'); await p.click('#server-step'); await p.click('#server-step'); await p.click('#server-step');
  const state = await p.textContent('#mission-state');
  await p.selectOption('#scenario', 'sync-rattrapage'); await p.click('text=Recharger le scénario');
  for (let i = 0; i < 9; i++) await p.click('#server-step');
  const refs = await p.locator('#sync-refs li').count();
  const origins = [...new Set(reqs.map(u => new URL(u).origin))];
  console.log(JSON.stringify({ origin: new URL(process.argv[2]).origin, g009_state: state, sync_refs: refs, request_origins: origins, errors: errs }));
  await b.close();
})();
