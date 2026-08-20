[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/"
}

$localDirectory = Join-Path $Root ".local"
if (-not (Test-Path -LiteralPath $localDirectory)) {
    New-Item -ItemType Directory -Path $localDirectory | Out-Null
}

$safeRoot = $Root.Replace("'", "''")
$command = "`$Host.UI.RawUI.WindowTitle = 'Recruiting Screening and Scheduling'; Set-Location -LiteralPath '$safeRoot'; uv run python -m apps.api --db .local/demo.sqlite3 --reset --port 8104"
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command
)

Write-Host "Recruiting demo starting at http://127.0.0.1:8104/"
Write-Host "API health: http://127.0.0.1:8104/health"
