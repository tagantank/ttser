from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

COMBINING_ACUTE = "\u0301"
PAUSE_ONLY_RE = re.compile(r"^\[pause(?:\s+\S+)?\]$", re.IGNORECASE)
WORD_BOUNDARY = r"(?<![0-9A-Za-zА-Яа-яЁё]){}(?![0-9A-Za-zА-Яа-яЁё])"


@dataclass
class Rule:
    source: str
    replacement: str
    note: str = ""


def load_rules(path: Path) -> list[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for item in data:
        rules.append(Rule(str(item["from"]), str(item["to"]).replace(COMBINING_ACUTE, ""), str(item.get("note", ""))))
    rules.sort(key=lambda r: len(r.source), reverse=True)
    return rules


def save_rules(path: Path, rules: list[Rule]) -> None:
    data = [{"from": r.source, "to": r.replacement.replace(COMBINING_ACUTE, ""), "note": r.note} for r in rules]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_rules(rules: list[Rule]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for idx, rule in enumerate(rules, start=1):
        if not rule.source.strip() or not rule.replacement.strip():
            errors.append(f"Rule #{idx}: 'from' and 'to' must be non-empty")
        key = rule.source.strip().lower()
        if key in seen:
            errors.append(f"Duplicate 'from': {rule.source}")
        seen.add(key)
    return errors


def _preserve_case(matched: str, replacement: str) -> str:
    return replacement[:1].upper() + replacement[1:] if matched[:1].isupper() else replacement


def apply_rules(text: str, rules: list[Rule]) -> tuple[str, dict[str, int]]:
    stats: dict[str, int] = {}
    out_lines: list[str] = []
    for line in text.splitlines():
        if PAUSE_ONLY_RE.match(line.strip()):
            out_lines.append(line.strip())
            continue
        result = line
        for rule in rules:
            pattern = re.compile(WORD_BOUNDARY.format(re.escape(rule.source)), flags=re.IGNORECASE)

            def replace(match: re.Match[str]) -> str:
                stats[rule.source] = stats.get(rule.source, 0) + 1
                return _preserve_case(match.group(0), rule.replacement)

            result = pattern.sub(replace, result)
        out_lines.append(result.replace(COMBINING_ACUTE, ""))
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), stats

