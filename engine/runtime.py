"""Runtime layout for a git checkout vs a frozen macOS .app."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_flatpak() -> bool:
    return os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"


def resource_root() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    if is_flatpak():
        return Path.home() / ".var" / "app" / "com.tagantank.ttser" / "data"
    if is_frozen() and sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ttser"
    if is_frozen():
        return Path.home() / ".local" / "share" / "ttser"
    return resource_root()


def prepend_library_path(env: dict[str, str], lib_dir: Path) -> dict[str, str]:
    lib = str(lib_dir)
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        prev = env.get(key, "")
        env[key] = f"{lib}:{prev}" if prev else lib
    return env


def synth_child_command(job_path: Path) -> list[str]:
    if is_frozen():
        helper = Path(sys.executable).resolve().parent / "ttser-synth"
        if helper.is_file():
            return [str(helper), "--job", str(job_path)]
        return [sys.executable, "--synth-job", str(job_path)]
    return [sys.executable, "-m", "engine.s2_synth", "--job", str(job_path)]


def ffmpeg_binary() -> str:
    bundled = resource_root() / "bin" / "ffmpeg"
    if bundled.is_file():
        return str(bundled)
    return "ffmpeg"


def default_output_mp3() -> str:
    if is_frozen():
        return str(Path.home() / "Documents" / "ttser" / "result.mp3")
    return "output/result.mp3"


def run_entry(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    extra = args[1:]
    if extra[:1] == ["--synth-job"]:
        from engine.s2_synth import main as synth_main

        job = extra[1] if len(extra) > 1 else ""
        return int(synth_main(["--job", job]))
    from ttser.app import main as gui_main

    return int(gui_main())
