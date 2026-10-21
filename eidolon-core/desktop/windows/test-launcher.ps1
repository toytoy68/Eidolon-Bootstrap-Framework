# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test-launcher.ps1
# Description : Test du lanceur et de son raccourci sans Core ni identifiants
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
param([Parameter(Mandatory=$true)][string]$LauncherExe)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$directory=Join-Path ([IO.Path]::GetTempPath()) ('Eidolon test & espace '+[guid]::NewGuid())
[void][IO.Directory]::CreateDirectory($directory)
$shortcutPath=Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Eidolon.lnk'
if (Test-Path -LiteralPath $shortcutPath) { throw 'TEST_SHORTCUT_ALREADY_EXISTS' }
$shell=$null
$link=$null
try {
    $exe=Join-Path $directory 'Eidolon.exe'
    Copy-Item -LiteralPath $LauncherExe -Destination $exe
    # The native launcher must fail safely without a personalized config: no PowerShell or network.
    $process=Start-Process -FilePath $exe -ArgumentList '--diagnostic' -PassThru
    $null=$process.Handle
    try {
        if (-not $process.WaitForExit(10000)) { $process.Kill(); throw 'LAUNCHER_TIMEOUT' }
        if ($process.ExitCode -ne 2) { throw 'MISSING_CONFIG_ACCEPTED' }
    } finally { $process.Dispose() }
    $report=Get-Content (Join-Path $env:LOCALAPPDATA 'Eidolon/last-launch-error.txt') -Raw
    if ($report -notmatch 'CONNECTION_CONFIG_MISSING') { throw 'NATIVE_DIAGNOSTIC_MISSING' }
    $process=Start-Process -FilePath $exe -ArgumentList '--shortcut' -PassThru
    $null=$process.Handle
    try {
        if (-not $process.WaitForExit(10000)) { $process.Kill(); throw 'SHORTCUT_TIMEOUT' }
        if ($process.ExitCode -ne 0) { throw 'SHORTCUT_EXIT_FAILED' }
    } finally { $process.Dispose() }
    $shell=New-Object -ComObject WScript.Shell
    $link=$shell.CreateShortcut($shortcutPath)
    if ($link.TargetPath -ne $exe -or $link.WorkingDirectory.TrimEnd('\') -ne $directory.TrimEnd('\') -or $link.IconLocation -ne "$exe,0") { throw 'SHORTCUT_CONTENT_FAILED' }
    $icon=[Drawing.Icon]::ExtractAssociatedIcon($exe)
    try { if ($null -eq $icon -or $icon.Width -lt 16) { throw 'LAUNCHER_ICON_MISSING' } } finally { if ($null -ne $icon) { $icon.Dispose() } }
    Write-Host '[OK] Lanceur execute, chemin avec espaces et &, raccourci et icone verifies.'
} finally {
    if ($null -ne $link) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($link) }
    if ($null -ne $shell) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) }
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Remove-Item -LiteralPath $directory -Recurse -Force
}
