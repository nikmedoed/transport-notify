param(
    [string]$Name = 'TransportationOverlay',
    [switch]$OneDir
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSCommandPath
$venvPython = Join-Path $root '.venv\Scripts\python.exe'

function Test-PythonPip {
    param([string]$PythonPath)

    & $PythonPath -m pip --version *> $null
    return $LASTEXITCODE -eq 0
}

if ((Test-Path -LiteralPath $venvPython) -and (Test-PythonPip $venvPython)) {
    $python = $venvPython
} else {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$argsList = @('scripts\build.py', '--install-deps', '--name', $Name)
if ($OneDir) {
    $argsList += '--onedir'
}

Push-Location $root
try {
    & $python @argsList
    if ($LASTEXITCODE -ne 0) {
        throw 'Build failed.'
    }
} finally {
    Pop-Location
}
