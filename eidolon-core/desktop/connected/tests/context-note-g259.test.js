/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : context-note-g259.test.js
 * Description : Index diagnostics describe only memory actually sent.
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { contextNote } = require('../src/conversation.js');
for (const memory of ['none', 'unavailable', 'dropped_for_budget']) {
  for (const memory_index of ['INDEX_STALE', 'INDEX_UNVERIFIED']) {
    test(`${memory}: ignore forged ${memory_index}`, () => {
      const note = {memory, partial: true};
      assert.equal(contextNote({...note, memory_index}), contextNote(note));
    });
  }
}
for (const memory_index of ['INDEX_STALE', 'INDEX_UNVERIFIED']) {
  test(`sent: preserve ${memory_index} even with zero excerpts`, () => {
    assert.match(contextNote({memory: 'sent', memory_items: 0, memory_index, partial: true}), /index/);
  });
}
