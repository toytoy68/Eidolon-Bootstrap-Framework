// ==========================================================
// Projet      : Eidolon Core
// Organisation: Eidolon Core Technologies (ECT)
// Fichier     : probe-main.cjs
// Description : Sonde de la logique de maquette, sans moteur de rendu ni réseau
// Standard    : Eidolon Presentation Standard v1
// ==========================================================
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const file = path.resolve(__dirname, '../../../proposals/2026-10-05-claude-desktop-ui/maquettes/Main.dc.html');
const html = fs.readFileSync(file, 'utf8');
const match = html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/);
assert.ok(match, 'script de maquette introuvable');
class DCLogic {
  constructor(props) { this.props = props; this.state = {}; }
  setState(update) { this.state = { ...this.state, ...update }; }
}
const context = vm.createContext({ DCLogic });
vm.runInContext(match[1] + '\nglobalThis.Component = Component;', context, { timeout: 1000 });
const online = new context.Component({ activity: 'attention', coreOnline: true });
online.renderVals().refuse();
const afterRefusal = online.renderVals();
assert.equal(afterRefusal.eye.label, 'Au travail');
const offline = new context.Component({ activity: 'attention', coreOnline: false });
offline.renderVals().approve();
const afterOfflineApproval = offline.renderVals();
assert.equal(afterOfflineApproval.decided, true);
assert.equal(afterOfflineApproval.offline, true);
afterOfflineApproval.undo();
assert.equal(offline.renderVals().pending, true);
console.log(JSON.stringify({
  source: 'Claude 176edac, Main.dc.html', node: process.version,
  scope: 'logique isolee de la maquette; ni rendu, ni accord Core, ni reseau',
  refusal_eye: afterRefusal.eye.label,
  offline_local_decision_label: afterOfflineApproval.decisionLabel,
  undo_restores_pending: offline.renderVals().pending,
  assertions: 4
}, null, 2));
