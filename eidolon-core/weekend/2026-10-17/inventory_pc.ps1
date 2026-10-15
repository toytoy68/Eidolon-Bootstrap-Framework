# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : weekend/2026-10-17/inventory_pc.ps1
# Description : Read-only PC inventory; no tunnel, installation or credential access
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port = 8767)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ssh = Get-Command ssh.exe -ErrorAction SilentlyContinue
$git = Get-Command git.exe -ErrorAction SilentlyContinue
$python = Get-Command python.exe -ErrorAction SilentlyContinue
$listeners = @()
try { $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object LocalAddress,LocalPort) } catch { }
[ordered]@{
    schema = 'eidolon-weekend-pc-inventory/1'
    captured_at = (Get-Date).ToUniversalTime().ToString('o')
    windows = [Environment]::OSVersion.Version.ToString()
    powershell = $PSVersionTable.PSVersion.ToString()
    ssh_available = ($null -ne $ssh)
    git_available = ($null -ne $git)
    python_available = ($null -ne $python)
    requested_port = $Port
    listeners = $listeners
    qualification = 'NOT_EVALUATED'
    physical_microphone = 'NOT_TESTED'
    physical_camera = 'NOT_TESTED'
} | ConvertTo-Json -Depth 4
