/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : receipts.test.js
 * Description : Reçus historiques contre le VRAI serveur et le jeu bêta C-009g, Node et Chromium (C-TASK-G036)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// Run from eidolon-core/: NODE_PATH=<dir containing playwright> node --test "desktop/connected/tests/*.test.js"
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const C = require("../src/session.js");
const { WEB_ROOT, CAPTURES, chromium, chromiumUnavailable, noPython, makeFixture, startServer, stop, nodeTransport,
  cleanup } = require("./helpers.js");

test("real server + beta fixture: the three receipt queries, an absent key and a wrong mission", { skip: noPython }, async () => {
  const fx = makeFixture();
  let server;
  try {
    server = await startServer(fx, null);
    const s = C.createSession({ transport: nodeTransport(server.base) });
    assert.equal(await s.connect(fx.token), true);
    assert.equal(s.state().storeId, fx.manifest.store_id);
    assert.equal(s.state().list.items.length, 6);
    const revoked = fx.role("approval_revoked");
    await s.selectMission(revoked);
    const current = s.state().list.selection.sync.view.mission;
    assert.equal(current.action_view.decision.status, "REVOKED");
    await s.lookupReceipt("beta-fixture", "historical-approve");
    let st = s.state();
    assert.equal(st.receipt.status, "FOUND");
    assert.equal(st.receipt.receipt.approval_status_at_recording, "APPROVED", "historical record");
    assert.equal(st.receipt.binding, "EVENT_HASH", "G048: binding reported by the real server");
    assert.deepEqual(st.list.selection.sync.view.mission, current, "current capture unchanged: still REVOKED");
    await s.lookupReceipt("beta-fixture", "historical-revoke");
    assert.equal(s.state().receipt.receipt.approval_status_at_recording, "REVOKED");
    await s.lookupReceipt("beta-fixture", "absente-g036");
    assert.equal(s.state().receipt.status, "NOT_FOUND");
    // The cancellation receipt belongs to another mission: asked from here, Core says mismatch.
    await s.lookupReceipt("beta-fixture", "cancel-requested");
    assert.equal(s.state().receipt.code, "RECEIPT_MISSION_MISMATCH");
    assert.equal(s.state().phase, "connected");
    await s.selectMission(fx.role("cancel_requested"));
    await s.lookupReceipt("beta-fixture", "cancel-requested");
    st = s.state();
    assert.equal(st.receipt.receipt.cancel_outcome, "REQUESTED");
    assert.equal(st.list.selection.sync.view.mission.status, "NEW", "requested, not stopped");
    assert.ok(!JSON.stringify(st).includes(fx.token));
  } finally { await cleanup({ servers: [server], dirs: [fx.dir] }); }
});

test("real server: another store behind the same address answers STORE_CHANGED; lookups stop until reconnection", { skip: noPython }, async () => {
  const a = makeFixture(), b = makeFixture();
  let server;
  try {
    server = await startServer(a, null);
    let base = server.base;
    const s = C.createSession({ transport: (m, p, body, t) => nodeTransport(base)(m, p, body, t) });
    await s.connect(a.token);
    await s.selectMission(a.role("approval_revoked"));
    await stop(server);
    server = await startServer(Object.assign({}, b, { tokenFile: a.tokenFile }), null);   // same token, other store
    base = server.base;
    await s.lookupReceipt("beta-fixture", "historical-approve");
    let st = s.state();
    assert.equal(st.receipt.code, "STORE_CHANGED");
    assert.equal(st.resyncRequired, true);
    assert.equal(await s.lookupReceipt("beta-fixture", "historical-revoke"), false, "nothing sent before resync");
    await s.connect(a.token);
    st = s.state();
    assert.equal(st.storeId, b.manifest.store_id);
    assert.equal(st.resyncRequired, false);
    assert.equal(st.list.selection, null, "old selection wiped with the old store");
  } finally { await cleanup({ servers: [server], dirs: [a.dir, b.dir] }); }
});

test("Chromium on the real server: receipt lookup shown next to the current capture, no command button", { skip: noPython || chromiumUnavailable }, async () => {
  const fx = makeFixture();
  let server, browser;
  try {
    server = await startServer(fx, WEB_ROOT);
    browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(server.base + "/");
    assert.equal(await page.isVisible("#receipt"), false, "no receipt form before a selection");
    await page.fill("#token", fx.token);
    await page.click("#connect");
    await page.waitForSelector(".mission-button");
    await page.click(".mission-button:has-text('" + fx.role("approval_revoked").slice(0, 10) + "')");
    await page.waitForSelector(".fields");
    await page.fill("#receipt-client", "beta-fixture");
    await page.fill("#receipt-key", "historical-approve");
    await page.click("#receipt-lookup");
    await page.waitForSelector(".receipt-found");
    const text = await page.textContent("#receipt-result");
    assert.match(text, /Enregistrement historique trouvé — décision « approve »/);
    assert.match(text, /APPROVED/);
    assert.match(text, /Capture actuelle\s*REVOKED/);
    // G048: the fixture is written by the current Core, so its receipts carry the event hash.
    assert.match(text, /Contrôle d'intégrité\s*Liaison au journal vérifiée par Core/);
    assert.match(text, /ni une signature ni une preuve d'exécution/);
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g036-receipt-found.png"), fullPage: true });
    await page.fill("#receipt-key", "absente-g036");
    await page.click("#receipt-lookup");
    await page.waitForSelector(".receipt-missing");
    assert.match(await page.textContent("#receipt-result"), /ne prouve pas que la commande n'est jamais partie/);
    await page.fill("#receipt-key", "clé invalide");
    await page.click("#receipt-lookup");
    await page.waitForSelector(".receipt-error");
    if (CAPTURES) await page.screenshot({ path: path.join(CAPTURES, "g036-receipt-invalid.png"), fullPage: true });
    const labels = await page.$$eval("button", (b) => b.map((x) => x.textContent));
    assert.deepEqual(labels.filter((x) => /approuv|lancer|annuler|exécut|renvoy/i.test(x)), []);
    assert.deepEqual(errors, []);
  } finally { await cleanup({ browser, servers: [server], dirs: [fx.dir] }); }
});
