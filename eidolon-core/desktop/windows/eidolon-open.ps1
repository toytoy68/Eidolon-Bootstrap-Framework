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
    if (-not (Test-Path -LiteralPath $ClientExe -PathType Leaf)) { throw 'CLIENT_EXE_MISSING' }
    if (Test-Path -LiteralPath $file) {
        $key = Read-EidolonPairing (Get-Content -LiteralPath $file -Raw) $binding
    } else {
        Write-Host '[INFO] Premier appairage : authentification SSH requise une seule fois pour recuperer la cle.'
        Write-Host '[INFO] Le tunnel doit avoir deja valide la cle SSH du serveur.'
        # Host key must already be trusted by the existing tunnel. No key on stdout.
        $lines = @(& ssh -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519 "$User@$Server" "cat -- $RemoteKey")
        if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) { throw 'PAIRING_SSH_FAILED' }
        $key = [string]$lines[0]
        if (-not (Test-EidolonKey $key)) { throw 'PAIRING_KEY_INVALID' }
        $encrypted = Protect-EidolonPairing $key $binding
        [void][IO.Directory]::CreateDirectory($directory)
        $stream = [IO.File]::Open($file,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try {
            $bytes = [Text.Encoding]::ASCII.GetBytes($encrypted)
            $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true)
        } finally { $stream.Dispose() }
    }
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
    # Never print exceptions: command arguments, JSON or DPAPI values may be private.
    Write-Host '[ERREUR] Ouverture impossible. Verifiez le tunnel, le client et l''appairage local. Pour refaire l''appairage : -ForgetPairing.'
    exit 2
}
