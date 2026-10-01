$ErrorActionPreference = 'Stop'

$python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -eq $python) {
    throw 'Python Launcher was not found. Install Python 3.11 for Windows first.'
}

Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
        Write-Output 'Creating Python 3.11 environment...'
        & py.exe -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }

    Write-Output 'Installing pinned packages...'
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }

    $obsExe = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe'
    if (Test-Path -LiteralPath $obsExe) {
        & .\obs_setup\apply.ps1
    } else {
        Write-Output 'OBS Studio was not found. Install it before using Telegram output.'
    }

    Write-Output 'Setup complete. Run Start.cmd.'
} finally {
    Pop-Location
}
