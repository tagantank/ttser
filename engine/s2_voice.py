from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"S2VOICE\x00"
VERSION = 1
DEFAULT_VOICE_ID = ""
DEFAULT_VOICE_LABEL = "Model default voice"
BUNDLED_VOICE_ORDER = ("tankindycast",)
PROTECTED_VOICE_IDS = frozenset({"tankindycast"})
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
S2_SAMPLE_RATE = 44100
S2_CODEBOOK_SIZE = 4096


@dataclass(frozen=True)
class VoiceProfile:
    transcript: str
    codes: list[int]
    num_codebooks: int
    t_prompt: int
    sample_rate: int
    codebook_size: int
    path: Path


def bundled_voice_dir() -> Path:
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        return Path("/app/share/ttser/voices")
    return Path("voices")


def user_voice_dir() -> Path:
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        return Path.home() / ".var" / "app" / "com.tagantank.ttser" / "data" / "voices"
    return Path("voices")


def voice_search_dirs(configured_voice_dir: str | Path | None = None) -> list[Path]:
    bundled = bundled_voice_dir()
    user = user_voice_dir()
    dirs: list[Path] = []
    for candidate in (user, bundled):
        if candidate not in dirs:
            dirs.append(candidate)
    if configured_voice_dir:
        configured = Path(configured_voice_dir)
        if configured not in dirs:
            dirs.append(configured)
    return dirs


def list_voice_ids(*voice_dirs: str | Path | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for voice_id in BUNDLED_VOICE_ORDER:
        if voice_id not in seen and _voice_exists_in_dirs(voice_id, voice_dirs):
            seen.add(voice_id)
            ordered.append(voice_id)
    extras = sorted(
        voice_id
        for voice_id in _scan_voice_ids(voice_dirs)
        if voice_id not in seen
    )
    ordered.extend(extras)
    return ordered


def _scan_voice_ids(voice_dirs: tuple[str | Path | None, ...]) -> set[str]:
    found: set[str] = set()
    for voice_dir in voice_dirs:
        if not voice_dir:
            continue
        path = Path(voice_dir)
        if not path.is_dir():
            continue
        for item in path.glob("*.s2voice"):
            if item.is_file():
                found.add(item.stem)
    return found


def _voice_exists_in_dirs(voice_id: str, voice_dirs: tuple[str | Path | None, ...]) -> bool:
    try:
        resolve_voice_path(voice_id, *voice_dirs)
    except FileNotFoundError:
        return False
    return True


def preferred_voice_id(
    *voice_dirs: str | Path | None,
    requested: str | None = None,
) -> str:
    available = set(_scan_voice_ids(voice_dirs))
    if requested in (None, DEFAULT_VOICE_ID):
        return DEFAULT_VOICE_ID
    if requested in available:
        return requested
    for voice_id in BUNDLED_VOICE_ORDER:
        if voice_id in available:
            return voice_id
    return DEFAULT_VOICE_ID


def validate_voice_id(voice_id: str) -> str:
    name = voice_id.strip()
    if not name:
        raise ValueError("voice name is required")
    if not VOICE_ID_RE.fullmatch(name):
        raise ValueError("voice name may only contain Latin letters, digits, _ and -")
    return name


def resolve_voice_path(voice_name: str, *voice_dirs: str | Path) -> Path:
    name = voice_name.strip()
    if not name:
        raise FileNotFoundError("voice profile name is empty")
    path = Path(name)
    candidates: list[Path] = []
    if path.suffix == ".s2voice":
        candidates.append(path)
        for voice_dir in voice_dirs:
            candidates.append(Path(voice_dir) / path.name)
    else:
        for voice_dir in voice_dirs:
            candidates.append(Path(voice_dir) / f"{name}.s2voice")
        candidates.append(Path(f"{name}.s2voice"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"voice profile not found: {name}")


def voice_output_path(voice_id: str, *voice_dirs: str | Path) -> Path:
    name = validate_voice_id(voice_id)
    user_dir = user_voice_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    output = user_dir / f"{name}.s2voice"
    if name in PROTECTED_VOICE_IDS:
        bundled = resolve_voice_path(name, *voice_dirs) if _voice_exists_in_dirs(name, voice_dirs) else None
        if bundled is not None and bundled.parent.resolve() != user_dir.resolve():
            if output.is_file():
                return output
            raise ValueError(f"bundled voice profile cannot be overwritten: {name}")
    return output


def load_s2voice(path: str | Path) -> VoiceProfile:
    file_path = Path(path)
    data = file_path.read_bytes()
    header_size = 8 + 4 + 16 + 16
    if len(data) < header_size:
        raise ValueError(f"truncated voice profile: {file_path}")
    if data[:8] != MAGIC:
        raise ValueError(f"invalid voice profile magic: {file_path}")
    version, num_codebooks, t_prompt, sample_rate, codebook_size = struct.unpack_from(
        "<Iiiii", data, 8
    )
    if version != VERSION:
        raise ValueError(f"unsupported voice profile version {version}: {file_path}")
    transcript_len, codes_size = struct.unpack_from("<QQ", data, 28)
    if transcript_len == 0:
        raise ValueError(f"invalid voice profile transcript length: {file_path}")
    start = header_size
    end_transcript = start + transcript_len
    end_codes = end_transcript + codes_size
    if end_codes > len(data):
        raise ValueError(f"truncated voice profile: {file_path}")
    transcript_buf = data[start:end_transcript]
    if transcript_buf[-1] != 0:
        raise ValueError(f"transcript not null-terminated: {file_path}")
    if codes_size % 4 != 0:
        raise ValueError(f"invalid voice profile codes size: {file_path}")
    codes = list(struct.unpack_from(f"<{codes_size // 4}i", data, end_transcript))
    return VoiceProfile(
        transcript=transcript_buf[:-1].decode("utf-8"),
        codes=codes,
        num_codebooks=num_codebooks,
        t_prompt=t_prompt,
        sample_rate=sample_rate,
        codebook_size=codebook_size,
        path=file_path,
    )


def save_s2voice(
    path: str | Path,
    *,
    transcript: str,
    codes: list[int],
    t_prompt: int,
    num_codebooks: int | None = None,
    sample_rate: int = S2_SAMPLE_RATE,
    codebook_size: int = S2_CODEBOOK_SIZE,
) -> Path:
    text = transcript.strip()
    if not text:
        raise ValueError("transcript is required")
    if t_prompt <= 0:
        raise ValueError("invalid T_prompt")
    if not codes:
        raise ValueError("voice profile has no prompt codes")
    resolved_num_codebooks = num_codebooks
    if resolved_num_codebooks is None:
        if len(codes) % t_prompt != 0:
            raise ValueError("codes length is not divisible by T_prompt")
        resolved_num_codebooks = len(codes) // t_prompt

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_bytes = text.encode("utf-8") + b"\x00"
    transcript_len = len(transcript_bytes)
    codes_bytes = struct.pack(f"<{len(codes)}i", *codes)
    codes_size = len(codes_bytes)
    payload = bytearray()
    payload.extend(MAGIC)
    payload.extend(struct.pack("<I", VERSION))
    payload.extend(struct.pack("<i", resolved_num_codebooks))
    payload.extend(struct.pack("<i", t_prompt))
    payload.extend(struct.pack("<i", sample_rate))
    payload.extend(struct.pack("<i", codebook_size))
    payload.extend(struct.pack("<Q", transcript_len))
    payload.extend(struct.pack("<Q", codes_size))
    payload.extend(transcript_bytes)
    payload.extend(codes_bytes)
    file_path.write_bytes(payload)
    return file_path
