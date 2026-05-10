param(
    [switch]$CreateVenv,
    [switch]$SkipDependencyInstall,
    [switch]$SkipFrontendInstall,
    [string]$ChromaPath = "",
    [int]$BackendPort = 8765,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$RuntimeConfigPath = Join-Path $FrontendRoot "public\runtime-config.js"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Test-PortAvailable {
    param([int]$Port)
    try {
        $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $Port)
        $Listener.Start()
        $Listener.Stop()
        return $true
    }
    catch {
        return $false
    }
}

function Get-AvailablePort {
    param([int]$PreferredPort)
    $Port = $PreferredPort
    while (-not (Test-PortAvailable -Port $Port)) {
        $Port += 1
    }
    return $Port
}

function Stop-BackendProcess {
    if ($script:BackendProcess -and -not $script:BackendProcess.HasExited) {
        Stop-Process -Id $script:BackendProcess.Id -Force
        try {
            Wait-Process -Id $script:BackendProcess.Id -Timeout 5 -ErrorAction Stop
        }
        catch {
            Write-Warning "Backend process $($script:BackendProcess.Id) did not exit cleanly within 5 seconds."
        }
    }
}

Set-Location $ProjectRoot

if ($CreateVenv -or -not (Test-Path $VenvPython)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}

if (-not $SkipDependencyInstall) {
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

if ($ChromaPath.Trim()) {
    $env:RAGSCOPE_CHROMA_PATH = $ChromaPath
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is required for the React UI. Install Node.js LTS."
}

if (-not $SkipFrontendInstall) {
    Push-Location $FrontendRoot
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

$BackendPort = Get-AvailablePort -PreferredPort $BackendPort
$FrontendPort = Get-AvailablePort -PreferredPort $FrontendPort
$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"

$RuntimeConfig = @{
    apiBase = $BackendUrl
    defaultChromaPath = $ChromaPath
} | ConvertTo-Json -Depth 3

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $RuntimeConfigPath) | Out-Null
Set-Content -LiteralPath $RuntimeConfigPath -Encoding UTF8 -Value "window.RAGSCOPE_CONFIG = $RuntimeConfig; window.CHROMADB_VISUALIZER_CONFIG = window.RAGSCOPE_CONFIG;"

Write-Host "Starting FastAPI backend at $BackendUrl"
$BackendArgs = @(
    "-m",
    "uvicorn",
    "backend:app",
    "--host",
    "127.0.0.1",
    "--port",
    "$BackendPort"
)
$script:BackendProcess = Start-Process -FilePath $VenvPython -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -ArgumentList $BackendArgs
$ExitEvent = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    if ($script:BackendProcess -and -not $script:BackendProcess.HasExited) {
        Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    Write-Host "Starting React UI at $FrontendUrl"
    Set-Location $FrontendRoot
    npx vite --host 127.0.0.1 --port $FrontendPort --strictPort
}
finally {
    if ($ExitEvent) {
        Unregister-Event -SourceIdentifier PowerShell.Exiting -ErrorAction SilentlyContinue
        Remove-Job -Id $ExitEvent.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-BackendProcess
    Set-Location $ProjectRoot
}
