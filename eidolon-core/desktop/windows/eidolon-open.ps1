# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : eidolon-open.ps1
# Description : Windows user-bound pairing and automatic conversation opening
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
[CmdletBinding()]
param(
    [string]$ClientExe = (Join-Path $PSScriptRoot 'eidolon-consultation.exe'),
    [string]$Server = '192.168.1.101',
    [string]$User = 'toytoy',
    [ValidateRange(1024,65535)][int]$Port = 8767,
    [string]$RemoteKey = '/home/toytoy/eidolon-beta/pc-toytoy-g277-token',
    [switch]$ForgetPairing
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Test-EidolonKey([string]$Key) { return $Key -cmatch '\Aecc_[A-Za-z0-9_-]{43}\z' }
function Protect-EidolonPairing([string]$Key, [string]$Binding) {
    if (-not (Test-EidolonKey $Key)) { throw 'PAIRING_KEY_INVALID' }
    $plain = @{ version=1; binding=$Binding; key=$Key } | ConvertTo-Json -Compress
    $secure = ConvertTo-SecureString -String $plain -AsPlainText -Force
    try { return ConvertFrom-SecureString -SecureString $secure } finally { $secure.Dispose(); $plain=$null }
}
function Read-EidolonPairing([string]$Encrypted, [string]$Binding) {
    $secure = ConvertTo-SecureString -String $Encrypted
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) | ConvertFrom-Json
        if ($value.version -ne 1 -or $value.binding -cne $Binding -or -not (Test-EidolonKey $value.key)) { throw 'PAIRING_BINDING_INVALID' }
        return [string]$value.key
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        $secure.Dispose()
    }
}
# Tests may import only the pure/DPAPI helpers, without SSH or application start.
if ($MyInvocation.InvocationName -eq '.') { return }

$stage='initialisation'
try {
    if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_REQUIRED' }
    if ($Server -notmatch '\A[A-Za-z0-9][A-Za-z0-9.-]{0,251}\z' -or
        $User -notmatch '\A[A-Za-z_][A-Za-z0-9_.-]{0,31}\z' -or
        $RemoteKey -notmatch '\A/[A-Za-z0-9_./-]{1,240}\z' -or $RemoteKey.Contains('..')) { throw 'PAIRING_TARGET_INVALID' }
    $binding = "$User@$Server|$Port|$RemoteKey"
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $id = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($binding)))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
    $directory = Join-Path $env:LOCALAPPDATA 'Eidolon\pairing'
    $file = Join-Path $directory ($id + '.dpapi')
    if ($ForgetPairing) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
        Write-Host '[OK] Appairage local oublie. La cle serveur reste soumise a sa propre revocation.'
        exit 0
    }
    $stage='fichiers-du-paquet'
    if (-not (Test-Path -LiteralPath $ClientExe -PathType Leaf)) { throw 'CLIENT_EXE_MISSING' }
    $stage='chargement-du-tunnel'
    . (Join-Path $PSScriptRoot 'eidolon-auto-tunnel.ps1')
    $stage='connexion-SSH'
    Start-EidolonTunnel $Server $User $Port
    if (Test-Path -LiteralPath $file) {
        $stage='lecture-appairage-Windows'
        $key = Read-EidolonPairing (Get-Content -LiteralPath $file -Raw) $binding
    } else {
        $stage='premier-appairage-SSH'
        Write-Host '[INFO] Premier appairage : authentification SSH requise une seule fois pour recuperer la cle.'
        Write-Host '[INFO] Le tunnel automatique a verifie le serveur SSH connu.'
        # Host key must already be trusted by the existing tunnel. No key on stdout.
        $lines = @(& ssh -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519 "$User@$Server" "cat -- $RemoteKey")
        if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) { throw 'PAIRING_SSH_FAILED' }
        $key = [string]$lines[0]
        if (-not (Test-EidolonKey $key)) { throw 'PAIRING_KEY_INVALID' }
        $stage='enregistrement-appairage-Windows'
        $encrypted = Protect-EidolonPairing $key $binding
        [void][IO.Directory]::CreateDirectory($directory)
        $stream = [IO.File]::Open($file,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try {
            $bytes = [Text.Encoding]::ASCII.GetBytes($encrypted)
            $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true)
        } finally { $stream.Dispose() }
    }
    $stage='demarrage-du-client'
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = (Resolve-Path -LiteralPath $ClientExe).Path
    $start.WorkingDirectory = Split-Path -Parent $start.FileName
    $start.Arguments = "--port $Port"
    $start.UseShellExecute = $false
    $start.EnvironmentVariables['EIDOLON_CONVERSATION_KEY'] = $key
    try {
        $process = [Diagnostics.Process]::Start($start)
        $process.Dispose()
    } finally { $start.EnvironmentVariables.Remove('EIDOLON_CONVERSATION_KEY'); $key=$null; $lines=$null }
    Write-Host '[INFO] Eidolon lance : ouverture automatique de la conversation.'
} catch {
    # Only fixed codes/stages and a source line number: never raw exceptions or credentials.
    $known=@('WINDOWS_REQUIRED','PAIRING_TARGET_INVALID','CLIENT_EXE_MISSING','PAIRING_KEY_INVALID',
        'PAIRING_BINDING_INVALID','PAIRING_SSH_FAILED','TUNNEL_PORT_OCCUPIED','TUNNEL_TARGET_INVALID',
        'TUNNEL_BUSY','TUNNEL_CONNECTION_FAILED')
    $code='WINDOWS_OPERATION_FAILED'
    if ($known -ccontains $_.Exception.Message) { $code=$_.Exception.Message }
    $kind=$_.Exception.GetType().Name
    $line=$_.InvocationInfo.ScriptLineNumber
    $source=[IO.Path]::GetFileName($_.InvocationInfo.ScriptName)
    $diagnostic="Etape=$stage ; Code=$code ; Type=$kind ; Source=$source ; Ligne=$line"
    Write-Host ('[ERREUR] '+$diagnostic)
    try {
        $logs=Join-Path $env:LOCALAPPDATA 'Eidolon'
        [void][IO.Directory]::CreateDirectory($logs)
        [IO.File]::WriteAllText((Join-Path $logs 'last-launch-error.txt'),$diagnostic)
    } catch { }
    Write-Host '[INFO] Lancez Diagnostiquer-Eidolon.cmd et transmettez la ligne ERREUR. Aucun mot de passe ni cle dans ce diagnostic.'
    exit 2
}
