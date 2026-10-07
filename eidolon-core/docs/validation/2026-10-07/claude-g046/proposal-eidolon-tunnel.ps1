# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : eidolon-tunnel.ps1
# Description : Lanceur candidat du tunnel SSH local vers la consultation bêta (C-TASK-G040)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
<#
.SYNOPSIS
  Ouvre ou arrête UN tunnel SSH local 127.0.0.1:<Port> -> serveur 127.0.0.1:<Port>.

.DESCRIPTION
  Mode aperçu par défaut : affiche ce qui serait fait, sans aucune connexion.
  -Connect ouvre le tunnel dans une nouvelle fenêtre (pour répondre à SSH :
  empreinte du serveur, mot de passe ou phrase de passe). -Stop arrête
  seulement le tunnel lancé par ce script pour ce port.
  Ne crée aucune clé, ne lit ni n'affiche aucun jeton, ne touche ni au
  pare-feu ni à la configuration SSH, n'installe rien. La vérification de la
  clé d'hôte SSH reste celle de votre configuration.
  Ce n'est pas l'application Windows d'Eidolon : un lanceur de recette.

.EXAMPLE
  .\eidolon-tunnel.ps1 -Server serveur.local -User toytoy -Port 8765
  .\eidolon-tunnel.ps1 -Server serveur.local -User toytoy -Port 8765 -Connect -OpenBrowser
  .\eidolon-tunnel.ps1 -Stop -Port 8765
#>
[CmdletBinding(DefaultParameterSetName = 'Run')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Run')][string]$Server,
    [Parameter(Mandatory = $true, ParameterSetName = 'Run')][string]$User,
    [Parameter(Mandatory = $true)][ValidateRange(1024, 65535)][int]$Port,
    [Parameter(ParameterSetName = 'Run')][switch]$Connect,
    [Parameter(ParameterSetName = 'Run')][switch]$OpenBrowser,
    # Diagnostic C-009c facultatif, exécuté sur le serveur avant le tunnel.
    # Chemins relatifs au dossier personnel distant (ou absolus).
    [Parameter(ParameterSetName = 'Run')][string]$RemoteCore,
    [Parameter(ParameterSetName = 'Run')][string]$RemoteState,
    [Parameter(ParameterSetName = 'Run')][string]$RemoteTokenFile,
    [Parameter(Mandatory = $true, ParameterSetName = 'Stop')][switch]$Stop
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-Header([string]$Title) {
    $width = 57
    $line = '#' * $width
    $row = { param($t) '#' + $t.PadLeft([int](($width - 2 + $t.Length) / 2)).PadRight($width - 2) + '#' }
    Write-Output ''
    Write-Output $line
    Write-Output (& $row '')
    Write-Output (& $row 'Eidolon Core')
    Write-Output (& $row $Title)
    Write-Output (& $row '')
    Write-Output $line
    Write-Output ''
    Write-Output 'Eidolon Core Technologies (ECT)'
    Write-Output 'Local AI • Modular • Reliable • Reproducible'
    Write-Output ''
}

function Write-Ect([ValidateSet('INFO', 'OK', 'ATTENTION', 'ERREUR')][string]$Level, [string]$Text) {
    Write-Output "[$Level] $Text"
}

function Stop-WithError([string]$Text) {
    Write-Ect 'ERREUR' $Text
    exit 2
}

# Record of the tunnel started by THIS script, one file per local port.
$RecordDir = Join-Path $env:LOCALAPPDATA 'Eidolon\beta-tunnel'
$RecordFile = Join-Path $RecordDir ("tunnel-{0}.json" -f $Port)

function Get-OwnTunnel {
    if (-not (Test-Path -LiteralPath $RecordFile)) { return $null }
    $record = Get-Content -LiteralPath $RecordFile -Raw | ConvertFrom-Json
    $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    # Same PID, same program, same start time: otherwise the PID was reused by something else.
    if ($null -eq $process -or $process.ProcessName -ne 'ssh' -or
        [math]::Abs($process.StartTime.ToUniversalTime().Ticks - [long]$record.started_ticks) -gt 20000000) { return @{ record = $record; process = $null } }
    return @{ record = $record; process = $process }
}

function Test-LocalPortFree([int]$P) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $P)
    try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}

function Test-LocalPortOpen([int]$P) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { $client.Connect('127.0.0.1', $P); return $true } catch { return $false } finally { $client.Dispose() }
}

# ---- Stop --------------------------------------------------------------------------------------
if ($PSCmdlet.ParameterSetName -eq 'Stop') {
    Write-Header 'Arrêt du tunnel de recette'
    $own = Get-OwnTunnel
    if ($null -eq $own) { Write-Ect 'INFO' "Aucun tunnel enregistré par ce script pour le port $Port."; exit 0 }
    if ($null -eq $own.process) {
        Remove-Item -LiteralPath $RecordFile
        Write-Ect 'INFO' "Le PID $($own.record.pid) n'est plus le tunnel enregistré (arrêté ou réutilisé) ; enregistrement retiré, aucun processus arrêté."
        exit 0
    }
    Stop-Process -Id $own.process.Id
    Remove-Item -LiteralPath $RecordFile
    Write-Ect 'OK' "Tunnel du port $Port arrêté (PID $($own.process.Id)). Le serveur Core n'est pas arrêté."
    exit 0
}

# ---- Run (preview by default) --------------------------------------------------------------------
Write-Header 'Tunnel de consultation bêta'

# Strict values only: no option injection into ssh, no shell metacharacters on the server.
if ($Server -notmatch '^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$') { Stop-WithError 'Nom de serveur invalide (lettres, chiffres, points, tirets).' }
if ($User -notmatch '^[A-Za-z_][A-Za-z0-9_.-]{0,31}$') { Stop-WithError "Nom d'utilisateur invalide." }
$remoteArgs = @(@($RemoteCore, $RemoteState, $RemoteTokenFile) | Where-Object { $_ })   # always an array (StrictMode)
if ($remoteArgs.Count -ne 0 -and $remoteArgs.Count -ne 3) { Stop-WithError 'Diagnostic distant : donner -RemoteCore, -RemoteState et -RemoteTokenFile ensemble.' }
foreach ($path in $remoteArgs) {
    if ($path -notmatch '^[A-Za-z0-9_./~-]{1,255}$' -or $path.StartsWith('-') -or
        ($path.StartsWith('~') -and $path -ne '~' -and -not $path.StartsWith('~/'))) { Stop-WithError "Chemin distant refusé : $path" }
}

$ssh = Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
if ($null -eq $ssh) { Stop-WithError "Client OpenSSH introuvable (ssh.exe). L'activer dans les fonctionnalités facultatives de Windows ; ce script ne l'installe pas." }
Write-Ect 'OK' "Client SSH : $($ssh.Source)"

$own = Get-OwnTunnel
if ($null -ne $own -and $null -ne $own.process) {
    Write-Ect 'INFO' "Un tunnel lancé par ce script est déjà actif sur le port $Port (PID $($own.process.Id))."
    Write-Ect 'INFO' "Adresse : http://127.0.0.1:$Port/  —  arrêt : .\eidolon-tunnel.ps1 -Stop -Port $Port"
    exit 0
}
if (-not (Test-LocalPortFree $Port)) {
    Stop-WithError "Le port local $Port est déjà utilisé. Choisir un autre port, identique sur le serveur (--port)."
}
Write-Ect 'OK' "Port local $Port libre sur 127.0.0.1."

$forward = "127.0.0.1:{0}:127.0.0.1:{0}" -f $Port
$tunnelArgs = @('-N', '-L', $forward, '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3', '--', "$User@$Server")
$checkCommand = $null
if ($remoteArgs.Count -eq 3) {
    # Expand relative paths against the remote home even AFTER cd to RemoteCore.
    # Inputs already exclude quotes, dollars and shell metacharacters.
    $q = {
        param($p)
        if ($p.StartsWith('/')) { return "'" + $p + "'" }
        # No double quote: Windows PowerShell 5.1 drops them when calling ssh.exe.
        # Tilde expansion is not word-split, and the single-quoted rest is literal.
        if ($p -eq '~') { return '~' }
        return "~/'" + ($p -replace '^~/', '') + "'"
    }
    $checkCommand = "cd $(& $q $RemoteCore) && PYTHONPATH=src python3 -m eidolon_core.http_api --state $(& $q $RemoteState) " +
                    "--token-file $(& $q $RemoteTokenFile) --web-root desktop/connected --port $Port --check --format human"
}
$url = "http://127.0.0.1:$Port/"

if (-not $Connect) {
    Write-Ect 'INFO' 'Mode aperçu : aucune connexion établie.'
    if ($checkCommand) { Write-Ect 'INFO' "Diagnostic distant prévu : ssh -- $User@$Server `"$checkCommand`"" }
    Write-Ect 'INFO' ("Tunnel prévu : ssh " + ($tunnelArgs -join ' '))
    Write-Ect 'INFO' "Adresse locale : $url"
    Write-Ect 'INFO' 'Relancer avec -Connect pour ouvrir le tunnel. Le serveur Core doit déjà tourner (recette BETA-ACCEPTANCE.md, S4).'
    exit 0
}

if ($checkCommand) {
    Write-Ect 'INFO' 'Diagnostic C-009c sur le serveur (ne démarre rien, ne teste ni le port ni le tunnel)…'
    & $ssh.Source -- "$User@$Server" $checkCommand
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Diagnostic distant en échec (code $LASTEXITCODE) : corriger sur le serveur avant d'ouvrir le tunnel." }
    Write-Ect 'OK' 'Diagnostic distant réussi. Ce n''est pas une qualification de la bêta.'
}

Write-Ect 'INFO' 'Ouverture du tunnel dans une nouvelle fenêtre : y répondre à SSH si nécessaire (empreinte, mot de passe).'
$process = Start-Process -FilePath $ssh.Source -ArgumentList $tunnelArgs -PassThru
New-Item -ItemType Directory -Force -Path $RecordDir | Out-Null
@{ pid = $process.Id; port = $Port; server = $Server; user = $User;
   started_ticks = $process.StartTime.ToUniversalTime().Ticks } | ConvertTo-Json | Set-Content -LiteralPath $RecordFile -Encoding UTF8

# Wait for the forward to listen (the user may be typing a password), at most 120 s.
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        Remove-Item -LiteralPath $RecordFile
        Stop-WithError "Le tunnel s'est arrêté (code $($process.ExitCode)). Vérifier l'accès SSH et que le port $Port est libre sur le serveur."
    }
    if (Test-LocalPortOpen $Port) { break }
    Start-Sleep -Milliseconds 500
}
if (-not (Test-LocalPortOpen $Port)) {
    Write-Ect 'ATTENTION' "Le tunnel (PID $($process.Id)) n'écoute pas encore après 120 s. Il reste ouvert ; l'arrêter avec -Stop -Port $Port."
    exit 2
}
Write-Ect 'OK' "Tunnel ouvert (PID $($process.Id)) : $url"
Write-Ect 'INFO' 'Jeton : le lire sur le serveur (cat du fichier jeton) et le coller dans la page. Ce script ne le lit jamais.'
Write-Ect 'INFO' "Arrêt du tunnel seul : .\eidolon-tunnel.ps1 -Stop -Port $Port"
if ($OpenBrowser) { Start-Process $url }
exit 0
