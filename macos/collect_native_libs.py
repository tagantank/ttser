#!/usr/bin/env python3
"""Copy s2/ggml dylibs and ffmpeg into a relocatable payload with @loader_path."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SYSTEM_PREFIXES = (
    "/usr/lib",
    "/System/",
    "/Library/Apple/",
    "/usr/lib/system",
)


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def otool_deps(path: Path) -> list[str]:
    proc = _run(["otool", "-L", str(path)])
    deps: list[str] = []
    for line in proc.stdout.splitlines()[1:]:
        deps.append(line.strip().split(" (compatibility", 1)[0].strip())
    return deps


def otool_rpaths(path: Path) -> list[str]:
    proc = _run(["otool", "-l", str(path)])
    rpaths: list[str] = []
    lines = proc.stdout.splitlines()
    for i, line in enumerate(lines):
        if "LC_RPATH" not in line:
            continue
        for follow in lines[i + 1 : i + 6]:
            stripped = follow.strip()
            if stripped.startswith("path "):
                rpaths.append(stripped[5:].split(" (", 1)[0].strip())
                break
    return rpaths


def is_system_lib(dep: str) -> bool:
    if dep.startswith("@loader_path/") or dep.startswith("@executable_path/"):
        return True
    return any(dep.startswith(prefix) for prefix in SYSTEM_PREFIXES)


def resolve_dep(dep: str, binary: Path) -> Path | None:
    if dep.startswith("@rpath/"):
        name = dep.split("/", 1)[1]
        for rpath in otool_rpaths(binary):
            candidate = (Path(rpath) / name).resolve()
            if candidate.is_file():
                return candidate
        sibling = (binary.parent / name).resolve()
        return sibling if sibling.is_file() else None
    path = Path(dep)
    return path if path.is_file() else None


def add_rpath(path: Path, rpath: str) -> None:
    existing = otool_rpaths(path)
    if rpath in existing:
        return
    _run(["install_name_tool", "-add_rpath", rpath, str(path)], check=False)


def delete_absolute_rpaths(path: Path) -> None:
    for rpath in otool_rpaths(path):
        if rpath.startswith("/") and not rpath.startswith("/usr/lib"):
            _run(["install_name_tool", "-delete_rpath", rpath, str(path)], check=False)


def collect_s2_build(build_dir: Path, dest: Path, dest_name: str) -> None:
    src = build_dir / "libs2.dylib"
    if not src.is_file():
        raise FileNotFoundError(f"missing {src}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest / dest_name)
    for dylib in build_dir.rglob("libggml*.dylib"):
        shutil.copy2(dylib, dest / dylib.name)
    for extra in build_dir.rglob("*"):
        if extra.suffix in {".metallib", ".metal"} and extra.is_file():
            shutil.copy2(extra, dest / extra.name)
    for item in dest.glob("*.dylib"):
        add_rpath(item, "@loader_path")
        delete_absolute_rpaths(item)


def bundle_binary(src: Path, dest_dir: Path, seen: set[str] | None = None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    dest.chmod(dest.stat().st_mode | 0o111)
    _run(["install_name_tool", "-id", f"@loader_path/{dest.name}", str(dest)], check=False)
    seen = seen if seen is not None else set()
    seen.add(dest.name)
    for dep in otool_deps(dest):
        if is_system_lib(dep) or dep.endswith(f"/{dest.name}") or dep == dest.name:
            continue
        real = resolve_dep(dep, src if src.is_file() else dest)
        if real is None or not real.is_file():
            continue
        if real.name not in seen:
            bundle_binary(real, dest_dir, seen)
        _run(
            ["install_name_tool", "-change", dep, f"@loader_path/{real.name}", str(dest)],
            check=False,
        )
    add_rpath(dest, "@loader_path")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=None)
    args = parser.parse_args()
    repo = args.repo.resolve()
    payload = args.payload.resolve()
    payload.mkdir(parents=True, exist_ok=True)

    collect_s2_build(repo / "s2.cpp" / "build-cpu", payload / "lib" / "cpu", "libs2_cpu.dylib")
    collect_s2_build(
        repo / "s2.cpp" / "build-metal", payload / "lib" / "metal", "libs2_metal.dylib"
    )

    ffmpeg = args.ffmpeg or Path(shutil.which("ffmpeg") or "")
    if not ffmpeg.is_file():
        raise SystemExit("ffmpeg not found; install it with Homebrew before bundling")
    bundle_binary(ffmpeg, payload / "bin")
    return 0


if __name__ == "__main__":
    if sys.platform != "darwin":
        raise SystemExit("collect_native_libs.py is macOS only")
    raise SystemExit(main())
