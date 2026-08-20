#!/usr/bin/env python3
"""Wrap UTF-8 text into ttser chunks for Fish Audio S2 Pro only.

Preserves existing ttser [pause …] lines. Collapses speech between pauses, then
packs at most two complete sentences toward --target-chars (default 180),
never over --max-chars (default 260). Not for VoxCPM or other TTS engines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Do not split on ':' — that leaves a lowercase continuation on the next line.
SENTENCE_RE = re.compile(r"(?<=[.!?;…])\s+")
PAUSE_RE = re.compile(r"\[pause\s+[^\]]+\]", re.IGNORECASE)
LATIN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9&.+#/-]*\b")
END_RE = re.compile(r"[.!?…;:]$")
SOFT_HYPHEN = "\u00ad"


def is_pause(line: str) -> bool:
    return bool(PAUSE_RE.fullmatch(line.strip()))


def normalize_surface(text: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u202f": " ",
        SOFT_HYPHEN: "",
        "“": "«",
        "”": "»",
        "„": "«",
        "—": " — ",
        "–": " — ",
        "&": " и ",
        "№": "номер ",
    }
    result = text
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r" {2,}", " ", result)
    return result.strip()


def collapse_speech(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_surface(text)).strip()


def split_sentences(paragraph: str) -> list[str]:
    pieces = [p.strip() for p in SENTENCE_RE.split(paragraph) if p.strip()]
    return pieces or ([paragraph.strip()] if paragraph.strip() else [])


def split_long_piece(piece: str, max_chars: int) -> list[str]:
    if len(piece) <= max_chars:
        return [piece]
    chunks: list[str] = []
    rest = piece.strip()
    while len(rest) > max_chars:
        window = rest[: max_chars + 1]
        cut = max(window.rfind(", "), window.rfind(" — "), window.rfind(" "))
        if cut < max(40, max_chars // 3):
            cut = max_chars
        head = rest[:cut].strip()
        rest = rest[cut:].strip()
        if head and not END_RE.search(head):
            head = head.rstrip(" ,;—-") + "…"
        chunks.append(head)
    if rest:
        chunks.append(rest)
    return chunks


def sentence_end_count(text: str) -> int:
    return len(re.findall(r"[.!?…]", text))


def wrap_text(text: str, target_chars: int, max_chars: int) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        for part in split_long_piece(sentence, max_chars):
            candidate = f"{current} {part}".strip() if current else part
            # S2 often EOS-stops after a few short period-separated sentences
            # and swallows the last one. Cap packing at two sentences.
            packed_full = current and (
                len(candidate) > target_chars or sentence_end_count(current) >= 2
            )
            if packed_full:
                lines.append(current)
                current = part
            else:
                current = candidate
            if len(current) > max_chars:
                split = split_long_piece(current, max_chars)
                lines.extend(split[:-1])
                current = split[-1]
    if current:
        lines.append(current)
    return [line for line in lines if line]


def ensure_punct(line: str) -> str:
    if is_pause(line) or END_RE.search(line):
        return line
    return line.rstrip(" ,;—-") + "…"


def join_continuations(lines: list[str], max_chars: int) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if (
            merged
            and not is_pause(line)
            and not is_pause(merged[-1])
            and line[:1].islower()
            and len(merged[-1]) + 1 + len(line) <= max_chars
        ):
            merged[-1] = f"{merged[-1]} {line}"
            continue
        if (
            merged
            and not is_pause(line)
            and merged[-1].endswith(":")
            and len(merged[-1]) + 1 + len(line) <= max_chars
        ):
            merged[-1] = f"{merged[-1]} {line}"
            continue
        merged.append(line)
    return merged


def merge_short_tails(lines: list[str], max_chars: int, min_keep: int = 40) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if (
            merged
            and not is_pause(line)
            and not is_pause(merged[-1])
            and len(line) < min_keep
            and len(merged[-1]) + 1 + len(line) <= max_chars
        ):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def prepare_chunks(text: str, target_chars: int, max_chars: int) -> list[str]:
    chunks: list[str] = []
    last = 0
    for match in PAUSE_RE.finditer(text):
        block = collapse_speech(text[last : match.start()])
        if block:
            chunks.extend(wrap_text(block, target_chars, max_chars))
        chunks.append(match.group(0).strip())
        last = match.end()
    tail = collapse_speech(text[last:])
    if tail:
        chunks.extend(wrap_text(tail, target_chars, max_chars))
    chunks = [ensure_punct(line) for line in chunks]
    chunks = join_continuations(chunks, max_chars)
    chunks = merge_short_tails(chunks, max_chars)
    return chunks


def speech_lines(chunks: list[str]) -> list[str]:
    return [line for line in chunks if not is_pause(line)]


def report_for(chunks: list[str], max_chars: int) -> dict[str, object]:
    speech = speech_lines(chunks)
    lengths = [len(line) for line in speech]
    leftovers_latin = sorted(set(LATIN_RE.findall("\n".join(chunks))))
    leftovers_latin = [token for token in leftovers_latin if token.lower() != "pause"]
    return {
        "chunks": len(chunks),
        "speech_chunks": len(speech),
        "pause_chunks": len(chunks) - len(speech),
        "min_line_length": min(lengths, default=0),
        "median_line_length": sorted(lengths)[len(lengths) // 2] if lengths else 0,
        "max_line_length": max(lengths, default=0),
        "short_under_25": sum(1 for n in lengths if n < 25),
        "short_under_80": sum(1 for n in lengths if n < 80),
        "over_max": sum(1 for n in lengths if n > max_chars),
        "missing_end_punct": sum(1 for line in speech if not END_RE.search(line)),
        "period_stacks_over_2": sum(1 for line in speech if sentence_end_count(line) > 2),
        "lowercase_starts": [line for line in speech if line[:1].islower()],
        "leftovers_latin": leftovers_latin,
    }


def print_report(report: dict[str, object], dest: Path | None = None) -> None:
    print(f"chunks: {report['chunks']}", file=sys.stderr)
    print(
        f"speech: {report['speech_chunks']} pauses: {report['pause_chunks']}",
        file=sys.stderr,
    )
    print(
        "min/median/max: "
        f"{report['min_line_length']}/{report['median_line_length']}/{report['max_line_length']}",
        file=sys.stderr,
    )
    print(
        f"short<25: {report['short_under_25']} short<80: {report['short_under_80']} "
        f">max: {report['over_max']} no-end: {report['missing_end_punct']} "
        f"period-stacks>2: {report['period_stacks_over_2']}",
        file=sys.stderr,
    )
    if report["lowercase_starts"]:
        print(f"lowercase starts: {len(report['lowercase_starts'])}", file=sys.stderr)
    if report["leftovers_latin"]:
        print(f"latin leftovers: {report['leftovers_latin']}", file=sys.stderr)
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare line-oriented UTF-8 text for ttser / Fish Audio S2 Pro only."
    )
    parser.add_argument("--input", "-i", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--target-chars", type=int, default=180)
    parser.add_argument("--max-chars", type=int, default=260)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.target_chars <= 0 or args.max_chars <= 0:
        raise SystemExit("target-chars and max-chars must be positive")
    if args.target_chars > args.max_chars:
        raise SystemExit("target-chars must be <= max-chars")
    source = args.input.read_text(encoding="utf-8")
    if args.check_only:
        chunks = [line.strip() for line in source.splitlines() if line.strip()]
    else:
        chunks = prepare_chunks(source, args.target_chars, args.max_chars)
    report = report_for(chunks, args.max_chars)
    print_report(report, args.report)
    if args.check_only:
        bad = (
            int(report["over_max"])
            or int(report["missing_end_punct"])
            or bool(report["lowercase_starts"])
            or int(report["period_stacks_over_2"])
        )
        return 1 if bad else 0
    if args.output is None:
        raise SystemExit("--output is required unless --check-only")
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Output exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(chunks) + ("\n" if chunks else ""), encoding="utf-8")
    print(f"written: {args.output}", file=sys.stderr)
    return 1 if int(report["over_max"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
