$ErrorActionPreference = "Stop"

$uiHost = if ([string]::IsNullOrWhiteSpace($env:COMPANION_UI_HOST)) { "127.0.0.1" } else { $env:COMPANION_UI_HOST }
$startPort = if ([string]::IsNullOrWhiteSpace($env:COMPANION_UI_PORT)) { 3000 } else { [int]$env:COMPANION_UI_PORT }
$maxPort = if ([string]::IsNullOrWhiteSpace($env:COMPANION_UI_MAX_PORT)) { ($startPort + 20) } else { [int]$env:COMPANION_UI_MAX_PORT }

if ($maxPort -lt $startPort) {
    throw "COMPANION_UI_MAX_PORT ($maxPort) must be >= COMPANION_UI_PORT ($startPort)."
}

function Test-PortAvailable {
    param(
        [string]$BindHost,
        [int]$Port
    )
    try {
        $address = [System.Net.Dns]::GetHostAddresses($BindHost) | Select-Object -First 1
        $listener = [System.Net.Sockets.TcpListener]::new($address, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

$uiPort = $null
for ($candidate = $startPort; $candidate -le $maxPort; $candidate++) {
    if (Test-PortAvailable -BindHost $uiHost -Port $candidate) {
        $uiPort = $candidate
        break
    }
}

if ($null -eq $uiPort) {
    throw "No open UI port found in range $startPort-$maxPort on $uiHost."
}

if ($uiPort -ne $startPort) {
    Write-Host "Port $startPort is in use; using $uiPort instead."
}

python -m uvicorn companion_app.server:app --app-dir src --host $uiHost --port $uiPort
