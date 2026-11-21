# Starts the clinic with no command windows, then opens the browser.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$logDir = Join-Path $env:LOCALAPPDATA "EndoEMR"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Show-Message([string]$text) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($text, "Endo EMR") | Out-Null
}

function Test-Url([string]$url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $url
        return $response.StatusCode -ge 200
    } catch {
        return $false
    }
}

function Find-Python {
    foreach ($candidate in @(
        (Join-Path $root "venv\Scripts\python.exe"),
        (Join-Path $backend "venv\Scripts\python.exe")
    )) {
        if (Test-Path $candidate) { return $candidate }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Start-Hidden([string]$file, [string]$arguments, [string]$directory, [string]$logPath) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $file
    $info.Arguments = $arguments
    $info.WorkingDirectory = $directory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    [void]$process.Start()
    Set-Content -Path $logPath -Value ("Started " + $file + " " + $arguments)
    return $process
}

$apiUp = Test-Url "http://127.0.0.1:8000/health"
$appUp = Test-Url "http://127.0.0.1:5173/"
if ($apiUp -and $appUp) {
    Start-Process "http://127.0.0.1:5173/"
    exit 0
}

if (-not $apiUp) {
    $python = Find-Python
    if (-not $python) {
        Show-Message "Python was not found. Install Python 3.10 or newer, then open Endo EMR again."
        exit 1
    }
    Start-Hidden $python "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" $backend (Join-Path $logDir "api.log") | Out-Null
}

if (-not $appUp) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Show-Message "Node.js was not found. Install it from https://nodejs.org and open Endo EMR again."
        exit 1
    }
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npm) {
            Show-Message "npm was not found, so the clinic page could not be prepared."
            exit 1
        }
        $install = Start-Hidden $npm.Source "install" $frontend (Join-Path $logDir "npm-install.log")
        $install.WaitForExit()
        if ($install.ExitCode -ne 0) {
            Show-Message "The clinic page could not be prepared. Details are in $logDir"
            exit 1
        }
    }
    $vite = Join-Path $frontend "node_modules\vite\bin\vite.js"
    Start-Hidden $node.Source ("`"$vite`" --host 127.0.0.1 --port 5173 --strictPort") $frontend (Join-Path $logDir "app.log") | Out-Null
}

$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    if ((Test-Url "http://127.0.0.1:8000/health") -and (Test-Url "http://127.0.0.1:5173/")) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}

if ($ready) {
    Start-Process "http://127.0.0.1:5173/"
} else {
    Show-Message "Endo EMR did not finish starting. Details are in $logDir"
    exit 1
}
