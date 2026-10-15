/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : context-note-g261.test.js
 * Description : Keep contradictory and future index diagnostics visible.
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { contextNote } = require('../src/conversation.js');
const { WEB_ROOT, chromium, chromiumUnavailable, noPython, makeFixture, startServer, cleanup } = require('./helpers.js');
const cases = [
  [{memory: 'sent', memory_index: 'INDEX_STALE', partial: false}, 'Contexte partiel : des changements de mémoire ne sont pas encore reflétés dans l’index.'],
  [{memory: 'sent', memory_index: 'INDEX_UNVERIFIED'}, 'Contexte partiel : la mise à jour complète de l’index mémoire n’a pas pu être vérifiée.'],
  [{memory: 'sent', memory_index: 'INDEX_FUTURE_STATE', partial: true}, 'Contexte partiel : l’état de l’index mémoire n’est pas reconnu.'],
  [{memory: 'sent', memory_index: 'INDEX_FUTURE_STATE', partial: false}, 'Contexte partiel : l’état de l’index mémoire n’est pas reconnu.'],
  [{memory: 'sent', memory_index: 'INDEX_SNAPSHOT_MATCH', partial: false}, null],
  [{memory: 'sent', partial: true}, null],
  [{memory: 'sent', memory_index: '<img src=x>', partial: true}, null],
  [{memory: 'sent', memory_index: 'index_stale', partial: true}, null],
  [{memory: 'none', memory_index: 'INDEX_FUTURE_STATE', partial: true}, null],
  [{memory: 'unavailable', memory_index: 'INDEX_FUTURE_STATE', partial: true}, 'Contexte partiel : mémoire indisponible.'],
  [{memory: 'dropped_for_budget', memory_index: 'INDEX_STALE', partial: true}, 'Contexte partiel : mémoire non transmise (taille).'],
];
for (const [i, [note, expected]] of cases.entries()) {
  test(`G261 context note ${i}: diagnostic and sent-memory boundary`, () => {
    assert.equal(contextNote(note), expected);
  });
}
test('G261 committed bundle preserves the same diagnostics in Chromium', {skip: noPython || chromiumUnavailable}, async () => {
  const fx = makeFixture();
  let server, browser;
  try {
    server = await startServer(fx, WEB_ROOT);
    browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto(server.base + '/');
    const got = await page.evaluate(notes => notes.map(window.EidolonConversation.contextNote), cases.map(c => c[0]));
    assert.deepEqual(got, cases.map(c => c[1]));
  } finally { await cleanup({browser, servers: [server], dirs: [fx.dir]}); }
});
