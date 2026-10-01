$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$obsRoot = Join-Path $env:APPDATA 'obs-studio'
$obsExe = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe'
if (-not (Test-Path -LiteralPath $obsExe)) { throw 'OBS Studio was not found.' }

$profileDir = Join-Path $obsRoot 'basic\profiles\MonkeyFacesMeme'
$scenePath = Join-Path $obsRoot 'basic\scenes\MonkeyFacesMeme.json'
$running = @(Get-Process -Name obs64 -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and ((Test-Path -LiteralPath $profileDir) -or (Test-Path -LiteralPath $scenePath))) {
    throw 'Close OBS before updating the MonkeyFacesMeme profile.'
}
$backupRoot = Join-Path (Join-Path $env:LOCALAPPDATA 'MonkeyFacesMeme') 'obs-backups'
$backupDir = Join-Path $backupRoot ('install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
foreach ($path in @((Join-Path $profileDir 'basic.ini'), $scenePath)) {
    if (Test-Path -LiteralPath $path) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Copy-Item -LiteralPath $path -Destination $backupDir -Force
    }
}
New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'basic.ini') -Destination (Join-Path $profileDir 'basic.ini')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'MonkeyFacesMeme.json') -Destination $scenePath
Write-Output 'Installed MonkeyFacesMeme profile: 720x720 at 30 FPS.'
Write-Output 'Existing OBS profiles and scene collections were preserved.'
foreach ($process in $running) {
    if (-not $process.CloseMainWindow()) {
        Write-Output 'SETTINGS INSTALLED. Exit OBS via File > Exit, then run .\start_telegram.ps1.'
        exit 0
    }
    if (-not $process.WaitForExit(20000)) {
        Write-Output 'SETTINGS INSTALLED. Finish exiting OBS, then run .\start_telegram.ps1.'
        exit 0
    }
}
