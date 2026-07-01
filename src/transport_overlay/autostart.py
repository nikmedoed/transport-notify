from __future__ import annotations

import json
import os
import sys
import winreg
from dataclasses import dataclass
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_RUN_NAME = "TransportationOverlay"
SETTINGS_FILE = "settings.json"
SOURCE_LAUNCHER_FILE = "start-source.ps1"
AUTOSTART_LOG_FILE = "autostart.log"
AUTOSTART_OUTPUT_LOG_FILE = "autostart-output.log"
AUTOSTART_ERROR_LOG_FILE = "autostart-error.log"


@dataclass(frozen=True)
class UserSettings:
    autostart_enabled: bool
    first_run_done: bool


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "TransportationOverlay"
    return Path.home() / "AppData" / "Roaming" / "TransportationOverlay"


def settings_path() -> Path:
    return user_data_dir() / SETTINGS_FILE


def load_user_settings() -> UserSettings:
    path = settings_path()
    if not path.exists():
        return UserSettings(autostart_enabled=True, first_run_done=False)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings(autostart_enabled=True, first_run_done=False)

    return UserSettings(
        autostart_enabled=bool(raw.get("autostart_enabled", True)),
        first_run_done=bool(raw.get("first_run_done", False)),
    )


def save_user_settings(settings: UserSettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "autostart_enabled": settings.autostart_enabled,
                "first_run_done": settings.first_run_done,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def configure_autostart_on_startup() -> UserSettings:
    settings = load_user_settings()
    if not settings.first_run_done:
        settings = UserSettings(autostart_enabled=True, first_run_done=True)
        save_user_settings(settings)

    set_autostart(settings.autostart_enabled)
    return settings


def set_autostart_enabled(enabled: bool) -> UserSettings:
    settings = UserSettings(autostart_enabled=enabled, first_run_done=True)
    set_autostart(enabled)
    save_user_settings(settings)
    return settings


def is_autostart_enabled() -> bool:
    expected = startup_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _value_type = winreg.QueryValueEx(key, APP_RUN_NAME)
    except FileNotFoundError:
        return False
    return value == expected


def set_autostart(enabled: bool) -> None:
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        access=winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_RUN_NAME)
            except FileNotFoundError:
                pass


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return quote_arg(Path(sys.executable).resolve())

    hidden_launcher = source_root() / "scripts" / "launch-hidden.vbs"
    if hidden_launcher.exists():
        wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
        return f"{quote_arg(wscript)} {quote_arg(hidden_launcher)}"

    launcher = write_source_launcher()
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return (
        f"{quote_arg(powershell)} -NoProfile -ExecutionPolicy Bypass "
        f"-WindowStyle Hidden -File {quote_arg(launcher)}"
    )


def write_source_launcher() -> Path:
    launcher = user_data_dir() / SOURCE_LAUNCHER_FILE
    log_path = user_data_dir() / AUTOSTART_LOG_FILE
    output_log_path = user_data_dir() / AUTOSTART_OUTPUT_LOG_FILE
    error_log_path = user_data_dir() / AUTOSTART_ERROR_LOG_FILE
    python = source_console_python()
    root = source_root()
    source_launcher = root / "scripts" / "launch.ps1"
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"

    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$root = {powershell_string(root)}",
                f"$python = {powershell_string(python)}",
                f"$main = {powershell_string(root / 'main.py')}",
                f"$sourceLauncher = {powershell_string(source_launcher)}",
                f"$powershell = {powershell_string(powershell)}",
                f"$log = {powershell_string(log_path)}",
                f"$outputLog = {powershell_string(output_log_path)}",
                f"$errorLog = {powershell_string(error_log_path)}",
                f"$env:PYTHONPATH = {powershell_string(root / 'src')}",
                '"[{0}] Starting TransportationOverlay from source" -f (Get-Date) | Set-Content -Encoding UTF8 $log',
                '"Root: {0}" -f $root | Add-Content -Encoding UTF8 $log',
                '"Python: {0}" -f $python | Add-Content -Encoding UTF8 $log',
                "if (Test-Path -LiteralPath $sourceLauncher) {",
                '    Start-Process -FilePath $powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $sourceLauncher) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $outputLog -RedirectStandardError $errorLog',
                "} else {",
                "    Start-Process -FilePath $python -ArgumentList @($main) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $outputLog -RedirectStandardError $errorLog",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return launcher


def source_python() -> Path:
    venv_pythonw = source_root() / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.exists():
        return venv_pythonw

    executable = Path(sys.executable).resolve()
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        return pythonw
    return executable


def source_console_python() -> Path:
    venv_python = source_root() / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python

    executable = Path(sys.executable).resolve()
    python = executable.with_name("python.exe")
    if python.exists():
        return python
    return executable


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def quote_arg(value: Path) -> str:
    return f'"{value}"'


def powershell_string(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"
