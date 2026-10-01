param([switch]$RestartOBS)

$ErrorActionPreference = 'Stop'
$launcherMutex = [Threading.Mutex]::new($false, 'Local\MonkeyFacesMemeLauncher')
$ownsLauncherMutex = $false
try {
    try {
        $ownsLauncherMutex = $launcherMutex.WaitOne(0)
    } catch [Threading.AbandonedMutexException] {
        $ownsLauncherMutex = $true
    }
    if (-not $ownsLauncherMutex) {
        Write-Output 'MonkeyFacesMeme launcher is already running.'
        exit 0
    }

function Invoke-OBSNormalModePrompt {
    try {
        Add-Type -AssemblyName UIAutomationClient
        $dialogCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty,
            'OBS Studio Crash Detected'
        )
        $dialog = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
            [System.Windows.Automation.TreeScope]::Children, $dialogCondition
        )
        if ($null -eq $dialog) { return $false }
        $typeCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Button
        )
        $nameCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty,
            'Run in Normal Mode'
        )
        $buttonCondition = New-Object System.Windows.Automation.AndCondition(
            $typeCondition, $nameCondition
        )
        $button = $dialog.FindFirst(
            [System.Windows.Automation.TreeScope]::Descendants, $buttonCondition
        )
        if ($null -eq $button) { return $false }
        $invoke = $button.GetCurrentPattern(
            [System.Windows.Automation.InvokePattern]::Pattern
        )
        $invoke.Invoke()
        return $true
    } catch {
        return $false
    }
}

$obsExe = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe'
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Python environment not found. Run Setup.cmd first.'
}
if (-not (Test-Path -LiteralPath $obsExe)) {
    throw 'OBS Studio was not found in C:\Program Files\obs-studio.'
}
$profileFile = Join-Path $env:APPDATA 'obs-studio\basic\profiles\MonkeyFacesMeme\basic.ini'
if (-not (Test-Path -LiteralPath $profileFile)) {
    & (Join-Path $PSScriptRoot 'obs_setup\apply.ps1')
}
$existingApp = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath) -eq [IO.Path]::GetFullPath($pythonExe) -and $_.CommandLine -match 'main\.py'
})
$runningOBS = @(Get-Process -Name obs64 -ErrorAction SilentlyContinue)
if ($runningOBS.Count -gt 0) {
    if (-not $RestartOBS) {
        $obsUserConfig = Join-Path $env:APPDATA 'obs-studio\user.ini'
        $activeConfig = Get-Content -LiteralPath $obsUserConfig -Raw -ErrorAction SilentlyContinue
        if ($activeConfig -notmatch '(?m)^ProfileDir=MonkeyFacesMeme\s*$' -or
            $activeConfig -notmatch '(?m)^SceneCollectionFile=MonkeyFacesMeme\.json\s*$') {
            Write-Output 'OBS is running with another profile. Restart it with:'
            Write-Output 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start_telegram.ps1 -RestartOBS'
            exit 1
        }
        Write-Output 'OBS is already running with MonkeyFacesMeme; reusing it.'
    } else {
        $dataRoot = Join-Path $env:LOCALAPPDATA 'MonkeyFacesMeme'
        $backupRoot = Join-Path $dataRoot 'obs-backups'
        $backupDir = Join-Path $backupRoot ('restart-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        $obsConfigRoot = Join-Path $env:APPDATA 'obs-studio'
        foreach ($entry in @('basic', 'user.ini', 'global.ini')) {
            $source = Join-Path $obsConfigRoot $entry
            if (Test-Path -LiteralPath $source) {
                Copy-Item -LiteralPath $source -Destination $backupDir -Recurse
            }
        }
        foreach ($process in $runningOBS) {
            if ($process.Path -ne $obsExe) { throw 'Unexpected OBS executable path; refusing to stop it.' }
            $closed = $process.CloseMainWindow()
            if (-not $closed -or -not $process.WaitForExit(5000)) {
                Write-Output ('Stopping existing OBS process ' + $process.Id)
                Stop-Process -Id $process.Id -Force
                if (-not $process.WaitForExit(5000)) { throw 'OBS did not stop.' }
            }
        }
        Write-Output ('Saved settings backup: ' + $backupDir)
        # copy the profile only after OBS has fully closed
        $profileDir = Join-Path $obsConfigRoot 'basic\profiles\MonkeyFacesMeme'
        $scenePath = Join-Path $obsConfigRoot 'basic\scenes\MonkeyFacesMeme.json'
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'obs_setup\basic.ini') `
                  -Destination (Join-Path $profileDir 'basic.ini') -Force
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'obs_setup\MonkeyFacesMeme.json') `
                  -Destination $scenePath -Force
        Write-Output 'Applied MonkeyFacesMeme scene: full-frame crop and Lanczos scaling.'
    }
}
$dataRoot = Join-Path $env:LOCALAPPDATA 'MonkeyFacesMeme'
$logRoot = Join-Path $dataRoot 'logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$runStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$appLog = Join-Path $logRoot ("camera-$runStamp.log")
$appErrorLog = Join-Path $logRoot ("camera-$runStamp-error.log")
$appWasStarted = $false
if ($existingApp.Count -eq 0) {
    $app = Start-Process -FilePath $pythonExe -ArgumentList 'main.py --telegram' -WorkingDirectory $PSScriptRoot -WindowStyle Normal -RedirectStandardOutput $appLog -RedirectStandardError $appErrorLog -PassThru
    $appWasStarted = $true
    Write-Output ('MonkeyFacesMeme launch requested. PID: ' + $app.Id)
} else {
    Write-Output 'MonkeyFacesMeme is already running. Press T if the output window is closed.'
}

if ($appWasStarted) {
    Write-Output 'Press Enter in the MonkeyFacesMeme window to start the camera.'
    $cameraDeadline = (Get-Date).AddMinutes(10)
    $cameraReady = $false
    while ((Get-Date) -lt $cameraDeadline) {
        if ($app.HasExited) { break }
        if ((Test-Path -LiteralPath $appLog) -and
            (Get-Item -LiteralPath $appLog).LastWriteTime -ge $app.StartTime) {
            $appText = Get-Content -LiteralPath $appLog -Raw -ErrorAction SilentlyContinue
            if ($appText -match 'MonkeyFacesMeme output ready: 720x720') {
                $cameraReady = $true
                break
            }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $cameraReady) {
        throw ("Camera did not produce the 720x720 feed. Check logs: $appLog and $appErrorLog")
    }

}
$runningOBS = @(Get-Process -Name obs64 -ErrorAction SilentlyContinue)
if ($runningOBS.Count -eq 0) {
    $obs = Start-Process -FilePath $obsExe -ArgumentList '--profile "MonkeyFacesMeme" --collection "MonkeyFacesMeme" --scene "MonkeyFacesMeme" --startvirtualcam' -WorkingDirectory (Split-Path $obsExe -Parent) -WindowStyle Normal -PassThru
    Write-Output ('OBS launch requested with MonkeyFacesMeme and Virtual Camera. PID: ' + $obs.Id)
    # a cold OBS start can take time while modules are loading
    $deadline = (Get-Date).AddSeconds(45)
    $virtualReady = $false
    $normalModeHandled = $false
    while ((Get-Date) -lt $deadline) {
        if (-not $normalModeHandled -and (Invoke-OBSNormalModePrompt)) {
            $normalModeHandled = $true
            $deadline = (Get-Date).AddSeconds(45)
            Write-Output 'OBS recovery prompt: Run in Normal Mode selected.'
        }
        $recentLog = Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'obs-studio\logs') -File |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($recentLog -and $recentLog.LastWriteTime -ge $obs.StartTime) {
            $logText = Get-Content -LiteralPath $recentLog.FullName -Raw
            if ($logText -match '==== Virtual Camera Start') { $virtualReady = $true; break }
        }
        if ($obs.HasExited) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $virtualReady) {
        throw 'OBS did not confirm Virtual Camera startup. Open OBS and click Start Virtual Camera. Keep OBS running while recording in Telegram.'
    }
}
if ($appWasStarted) {
    Write-Output ('Application log: ' + $appLog)
    Write-Output ('Application error log: ' + $appErrorLog)
}
Write-Output 'OBS Virtual Camera is running. Keep OBS open or minimized while recording in Telegram.'
& $pythonExe (Join-Path $PSScriptRoot 'arrange_windows.py')
} finally {
    if ($ownsLauncherMutex) { $launcherMutex.ReleaseMutex() }
    $launcherMutex.Dispose()
}
