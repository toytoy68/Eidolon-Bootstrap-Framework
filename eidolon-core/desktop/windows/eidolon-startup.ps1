# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : eidolon-startup.ps1
# Description : Preview or explicitly register/remove current-user Eidolon startup
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ResidentScript,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ScriptSha256,
    [Parameter(Mandatory=$true)][string]$ClientExe,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ClientSha256,
    [ValidateRange(1024,65535)][int]$Port = 8767,
    [switch]$Remove,
    [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$EidolonScript = Get-Item -LiteralPath $ResidentScript
$EidolonClient = Get-Item -LiteralPath $ClientExe
foreach ($item in @($EidolonScript, $EidolonClient)) {
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.FullName.Contains('"')) { throw 'EIDOLON_STARTUP_PATH_INVALID' }
}
if ($EidolonScript.Extension -ne '.ps1' -or $EidolonClient.Extension -ne '.exe') { throw 'EIDOLON_STARTUP_EXTENSION_INVALID' }
if ((Get-FileHash -LiteralPath $EidolonScript.FullName -Algorithm SHA256).Hash -ne $ScriptSha256 -or
    (Get-FileHash -LiteralPath $EidolonClient.FullName -Algorithm SHA256).Hash -ne $ClientSha256) { throw 'EIDOLON_STARTUP_HASH_MISMATCH' }
$EidolonPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$EidolonCommand = '"' + $EidolonPowerShell + '" -NoProfile -STA -WindowStyle Hidden -File "' + $EidolonScript.FullName + '" -ClientExe "' + $EidolonClient.FullName + '" -ExpectedSha256 ' + $ClientSha256 + ' -Port ' + $Port + ' -Run'
$EidolonRegistry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not $Apply) {
    [ordered]@{state='PREVIEW'; operation=$(if ($Remove) {'REMOVE'} else {'REGISTER'}); command=$EidolonCommand; scope='current-user'; effects='NONE'} | ConvertTo-Json -Compress
    exit 0
}
$current = Get-ItemProperty -LiteralPath $EidolonRegistry -Name 'EidolonCore' -ErrorAction SilentlyContinue
if ($null -ne $current -and $current.EidolonCore -ne $EidolonCommand) { throw 'EIDOLON_STARTUP_CONFLICT' }
if ($Remove) {
    if ($null -ne $current) { Remove-ItemProperty -LiteralPath $EidolonRegistry -Name 'EidolonCore' }
} else {
    if (-not (Test-Path -LiteralPath $EidolonRegistry)) { [void](New-Item -Path $EidolonRegistry -Force) }
    [void](New-ItemProperty -LiteralPath $EidolonRegistry -Name 'EidolonCore' -Value $EidolonCommand -PropertyType String -Force)
}
[ordered]@{state='APPLIED'; operation=$(if ($Remove) {'REMOVE'} else {'REGISTER'}); scope='current-user'} | ConvertTo-Json -Compress
