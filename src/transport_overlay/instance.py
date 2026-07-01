from __future__ import annotations

import atexit
import ctypes
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from transport_overlay.autostart import user_data_dir


LOCK_FILE = "instance.lock"
WAIT_SECONDS = 10

SYNCHRONIZE = 0x00100000
PROCESS_TERMINATE = 0x0001
WAIT_OBJECT_0 = 0x00000000

kernel32 = ctypes.windll.kernel32


@dataclass
class SingleInstance:
    path: Path
    pid: int

    @classmethod
    def acquire_or_restart_existing(cls) -> SingleInstance | None:
        path = user_data_dir() / LOCK_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            instance = cls._try_create(path)
            if instance is not None:
                atexit.register(instance.release)
                return instance

            existing_pid = _read_existing_pid(path)
            if existing_pid == os.getpid():
                _remove_lock(path)
                continue

            if existing_pid is None or not _is_transportation_process(existing_pid):
                _remove_lock(path)
                continue

            _terminate_process(existing_pid)
            _wait_for_process_exit(existing_pid, deadline)
            _remove_lock(path)

        return None

    @classmethod
    def _try_create(cls, path: Path) -> SingleInstance | None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(path, flags)
        except FileExistsError:
            return None

        pid = os.getpid()
        payload = {
            "pid": pid,
            "argv": sys.argv,
            "executable": sys.executable,
            "created_at": time.time(),
        }
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        return cls(path=path, pid=pid)

    def release(self) -> None:
        existing_pid = _read_existing_pid(self.path)
        if existing_pid == self.pid:
            _remove_lock(self.path)


def _read_existing_pid(path: Path) -> int | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return int(raw["pid"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _remove_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _is_transportation_process(pid: int) -> bool:
    command_line = _process_command_line(pid)
    if not command_line:
        return False

    root = str(Path(__file__).resolve().parents[2]).lower()
    command_line = command_line.lower()
    return root in command_line and "main.py" in command_line


def _terminate_orphaned_instances(deadline: float) -> None:
    for pid in _transportation_pids():
        if pid == os.getpid():
            continue
        _terminate_process(pid)
        _wait_for_process_exit(pid, deadline)


def _transportation_pids() -> list[int]:
    root = str(Path(__file__).resolve().parents[2]).replace("'", "''")
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.Name -like 'python*' -and $_.CommandLine -and $_.CommandLine.Contains('{root}') -and $_.CommandLine.Contains('main.py') }} | "
            "ForEach-Object { $_.ProcessId }"
        ),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def _process_command_line(pid: int) -> str | None:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    command_line = result.stdout.strip()
    return command_line or None


def _terminate_process(pid: int) -> None:
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return

    try:
        kernel32.TerminateProcess(handle, 0)
    finally:
        kernel32.CloseHandle(handle)


def _wait_for_process_exit(pid: int, deadline: float) -> None:
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return

    try:
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        result = kernel32.WaitForSingleObject(handle, remaining_ms)
        if result != WAIT_OBJECT_0:
            time.sleep(0.2)
    finally:
        kernel32.CloseHandle(handle)
