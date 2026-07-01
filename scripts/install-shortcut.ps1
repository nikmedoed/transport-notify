param(
    [string]$Name = 'Transportation Overlay',
    [switch]$Desktop
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$launcher = Join-Path $root 'scripts\launch-hidden.vbs'
$icon = Join-Path $root 'assets\transportation-overlay.ico'
$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Launcher was not found: $launcher"
}

$shell = New-Object -ComObject WScript.Shell
$programs = [Environment]::GetFolderPath('Programs')
$shortcutPaths = @(
    Join-Path $programs "$Name.lnk"
)

if ($Desktop) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPaths += Join-Path $desktop "$Name.lnk"
}

foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = "`"$launcher`""
    $shortcut.WorkingDirectory = $root
    if (Test-Path -LiteralPath $icon) {
        $shortcut.IconLocation = $icon
    } else {
        $shortcut.IconLocation = "$wscript,0"
    }
    $shortcut.Description = 'Launch Transportation Overlay from source'
    $shortcut.Save()
    Write-Host "Created shortcut: $shortcutPath"
}

Write-Host ''
Write-Host 'You can pin the Start Menu shortcut to the taskbar.'
