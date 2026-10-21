# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : build-launcher.ps1
# Description : Compilation du lanceur GUI avec l'icone Eidolon existante
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[void][IO.Directory]::CreateDirectory($OutputDirectory)
$output=Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path 'Eidolon.exe'
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$icon=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../tauri/icons/icon.ico')).Path
& $compiler /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll /reference:System.Security.dll /reference:System.Web.Extensions.dll "/win32icon:$icon" "/out:$output" (Join-Path $PSScriptRoot 'EidolonLauncher.cs')
if ($LASTEXITCODE -ne 0) { throw 'LAUNCHER_COMPILATION_FAILED' }
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw 'LAUNCHER_EXE_MISSING' }

$camera=Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path 'Eidolon-camera.exe'
& $compiler /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$icon" "/out:$camera" (Join-Path $PSScriptRoot 'PixyControl.cs')
if ($LASTEXITCODE -ne 0) { throw 'CAMERA_COMPILATION_FAILED' }
