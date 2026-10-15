# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : eidolon-resident.ps1
# Description : Windows resident tray host for the pinned Eidolon native client
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ClientExe,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [ValidateRange(1024,65535)][int]$Port = 8767,
    [switch]$Run
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$EidolonExe = Get-Item -LiteralPath $ClientExe
if ($EidolonExe.PSIsContainer -or $EidolonExe.Extension -ne '.exe' -or ($EidolonExe.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'EIDOLON_CLIENT_INVALID' }
if ((Get-FileHash -LiteralPath $EidolonExe.FullName -Algorithm SHA256).Hash -ne $ExpectedSha256) { throw 'EIDOLON_CLIENT_HASH_MISMATCH' }
if (-not $Run) {
    [ordered]@{state='PREVIEW'; product='Eidolon Core'; organization='Eidolon Core Technologies (ECT)'; resident=$true; port=$Port; client_sha256=$ExpectedSha256.ToLower(); effects='NONE'} | ConvertTo-Json -Compress
    exit 0
}
if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') { throw 'EIDOLON_STA_REQUIRED' }
$EidolonCreated = $false
$EidolonMutex = New-Object Threading.Mutex($true, 'Local\EidolonResident', [ref]$EidolonCreated)
if (-not $EidolonCreated) { $EidolonMutex.Dispose(); throw 'EIDOLON_ALREADY_RUNNING' }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class EidolonNativeWindow {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@
$script:EidolonProcess = $null
$EidolonTray = New-Object Windows.Forms.NotifyIcon
$EidolonTray.Icon = [Drawing.Icon]::ExtractAssociatedIcon($EidolonExe.FullName)
$EidolonTray.Text = 'Eidolon — ouvrir la conversation'
$EidolonMenu = New-Object Windows.Forms.ContextMenuStrip
function Show-Eidolon {
    $connection = New-Object Net.Sockets.TcpClient
    try {
        $attempt = $connection.ConnectAsync('127.0.0.1', $Port)
        if (-not $attempt.Wait(1500) -or -not $connection.Connected) { throw 'EIDOLON_TUNNEL_UNAVAILABLE' }
    } finally { $connection.Dispose() }
    if ($null -eq $script:EidolonProcess -or $script:EidolonProcess.HasExited) {
        if ((Get-FileHash -LiteralPath $EidolonExe.FullName -Algorithm SHA256).Hash -ne $ExpectedSha256) { throw 'EIDOLON_CLIENT_CHANGED' }
        $start = New-Object Diagnostics.ProcessStartInfo
        $start.FileName = $EidolonExe.FullName
        $start.Arguments = '--port ' + $Port
        $start.UseShellExecute = $false
        $script:EidolonProcess = [Diagnostics.Process]::Start($start)
    } else {
        $script:EidolonProcess.Refresh()
        [void][EidolonNativeWindow]::ShowWindow($script:EidolonProcess.MainWindowHandle, 9)
        [void][EidolonNativeWindow]::SetForegroundWindow($script:EidolonProcess.MainWindowHandle)
    }
}
$EidolonOpen = $EidolonMenu.Items.Add('Ouvrir Eidolon')
$EidolonOpen.add_Click({ try { Show-Eidolon } catch { [void][Windows.Forms.MessageBox]::Show("Vérifiez le tunnel Core et l'empreinte du client, puis réessayez.", 'Eidolon') } })
$EidolonClose = $EidolonMenu.Items.Add('Fermer la conversation')
$EidolonClose.add_Click({ if ($null -ne $script:EidolonProcess -and -not $script:EidolonProcess.HasExited) { [void]$script:EidolonProcess.CloseMainWindow() } })
$EidolonQuit = $EidolonMenu.Items.Add('Quitter Eidolon')
$EidolonQuit.add_Click({
    if ($null -ne $script:EidolonProcess -and -not $script:EidolonProcess.HasExited) {
        [void]$script:EidolonProcess.CloseMainWindow()
        if (-not $script:EidolonProcess.WaitForExit(2000)) {
            [void][Windows.Forms.MessageBox]::Show("Fermez la fenêtre Eidolon avant de quitter. Aucun processus n'a été forcé.", 'Eidolon')
            return
        }
    }
    [Windows.Forms.Application]::ExitThread()
})
$EidolonTray.ContextMenuStrip = $EidolonMenu
$EidolonTray.add_DoubleClick({ $EidolonOpen.PerformClick() })
$EidolonTray.Visible = $true
try {
    try { Show-Eidolon } catch {
        $EidolonTray.ShowBalloonTip(5000, 'Eidolon', 'Core est indisponible. Ouvrez le tunnel puis choisissez Ouvrir Eidolon.', [Windows.Forms.ToolTipIcon]::Info)
    }
    [Windows.Forms.Application]::Run()
} finally {
    $EidolonTray.Visible = $false
    $EidolonTray.Dispose(); $EidolonMenu.Dispose()
    $EidolonMutex.ReleaseMutex(); $EidolonMutex.Dispose()
}
