param(
    [switch]$Console
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$main = Join-Path $root 'main.py'
$venvConfig = Join-Path $root '.venv\pyvenv.cfg'
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$venvSitePackages = Join-Path $root '.venv\Lib\site-packages'
$logDir = Join-Path $env:APPDATA 'TransportationOverlay\logs'

$pythonPathParts = @(Join-Path $root 'src')
if (Test-Path -LiteralPath $venvSitePackages) {
    $pythonPathParts += $venvSitePackages
}

$env:PYTHONPATH = $pythonPathParts -join [IO.Path]::PathSeparator
$env:TRANSPORT_OVERLAY_LOGS = '1'

function Stop-ExistingSourceInstances {
    $rootPattern = '*' + [WildcardPattern]::Escape($root) + '*'
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.ProcessId -ne $PID -and
            $_.Name -like 'python*' -and
            $_.CommandLine -and
            $_.CommandLine -like $rootPattern -and
            $_.CommandLine -like '*main.py*'
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

if (Test-Path -LiteralPath $venvConfig) {
    $venvHome = Get-Content -LiteralPath $venvConfig |
        Where-Object { $_ -match '^home\s*=' } |
        Select-Object -First 1
    if ($venvHome) {
        $venvHomePython = Join-Path (($venvHome -split '=', 2)[1].Trim()) 'python.exe'
    }
}

if ($venvHomePython -and (Test-Path -LiteralPath $venvHomePython)) {
    $python = $venvHomePython
} elseif (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
} else {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Stop-ExistingSourceInstances

if ($Console) {
    Push-Location $root
    try {
        & $python $main
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Push-Location $root
try {
    & $python $main
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
