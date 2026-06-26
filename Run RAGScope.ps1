param(
    [switch]$CreateVenv,
    [switch]$SkipDependencyInstall,
    [switch]$SkipFrontendInstall,
    [string]$ChromaPath = "",
    [int]$BackendPort = 8765,
    [int]$FrontendPort = 5173
)

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherPath = Join-Path $ScriptRoot "scripts\Run RAGScope.ps1"

& $LauncherPath `
    -CreateVenv:$CreateVenv `
    -SkipDependencyInstall:$SkipDependencyInstall `
    -SkipFrontendInstall:$SkipFrontendInstall `
    -ChromaPath $ChromaPath `
    -BackendPort $BackendPort `
    -FrontendPort $FrontendPort
