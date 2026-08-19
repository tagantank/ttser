from __future__ import annotations

import re

SENTENCE_RE = re.compile(r"(?<=[.!?;:…])\s+")
LATIN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9&.+#/-]*\b")
DIGIT_RE = re.compile(r"\b\d+\b")


def normalize_text_surface(text: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u202f": " ",
        "\u00ad": "",
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
    result = re.sub(r" *\n *", "\n", result)
    result = re.sub(r" {2,}", " ", result)
    return result.strip()


def split_sentences(paragraph: str) -> list[str]:
    return [p.strip() for p in SENTENCE_RE.split(paragraph) if p.strip()]


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
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def wrap_text(text: str, target_chars: int, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    lines: list[str] = []
    for paragraph in paragraphs:
        current = ""
        for sentence in split_sentences(paragraph) or [paragraph]:
            for part in split_long_piece(sentence, max_chars):
                candidate = f"{current} {part}".strip() if current else part
                if current and len(candidate) > target_chars:
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


def find_leftovers(text: str) -> dict[str, list[str]]:
    latin = sorted(set(LATIN_RE.findall(text)))
    digits = sorted(set(DIGIT_RE.findall(text)))
    return {"latin": latin, "digits": digits}
