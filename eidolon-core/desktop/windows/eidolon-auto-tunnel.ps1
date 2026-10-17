# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : eidolon-auto-tunnel.ps1
# Description : Tunnel SSH automatique avant ouverture du client Windows
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
# Function-only module: importing it never starts a connection.
function Test-EidolonSshOwner($Owner, [string]$SshPath, [string]$Server, [string]$User, [int]$Port) {
    if ($null -eq $Owner -or $Owner.Name -ine 'ssh.exe' -or
        [string]::IsNullOrEmpty($Owner.ExecutablePath) -or
        -not [string]::Equals($Owner.ExecutablePath, $SshPath, [StringComparison]::OrdinalIgnoreCase) -or
        [string]::IsNullOrEmpty($Owner.CommandLine)) { return $false }
    $forward=[regex]::Escape("127.0.0.1:${Port}:127.0.0.1:${Port}")
    $destination=[regex]::Escape("$User@$Server")
    return ($Owner.CommandLine -cmatch ('(?:^|\s)-L\s+"?'+$forward+'"?(?=\s|$)') -and
        $Owner.CommandLine -cmatch ('(?:^|\s)"?'+$destination+'"?(?=\s|$)'))
}
function Test-EidolonTunnelReady([string]$SshPath, [string]$Server, [string]$User, [int]$Port, [int]$ExpectedPid=0) {
    $listeners=@(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $false }
    foreach ($listener in $listeners) {
        if ($listener.LocalAddress -ne '127.0.0.1') { throw 'TUNNEL_PORT_OCCUPIED' }
        if ($ExpectedPid -ne 0 -and $listener.OwningProcess -ne $ExpectedPid) { throw 'TUNNEL_PORT_OCCUPIED' }
        $owner=Get-CimInstance Win32_Process -Filter ("ProcessId = "+[int]$listener.OwningProcess) -ErrorAction Stop
        if (-not (Test-EidolonSshOwner $owner $SshPath $Server $User $Port)) { throw 'TUNNEL_PORT_OCCUPIED' }
    }
    return $true
}
function Wait-EidolonTunnel($Process, [string]$SshPath, [string]$Server, [string]$User, [int]$Port, [int]$Seconds) {
    $deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) { return $false }
        if (Test-EidolonTunnelReady $SshPath $Server $User $Port $Process.Id) { return $true }
        [void]$Process.WaitForExit(200)
    }
    return $false
}
function Start-EidolonTunnel([string]$Server, [string]$User, [int]$Port) {
    if ($Server -notmatch '\A[A-Za-z0-9][A-Za-z0-9.-]{0,251}\z' -or
        $User -notmatch '\A[A-Za-z_][A-Za-z0-9_.-]{0,31}\z' -or $Port -lt 1024 -or $Port -gt 65535) { throw 'TUNNEL_TARGET_INVALID' }
    $ssh=(Get-Command ssh.exe -CommandType Application -ErrorAction Stop).Source
    $mutex=New-Object Threading.Mutex($false, ("Local\EidolonAutoTunnel-"+$Port))
    $locked=$false
    try {
        try { $locked=$mutex.WaitOne(135000) } catch [Threading.AbandonedMutexException] { $locked=$true }
        if (-not $locked) { throw 'TUNNEL_BUSY' }
        if (Test-EidolonTunnelReady $ssh $Server $User $Port) {
            Write-Host '[INFO] Tunnel Eidolon existant reutilise.'
            return
        }
        $baseArgs=@('-N','-L',"127.0.0.1:${Port}:127.0.0.1:${Port}",
            '-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519',
            '-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1',
            '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3')
        # Try an existing key/agent silently. Never save or pass an SSH password.
        $process=Start-Process -FilePath $ssh -ArgumentList ($baseArgs+@('-o','BatchMode=yes','--',"$User@$Server")) -WindowStyle Hidden -PassThru
        $ready=$false
        try {
            $ready=Wait-EidolonTunnel $process $ssh $Server $User $Port 12
        } finally {
            if (-not $ready -and -not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
            $process.Dispose()
        }
        if ($ready) { Write-Host '[OK] Tunnel Eidolon ouvert automatiquement.'; return }
        Write-Host '[INFO] Authentification SSH : entrez le mot de passe dans la fenetre ouverte automatiquement.'
        $process=Start-Process -FilePath $ssh -ArgumentList ($baseArgs+@('--',"$User@$Server")) -WindowStyle Normal -PassThru
        $ready=$false
        try {
            $ready=Wait-EidolonTunnel $process $ssh $Server $User $Port 120
            if (-not $ready) { throw 'TUNNEL_CONNECTION_FAILED' }
        } finally {
            if (-not $ready -and -not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
            $process.Dispose()
        }
        Write-Host '[OK] Tunnel Eidolon ouvert automatiquement.'
    } finally {
        if ($locked) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}
