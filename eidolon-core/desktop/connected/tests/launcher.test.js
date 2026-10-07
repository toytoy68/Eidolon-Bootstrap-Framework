/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : launcher.test.js
 * Description : Contrôles statiques du lanceur PowerShell candidat (C-TASK-G040)
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
// STATIC checks only: PowerShell and Windows are not available where this runs.
// They pin the safety properties of the script text; they do not execute it.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const FILE = path.join(__dirname, "..", "launchers", "eidolon-tunnel.ps1");
const raw = fs.readFileSync(FILE);
const text = raw.toString("utf8");

test("UTF-8 with BOM, so Windows PowerShell 5.1 reads the accents correctly", () => {
  assert.deepEqual([...raw.subarray(0, 3)], [0xef, 0xbb, 0xbf]);
});

test("the forward binds 127.0.0.1 on both sides, same port, and ends ssh options before the destination", () => {
  assert.match(text, /"127\.0\.0\.1:\{0\}:127\.0\.0\.1:\{0\}" -f \$Port/);
  assert.match(text, /'ExitOnForwardFailure=yes'/);
  assert.match(text, /'--', "\$User@\$Server"/);
  assert.doesNotMatch(text, /0\.0\.0\.0|GatewayPorts|-g'/);
});

test("host key verification and system settings are never weakened", () => {
  for (const bad of [/StrictHostKeyChecking/i, /UserKnownHostsFile/i, /ssh-keygen/i, /NetFirewall/i, /Set-Service|New-Service/i,
    /Install-(Module|Package)|Add-WindowsCapability/i, /Set-ExecutionPolicy/i, /reg(\.exe)? add/i]) {
    assert.doesNotMatch(text, bad, String(bad));
  }
});

test("preview by default; connection only with -Connect; stop limited to its own recorded ssh process", () => {
  assert.match(text, /if \(-not \$Connect\) \{[\s\S]*?Mode aperçu : aucune connexion établie[\s\S]*?exit 0/);
  assert.match(text, /\$process\.ProcessName -ne 'ssh'/);
  assert.match(text, /StartTime\.ToUniversalTime\(\)\.Ticks -ne \[long\]\$record\.started_ticks/);
  const stops = text.match(/Stop-Process[^\n]*/g);
  assert.deepEqual(stops, ["Stop-Process -Id $own.process.Id"]);
  const removes = text.match(/Remove-Item[^\n]*/g);
  assert.ok(removes.every((r) => r.trim() === "Remove-Item -LiteralPath $RecordFile"), removes.join(" | "));
});

test("no secret is read or printed; inputs are validated before reaching ssh or the remote shell", () => {
  assert.doesNotMatch(text, /read-token'|Get-Content[^\n]*token/i);
  assert.match(text, /\$Server -notmatch '\^\[A-Za-z0-9\]/);
  assert.match(text, /\$User -notmatch/);
  assert.match(text, /\$path -notmatch '\^\[A-Za-z0-9_\.\/~-\]\{1,255\}\$' -or \$path\.StartsWith\('-'\)/);
  assert.match(text, /ValidateRange\(1024, 65535\)/);
});

test("the optional remote diagnostic is C-009c --check, which starts nothing", () => {
  assert.match(text, /--web-root desktop\/connected --port \$Port --check --format human/);
  assert.doesNotMatch(text, /http_api --state[^\n]*--port \$Port"\s*$/m, "never starts the server remotely");
});

// Static contract only; the PowerShell construction still requires Windows execution.
test("remote relative paths keep their home anchor after cd; absolute paths remain literal", () => {
  assert.ok(text.includes(`if ($p.StartsWith('/')) { return "'" + $p + "'" }`));
  assert.ok(text.includes(`return "~/'" + ($p -replace '^~/', '') + "'"`));
  assert.ok(text.includes(`if ($p -eq '~') { return '~' }`));
  assert.doesNotMatch(text, /return '\"\$HOME/);
  assert.ok(text.includes(`$path.StartsWith('~') -and $path -ne '~' -and -not $path.StartsWith('~/')`));
});
