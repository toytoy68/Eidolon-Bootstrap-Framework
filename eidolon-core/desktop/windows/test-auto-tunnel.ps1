# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test-auto-tunnel.ps1
# Description : Tests du tunnel automatique, sans serveur ni identifiants
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'eidolon-auto-tunnel.ps1')
$ssh=(Get-Command ssh.exe -CommandType Application -ErrorAction Stop).Source
$owner=[pscustomobject]@{Name='ssh.exe'; ExecutablePath=$ssh; CommandLine='"'+$ssh+'" -N -L 127.0.0.1:18767:127.0.0.1:18767 -- fixture@fixture.invalid'}
if (-not (Test-EidolonSshOwner $owner $ssh 'fixture.invalid' 'fixture' 18767)) { throw 'Correct tunnel rejected' }
foreach ($change in @(
    @{Name='ssh.exe'; ExecutablePath=$ssh; CommandLine=$owner.CommandLine.Replace('fixture@','Fixture@')},
    @{Name='ssh.exe'; ExecutablePath=$ssh; CommandLine=$owner.CommandLine.Replace('fixture.invalid','other.invalid')},
    @{Name='ssh.exe'; ExecutablePath=$ssh; CommandLine=$owner.CommandLine.Replace('18767','18768')},
    @{Name='ssh.exe'; ExecutablePath='C:\other\ssh.exe'; CommandLine=$owner.CommandLine},
    @{Name='other.exe'; ExecutablePath=$ssh; CommandLine=$owner.CommandLine}
)) {
    if (Test-EidolonSshOwner ([pscustomobject]$change) $ssh 'fixture.invalid' 'fixture' 18767) { throw 'Unrelated tunnel accepted' }
}
# A real local listener owned by this PowerShell must never be reused as SSH.
$listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,0)
$listener.Start()
try {
    $refused=$false
    try { [void](Test-EidolonTunnelReady $ssh 'fixture.invalid' 'fixture' $listener.LocalEndpoint.Port) }
    catch { if ($_.Exception.Message -eq 'TUNNEL_PORT_OCCUPIED') { $refused=$true } else { throw } }
    if (-not $refused) { throw 'Occupied port accepted' }
} finally { $listener.Stop() }

# Control process creation/readiness only; never contact an SSH server.
$script:reuse=$false
$script:created=0
$script:killed=0
$script:waitResults=@()
$script:windowStyles=@()
function Test-EidolonTunnelReady { return $script:reuse }
function Start-Process {
    param([string]$FilePath,[string[]]$ArgumentList,[string]$WindowStyle,[switch]$PassThru)
    $script:created++
    $script:windowStyles+=@($WindowStyle)
    if ($FilePath -ne $ssh) { throw ('Incorrect SSH path: '+$FilePath+' expected '+$ssh) }
    if ($ArgumentList -notcontains 'StrictHostKeyChecking=yes') { throw ('Host checking missing: '+($ArgumentList -join '|')) }
    if ($ArgumentList -notcontains '127.0.0.1:18767:127.0.0.1:18767') { throw ('Forward missing: '+($ArgumentList -join '|')) }
    if ($script:created -eq 1 -and $ArgumentList -notcontains 'BatchMode=yes') { throw 'Silent key authentication missing' }
    $fake=[pscustomobject]@{HasExited=$false; Id=12345}
    $fake | Add-Member ScriptMethod Kill { $script:killed++; $this.HasExited=$true }
    $fake | Add-Member ScriptMethod WaitForExit { return $true }
    $fake | Add-Member ScriptMethod Dispose {}
    return $fake
}
function Wait-EidolonTunnel {
    $result=$script:waitResults[0]
    $script:waitResults=@($script:waitResults | Select-Object -Skip 1)
    return $result
}
$script:reuse=$true
Start-EidolonTunnel 'fixture.invalid' 'fixture' 18767
if ($script:created -ne 0) { throw 'Existing tunnel duplicated' }
$script:reuse=$false
$script:waitResults=@($true)
Start-EidolonTunnel 'fixture.invalid' 'fixture' 18767
if ($script:created -ne 1 -or $script:killed -ne 0 -or $script:windowStyles[0] -ne 'Hidden') { throw 'Silent tunnel failed' }
$script:created=0; $script:windowStyles=@(); $script:waitResults=@($false,$true)
Start-EidolonTunnel 'fixture.invalid' 'fixture' 18767
if ($script:created -ne 2 -or $script:killed -ne 1 -or $script:windowStyles[1] -ne 'Normal') { throw 'Interactive fallback failed' }
$script:created=0; $script:waitResults=@($false,$false)
$refused=$false
try { Start-EidolonTunnel 'fixture.invalid' 'fixture' 18767 }
catch { if ($_.Exception.Message -eq 'TUNNEL_CONNECTION_FAILED') { $refused=$true } else { throw } }
if (-not $refused -or $script:killed -ne 3) { throw 'Failed children not cleaned up' }
Write-Host '[OK] Propriete du tunnel, port occupe, reutilisation, cle silencieuse, mot de passe et echec verifies.'
