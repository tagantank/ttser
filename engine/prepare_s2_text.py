#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engine.s2_text import find_leftovers, normalize_text_surface, wrap_text

BREAK_RE = re.compile(r"<break\s+time=\"([^\"]+)\"\s*/>", re.IGNORECASE)


def parse_break_duration(raw: str) -> str:
    value = raw.strip().lower()
    if value.endswith("ms"):
        seconds = float(value[:-2]) / 1000.0
    elif value.endswith("s"):
        seconds = float(value[:-1])
    else:
        seconds = float(value)
    seconds = max(0.1, seconds)
    rendered = f"{seconds:.1f}".rstrip("0").rstrip(".")
    return f"{rendered}s"


def prepare_chunks(text: str, target_chars: int, max_chars: int) -> list[str]:
    chunks: list[str] = []
    last = 0
    for match in BREAK_RE.finditer(text):
        block = normalize_text_surface(text[last : match.start()])
        if block:
            chunks.extend(wrap_text(block, target_chars, max_chars))
        chunks.append(f"[pause {parse_break_duration(match.group(1))}]")
        last = match.end()
    tail = normalize_text_surface(text[last:])
    if tail:
        chunks.extend(wrap_text(tail, target_chars, max_chars))
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--target-chars", type=int, default=180)
    parser.add_argument("--max-chars", type=int, default=260)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Output exists: {args.output}")
    source = args.input.read_text(encoding="utf-8")
    chunks = prepare_chunks(source, args.target_chars, args.max_chars)
    rendered = "\n".join(chunks) + ("\n" if chunks else "")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    if args.report:
        report = {
            "chunks": len(chunks),
            "pause_chunks": sum(1 for c in chunks if c.startswith("[pause")),
            "max_line_length": max((len(c) for c in chunks), default=0),
            "leftovers": find_leftovers(rendered),
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
