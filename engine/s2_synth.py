#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from engine.errors import SynthesisCancelled
from engine.s2_lib import S2Library, write_synth_status


def _progress(idx: int, total: int, _path: Path) -> None:
    print(f"PROGRESS {idx} {total}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolated s2.cpp synthesis job")
    parser.add_argument("--job", type=Path, required=True)
    args = parser.parse_args(argv)

    job = json.loads(args.job.read_text(encoding="utf-8"))
    output_dir = Path(job["output_dir"])
    library_path = Path(job["library_path"])
    lib_dir = library_path.parent
    prev_ld = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev_ld}" if prev_ld else str(lib_dir)

    write_synth_status(output_dir, "init")
    lib = S2Library(library_path)
    voice_name = job.get("voice_name")
    voice_dirs = job.get("voice_dirs") or job.get("voice_dir")
    if isinstance(voice_dirs, str):
        voice_dirs = [voice_dirs]
    try:
        lib.synthesize_batch(
            lines=list(job["lines"]),
            output_dir=output_dir,
            model_path=Path(job["model_path"]),
            tokenizer_path=Path(job["tokenizer_path"]),
            backend_type=int(job["backend_type"]),
            gpu_device=int(job["gpu_device"]),
            n_gpu_layers=int(job["n_gpu_layers"]),
            threads=int(job["threads"]),
            voice_name=voice_name,
            voice_dirs=[Path(path) for path in voice_dirs] if voice_dirs else None,
            progress=_progress,
            skip_existing=True,
            codec_follow_backend=job.get("codec_follow_backend"),
        )
    except SynthesisCancelled:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SYNTH_ERROR {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
