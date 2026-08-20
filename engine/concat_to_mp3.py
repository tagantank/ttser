#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from engine.runtime import ffmpeg_binary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_mp3", type=Path)
    parser.add_argument("--bitrate", default="128k")
    parser.add_argument("--stereo", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    files = sorted(args.input_dir.glob("output_*.wav"))
    if not files:
        raise SystemExit("No WAV files found")

    args.output_mp3.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        list_file = Path(f.name)
        for wav in files:
            f.write(f"file '{wav.resolve()}'\n")

    cmd = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error"]
    cmd += ["-y" if args.overwrite else "-n"]
    cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file)]
    cmd += ["-c:a", "libmp3lame", "-b:a", args.bitrate]
    if args.stereo:
        cmd += ["-ac", "2"]
    cmd += [str(args.output_mp3)]
    subprocess.run(cmd, check=True)
    list_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
