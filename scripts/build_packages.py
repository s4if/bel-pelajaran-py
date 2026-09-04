#!/usr/bin/env python3
"""Build native release artifacts for Bel Pembelajaran.

Run this script with the project's Python environment (normally ``uv run``).
PyInstaller must run on the target OS: Windows builds the EXE; Linux builds the
payload used by both the Debian package and AppImage.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "packaging"
APP_ID = "bel-pelajaran"
DISPLAY_NAME = "Bel Pembelajaran"
RESOURCE_ENV = "BEL_PELAJARAN_RESOURCE_DIR"


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        value = str(tomllib.load(file)["project"]["version"])
    if not re.fullmatch(r"[0-9][0-9A-Za-z.+:~-]*", value):
        raise SystemExit(f"Versi paket tidak valid: {value!r}")
    return value


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def pyinstaller_payload(*, target: str) -> Path:
    """Build an onedir payload and return its directory."""
    work = BUILD / f"pyinstaller-{target}"
    clean_directory(work)
    (work / "spec").mkdir()
    dist = work / "dist"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        APP_ID,
        "--distpath",
        str(dist),
        "--workpath",
        str(work / "work"),
        "--specpath",
        str(work / "spec"),
        "--hidden-import",
        "PySide6.QtMultimedia",
        "--collect-submodules",
        "PySide6",
    ]

    if target == "windows":
        separator = ";"
        cmd.extend(
            [
                "--add-data",
                f"{ROOT / 'assets'}{separator}assets",
                "--add-data",
                f"{ROOT / 'configs'}{separator}configs",
                "--add-data",
                f"{ROOT / 'LICENSE'}{separator}.",
            ]
        )
        icon = ROOT / "assets" / "app_icon.ico"
        if icon.is_file():
            cmd.extend(["--icon", str(icon)])

    cmd.append(str(ROOT / "run_gui.py"))
    run(cmd)
    payload = dist / APP_ID
    if not payload.is_dir():
        raise SystemExit(f"PyInstaller tidak membuat payload yang diharapkan: {payload}")
    return payload


def build_windows() -> Path:
    if os.name != "nt":
        raise SystemExit("Target windows harus dibangun di Windows native (bukan WSL).")
    payload = pyinstaller_payload(target="windows")
    output = DIST / "windows" / APP_ID
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(payload, output, symlinks=True)
    executable = output / f"{APP_ID}.exe"
    if not executable.is_file():
        raise SystemExit(f"EXE tidak ditemukan setelah build: {executable}")
    print(f"Windows EXE: {executable}")
    return executable


def linux_architecture(*, debian: bool) -> str:
    machine = platform.machine().lower()
    mappings = {
        "x86_64": ("amd64", "x86_64"),
        "amd64": ("amd64", "x86_64"),
        "aarch64": ("arm64", "aarch64"),
        "arm64": ("arm64", "aarch64"),
    }
    try:
        return mappings[machine][0 if debian else 1]
    except KeyError as exc:
        raise SystemExit(f"Arsitektur Linux belum didukung: {machine}") from exc


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_linux_tree(root: Path, payload: Path, *, appimage: bool) -> None:
    """Install payload/resources into a Debian root or AppDir."""
    lib_dir = root / "usr" / "lib" / APP_ID
    share_dir = root / "usr" / "share" / APP_ID
    shutil.copytree(payload, lib_dir, symlinks=True)
    shutil.copytree(ROOT / "assets", share_dir / "assets")
    shutil.copytree(ROOT / "configs", share_dir / "configs")
    documentation = root / "usr" / "share" / "doc" / APP_ID
    documentation.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", documentation / "copyright")

    desktop_source = ROOT / "packaging" / "linux" / f"{APP_ID}.desktop"
    applications = root / "usr" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    shutil.copy2(desktop_source, applications / desktop_source.name)

    icon_dir = root / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets" / "app_icon.svg", icon_dir / f"{APP_ID}.svg")

    if appimage:
        launcher = """#!/bin/sh
set -eu
APPDIR=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
export BEL_PELAJARAN_RESOURCE_DIR="$APPDIR/usr/share/bel-pelajaran"
exec "$APPDIR/usr/lib/bel-pelajaran/bel-pelajaran" "$@"
"""
    else:
        launcher = """#!/bin/sh
set -eu
export BEL_PELAJARAN_RESOURCE_DIR=/usr/share/bel-pelajaran
exec /usr/lib/bel-pelajaran/bel-pelajaran "$@"
"""
    write_executable(root / "usr" / "bin" / APP_ID, launcher)


def require_command(name: str, install_hint: str) -> str:
    command = shutil.which(name)
    if command is None:
        raise SystemExit(f"Perintah {name!r} tidak tersedia. {install_hint}")
    return command


def build_deb(payload: Path, version: str) -> Path:
    dpkg_deb = require_command(
        "dpkg-deb",
        "Pasang prerequisite Debian: sudo apt install dpkg-dev",
    )
    architecture = linux_architecture(debian=True)
    stage = BUILD / "deb-root"
    clean_directory(stage)
    install_linux_tree(stage, payload, appimage=False)

    installed_bytes = sum(path.stat().st_size for path in stage.rglob("*") if path.is_file())
    control_dir = stage / "DEBIAN"
    control_dir.mkdir()
    (control_dir / "control").write_text(
        f"""Package: {APP_ID}
Version: {version}
Section: utils
Priority: optional
Architecture: {architecture}
Maintainer: s4if
Installed-Size: {(installed_bytes + 1023) // 1024}
Depends: libc6 (>= 2.31), libdbus-1-3, libfontconfig1, libgl1, libglib2.0-0, libxkbcommon0
Description: Bel sekolah otomatis dengan editor jadwal desktop
 Aplikasi Qt untuk mengelola jadwal dan memutar bel sekolah secara otomatis.
""",
        encoding="utf-8",
        newline="\n",
    )

    output_dir = DIST / "linux"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{APP_ID}_{version}_{architecture}.deb"
    output.unlink(missing_ok=True)
    run([dpkg_deb, "--root-owner-group", "--build", str(stage), str(output)])
    print(f"Debian package: {output}")
    return output


def find_appimagetool(explicit: str | None) -> str:
    candidate = explicit or os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if not candidate or not Path(candidate).is_file():
        raise SystemExit(
            "appimagetool tidak tersedia. Unduh AppImageKit appimagetool, "
            "chmod +x, lalu gunakan --appimagetool /path/appimagetool."
        )
    return str(Path(candidate).resolve())


def build_appimage(payload: Path, version: str, appimagetool: str | None) -> Path:
    tool = find_appimagetool(appimagetool)
    architecture = linux_architecture(debian=False)
    appdir = BUILD / f"{DISPLAY_NAME.replace(' ', '')}.AppDir"
    clean_directory(appdir)
    install_linux_tree(appdir, payload, appimage=True)

    write_executable(
        appdir / "AppRun",
        """#!/bin/sh
set -eu
APPDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$APPDIR/usr/bin/bel-pelajaran" "$@"
""",
    )
    shutil.copy2(
        ROOT / "packaging" / "linux" / f"{APP_ID}.desktop",
        appdir / f"{APP_ID}.desktop",
    )
    icon_target = Path("usr/share/icons/hicolor/scalable/apps") / f"{APP_ID}.svg"
    (appdir / f"{APP_ID}.svg").symlink_to(icon_target)
    (appdir / ".DirIcon").symlink_to(f"{APP_ID}.svg")

    output_dir = DIST / "linux"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"Bel-Pembelajaran-{version}-{architecture}.AppImage"
    output.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["ARCH"] = architecture
    # Allows the appimagetool AppImage to run on build hosts without FUSE.
    environment.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")
    run([tool, str(appdir), str(output)], env=environment)
    output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"AppImage: {output}")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        choices=("windows", "deb", "appimage", "linux"),
        help="linux membangun .deb dan AppImage dari satu payload",
    )
    parser.add_argument(
        "--appimagetool",
        help="path appimagetool (atau set environment APPIMAGETOOL)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.target == "windows":
        build_windows()
        return 0
    if not sys.platform.startswith("linux"):
        raise SystemExit("Target deb/appimage harus dibangun di Linux.")

    # Fail before the comparatively expensive PyInstaller build when a native
    # packaging prerequisite is missing.
    resolved_appimagetool = None
    if args.target in ("deb", "linux"):
        require_command(
            "dpkg-deb",
            "Pasang prerequisite Debian: sudo apt install dpkg-dev",
        )
    if args.target in ("appimage", "linux"):
        resolved_appimagetool = find_appimagetool(args.appimagetool)

    version = project_version()
    payload = pyinstaller_payload(target="linux")
    if args.target in ("deb", "linux"):
        build_deb(payload, version)
    if args.target in ("appimage", "linux"):
        build_appimage(payload, version, resolved_appimagetool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
