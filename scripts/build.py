import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERSION = "0.1.0"


def data_arg(source: Path, dest: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{dest}"


def run(cmd: list[str]) -> None:
    print(" ".join(str(part) for part in cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def output(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def normalize_version(version: str) -> str:
    return version.strip().lstrip("vV")


def resolve_build_version(explicit_version: str | None = None) -> str:
    if explicit_version:
        return normalize_version(explicit_version)

    github_ref = os.environ.get("GITHUB_REF_NAME")
    if github_ref and github_ref.startswith(("v", "V")):
        return normalize_version(github_ref)

    git_tag = output(["git", "describe", "--tags", "--abbrev=0"])
    if git_tag:
        return normalize_version(git_tag)

    return DEFAULT_VERSION


def build_target(name: str, entry: Path, *, onedir: bool) -> None:
    mode = "--onedir" if onedir else "--onefile"
    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode,
        "--name",
        name,
        "--windowed",
        "--paths",
        str(ROOT / "src"),
        "--collect-all",
        "PySide6",
        "--collect-all",
        "curl_cffi",
        "--add-data",
        data_arg(ROOT / "config.toml", "."),
        str(entry),
    ]
    run(pyinstaller_args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="TransportationOverlay")
    parser.add_argument("--onedir", action="store_true")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--version", help="Version used for release builds.")
    args = parser.parse_args()
    version = resolve_build_version(args.version)

    if args.install_deps:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        run([sys.executable, "-m", "pip", "install", "-e", ".", "-r", "requirements-build.txt"])

    dist_dir = ROOT / "dist"
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
        except PermissionError as exc:
            raise SystemExit(
                "Could not clean dist/. Close any running TransportationOverlay executable, "
                "then run the build again."
            ) from exc

    print(f"Build version: {version}")
    build_target(args.name, ROOT / "main.py", onedir=args.onedir)
    print(f"Build complete: {ROOT / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
