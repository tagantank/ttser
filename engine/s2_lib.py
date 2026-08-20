from __future__ import annotations

import ctypes
import struct
from pathlib import Path
from typing import Callable

from engine.errors import SynthesisCancelled
from engine.s2_voice import load_s2voice, resolve_voice_path, save_s2voice

PAUSE_PREFIX = "[pause"
# s2 export API requires a non-empty transcript when reference codes are used.
# Voice timbre comes from encoded audio; this placeholder satisfies the API only.
REFERENCE_PROMPT_PLACEHOLDER = "."
WAV_HEADER_MIN = 44
SYNTH_STATUS_NAME = ".ttser-synth-status"
SKIP_MARKER_SUFFIX = ".skip"
MIN_SPEECH_RMS = 1e-3
MIN_SPEECH_PEAK = 0.02
MAX_TRIM_SECONDS = 1.0
MIN_KEEP_RATIO = 0.5


class _StdVectorI32(ctypes.Structure):
    # libstdc++ / libc++ std::vector<int32_t>: begin, end, capacity.
    # S2Synthesize only reads the vector; we never pass this to ReleaseS2AudioPromptCodes.
    _fields_ = (
        ("begin", ctypes.c_void_p),
        ("end", ctypes.c_void_p),
        ("capacity", ctypes.c_void_p),
    )


def _vector_from_codes(codes: list[int]) -> tuple[_StdVectorI32, ctypes.Array]:
    if not codes:
        raise ValueError("voice profile has no prompt codes")
    array = (ctypes.c_int32 * len(codes))(*codes)
    start = ctypes.addressof(array)
    nbytes = len(codes) * ctypes.sizeof(ctypes.c_int32)
    vector = _StdVectorI32(start, start + nbytes, start + nbytes)
    return vector, array


def _read_vector_i32(vector_ptr: int) -> list[int]:
    vec = _StdVectorI32.from_address(vector_ptr)
    if not vec.begin or not vec.end or vec.end <= vec.begin:
        return []
    count = (vec.end - vec.begin) // ctypes.sizeof(ctypes.c_int32)
    return list((ctypes.c_int32 * count).from_address(vec.begin))


def chunk_wav_path(output_dir: Path, idx: int) -> Path:
    return output_dir / f"output_{idx:03d}.wav"


def skip_marker_path(wav_path: Path) -> Path:
    return wav_path.with_name(wav_path.name + SKIP_MARKER_SUFFIX)


def mark_chunk_skipped(path: Path) -> None:
    skip_marker_path(path).write_text("1", encoding="utf-8")


def is_chunk_skipped(path: Path) -> bool:
    return skip_marker_path(path).is_file()


def read_wav_stats(path: Path) -> dict[str, float | int | bool | bytes] | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) < WAV_HEADER_MIN:
        return None
    riff, riff_size, wave = struct.unpack_from("<4sI4s", raw, 0)
    if riff != b"RIFF" or wave != b"WAVE":
        return None
    fmt_code = channels = sample_rate = bits = 0
    payload = b""
    truncated = False
    offset = 12
    while offset + 8 <= len(raw):
        chunk_id, chunk_size = struct.unpack_from("<4sI", raw, offset)
        data_start = offset + 8
        data_end = data_start + chunk_size
        if chunk_id == b"fmt " and chunk_size >= 16 and data_end <= len(raw):
            fmt_code, channels, sample_rate, _byte_rate, _align, bits = struct.unpack_from(
                "<HHIIHH", raw, data_start
            )
        elif chunk_id == b"data":
            available = max(0, len(raw) - data_start)
            truncated = chunk_size > available
            payload = raw[data_start : data_start + min(chunk_size, available)]
            break
        offset = data_end + (chunk_size & 1)
    if sample_rate <= 0 or channels <= 0 or bits <= 0 or not payload:
        return None
    frame_bytes = max(1, channels * (bits // 8))
    n_samples = len(payload) // frame_bytes
    peak = 0.0
    sum_sq = 0.0
    if fmt_code == 3 and bits == 32:
        count = (len(payload) // 4)
        samples = struct.unpack(f"<{count}f", payload[: count * 4])
        n_samples = len(samples)
        for sample in samples:
            amplitude = abs(sample)
            if amplitude > peak:
                peak = amplitude
            sum_sq += sample * sample
    elif fmt_code == 1 and bits == 16:
        count = len(payload) // 2
        samples = struct.unpack(f"<{count}h", payload[: count * 2])
        n_samples = len(samples)
        scale = 32768.0
        for sample in samples:
            value = sample / scale
            amplitude = abs(value)
            if amplitude > peak:
                peak = amplitude
            sum_sq += value * value
    else:
        return None
    rms = (sum_sq / n_samples) ** 0.5 if n_samples else 0.0
    return {
        "n_samples": n_samples,
        "sample_rate": sample_rate,
        "channels": channels,
        "bits": bits,
        "fmt_code": fmt_code,
        "peak": peak,
        "rms": rms,
        "truncated": truncated,
        "riff_ok": riff_size == len(raw) - 8 or not truncated,
        "payload": payload,
    }


def is_complete_wav(path: Path) -> bool:
    stats = read_wav_stats(path)
    return bool(stats) and not stats["truncated"] and int(stats["n_samples"]) > 0


def is_usable_speech_wav(path: Path, generated_samples: int | None = None) -> bool:
    stats = read_wav_stats(path)
    if not stats or stats["truncated"] or int(stats["n_samples"]) <= 0:
        return False
    if float(stats["peak"]) < MIN_SPEECH_PEAK and float(stats["rms"]) < MIN_SPEECH_RMS:
        return False
    if generated_samples and generated_samples > 0:
        sample_rate = int(stats["sample_rate"])
        kept = int(stats["n_samples"])
        lost = generated_samples - kept
        if (
            sample_rate > 0
            and lost > sample_rate * MAX_TRIM_SECONDS
            and kept < generated_samples * MIN_KEEP_RATIO
        ):
            return False
    return True


def first_incomplete_index(lines: list[str], output_dir: Path) -> int | None:
    for idx, text in enumerate(lines, start=1):
        path = chunk_wav_path(output_dir, idx)
        if is_chunk_skipped(path):
            continue
        if parse_pause_seconds(text) is not None:
            if not is_complete_wav(path):
                return idx
        elif not is_usable_speech_wav(path):
            return idx
    return None


def write_synth_status(output_dir: Path, text: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SYNTH_STATUS_NAME).write_text(text, encoding="utf-8")


def read_synth_status(output_dir: Path) -> str:
    path = output_dir / SYNTH_STATUS_NAME
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_wav(
    path: Path,
    payload: bytes,
    *,
    sample_rate: int,
    channels: int,
    bits: int,
    fmt_code: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    block_align = max(1, channels * (bits // 8))
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(payload),
        b"WAVE",
        b"fmt ",
        16,
        fmt_code,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits,
        b"data",
        len(payload),
    )
    path.write_bytes(header + payload)


def write_silence(path: Path, seconds: float, sample_rate: int = 44100) -> None:
    frames = max(1, int(round(sample_rate * seconds)))
    _write_wav(
        path,
        b"\x00\x00\x00\x00" * frames,
        sample_rate=sample_rate,
        channels=1,
        bits=32,
        fmt_code=3,
    )


def append_silence(path: Path, seconds: float) -> None:
    if seconds <= 0:
        return
    stats = read_wav_stats(path)
    if not stats or stats["truncated"]:
        raise ValueError(f"cannot append silence to incomplete WAV: {path}")
    sample_rate = int(stats["sample_rate"])
    channels = int(stats["channels"])
    bits = int(stats["bits"])
    frame_bytes = max(1, channels * (bits // 8))
    extra_frames = max(1, int(round(sample_rate * seconds)))
    payload = bytes(stats["payload"]) + (b"\x00" * extra_frames * frame_bytes)
    _write_wav(
        path,
        payload,
        sample_rate=sample_rate,
        channels=channels,
        bits=bits,
        fmt_code=int(stats["fmt_code"]),
    )


def pad_speech_chunks(lines: list[str], output_dir: Path, pause_ms: int) -> None:
    """Append trailing silence to synthesized speech lines before MP3 concat."""
    seconds = pause_ms / 1000.0
    if seconds <= 0:
        return
    total = len(lines)
    for idx, text in enumerate(lines, start=1):
        if parse_pause_seconds(text) is not None:
            continue
        path = chunk_wav_path(output_dir, idx)
        if is_chunk_skipped(path):
            continue
        next_text = lines[idx] if idx < total else None
        if next_text is not None and parse_pause_seconds(next_text) is not None:
            continue
        if is_usable_speech_wav(path):
            append_silence(path, seconds)


def parse_pause_seconds(text: str) -> float | None:
    t = text.strip().lower()
    if not t.startswith(PAUSE_PREFIX):
        return None
    raw = t.strip("[]").replace("pause", "").strip()
    if not raw:
        return 1.0
    if raw.endswith("ms"):
        return max(0.1, float(raw[:-2]) / 1000.0)
    if raw.endswith("s"):
        return max(0.1, float(raw[:-1]))
    return max(0.1, float(raw))


class S2Library:
    def __init__(self, library_path: Path):
        self.lib = ctypes.CDLL(str(library_path))
        self._bind_symbols()

    def _bind_symbols(self) -> None:
        c_void_p = ctypes.c_void_p
        c_char_p = ctypes.c_char_p
        c_int = ctypes.c_int
        c_int32 = ctypes.c_int32

        self.alloc_pipeline = self.lib.AllocS2Pipeline
        self.alloc_pipeline.restype = c_void_p
        self.release_pipeline = self.lib.ReleaseS2Pipeline
        self.release_pipeline.argtypes = [c_void_p]

        self.alloc_params = self.lib.AllocS2GenerateParams
        self.alloc_params.restype = c_void_p
        self.release_params = self.lib.ReleaseS2GenerateParams
        self.release_params.argtypes = [c_void_p]

        self.init_pipeline = self.lib.InitializeS2PipelineFromFiles
        self.init_pipeline.argtypes = [
            c_void_p,
            c_char_p,
            c_char_p,
            c_int32,
            c_int32,
            c_int32,
            c_int32,
        ]
        self.init_pipeline.restype = c_int

        self.init_params = self.lib.InitializeS2GenerateParams
        self.init_params.argtypes = [
            c_void_p,
            c_int32,
            ctypes.c_float,
            ctypes.c_float,
            c_int32,
            c_int32,
            c_int32,
            c_int,
        ]
        self.init_params.restype = c_int

        self.set_log_level = self.lib.SetS2LogLevel
        self.set_log_level.argtypes = [c_int32]
        self.set_log_level.restype = None
        self.get_log_level = self.lib.GetS2LogLevel
        self.get_log_level.argtypes = []
        self.get_log_level.restype = c_int32

        self.alloc_prompt_codes = self.lib.AllocS2AudioPromptCodes
        self.alloc_prompt_codes.restype = c_void_p
        self.release_prompt_codes = self.lib.ReleaseS2AudioPromptCodes
        self.release_prompt_codes.argtypes = [c_void_p]
        self.init_prompt_codes = self.lib.InitializeAudioPromptCodes
        self.init_prompt_codes.argtypes = [
            c_void_p,
            c_int32,
            c_char_p,
            c_void_p,
            ctypes.POINTER(c_int32),
        ]
        self.init_prompt_codes.restype = c_int

        self.synthesize = self.lib.S2Synthesize
        self.synthesize.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
            ctypes.POINTER(c_int32),
            c_char_p,
            c_char_p,
            c_char_p,
            c_char_p,
            ctypes.POINTER(c_int32),
        ]
        self.synthesize.restype = c_int

    def encode_and_save_voice(
        self,
        *,
        model_path: Path,
        tokenizer_path: Path,
        backend_type: int,
        gpu_device: int,
        threads: int,
        reference_audio_path: Path,
        transcript: str,
        output_path: Path,
        codec_follow_backend: int | None = None,
    ) -> Path:
        if codec_follow_backend is None:
            codec_follow_backend = 0 if backend_type == 0 else 1
        pipeline = self.alloc_pipeline()
        prompt_codes = None
        t_prompt = ctypes.c_int32(0)
        try:
            rc = self.init_pipeline(
                pipeline,
                str(model_path).encode(),
                str(tokenizer_path).encode(),
                gpu_device,
                backend_type,
                0,
                codec_follow_backend,
            )
            if rc != 1:
                raise RuntimeError(f"InitializeS2PipelineFromFiles failed: {rc}")
            prompt_codes = self.alloc_prompt_codes()
            rc = self.init_prompt_codes(
                pipeline,
                threads,
                str(reference_audio_path).encode("utf-8"),
                prompt_codes,
                ctypes.byref(t_prompt),
            )
            if rc != 1:
                raise RuntimeError(f"InitializeAudioPromptCodes failed: {rc}")
            codes = _read_vector_i32(int(prompt_codes))
            if not codes or t_prompt.value <= 0:
                raise RuntimeError("Reference audio produced no prompt codes")
            return save_s2voice(
                output_path,
                transcript=transcript,
                codes=codes,
                t_prompt=t_prompt.value,
            )
        finally:
            if prompt_codes:
                self.release_prompt_codes(prompt_codes)
            self.release_pipeline(pipeline)

    def synthesize_batch(
        self,
        lines: list[str],
        output_dir: Path,
        model_path: Path,
        tokenizer_path: Path,
        backend_type: int,
        gpu_device: int,
        n_gpu_layers: int,
        threads: int,
        voice_name: str | None,
        voice_dirs: list[Path] | None,
        progress: Callable[[int, int, Path], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        skip_existing: bool = False,
        codec_follow_backend: int | None = None,
        max_new_tokens: int = 1024,
        temperature: float = 0.8,
        top_p: float = 0.8,
        top_k: int = 30,
        min_tokens_before_end: int = 0,
        verbose: bool = False,
        log_level: int = 2,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        if backend_type == 0:
            # Vulkan on shared iGPU RAM: keep the codec on CPU. GPU codec
            # auto-benchmark creates a second Vulkan context and on RADV can
            # decode to silence or truncated audio, then DeviceLost.
            codec_follow_backend = 0
        elif codec_follow_backend is None:
            codec_follow_backend = 1
        write_synth_status(output_dir, "init")
        self.set_log_level(log_level)
        pipeline = self.alloc_pipeline()
        params = self.alloc_params()
        prompt_codes = None
        t_prompt = ctypes.c_int32(0)
        try:
            rc = self.init_pipeline(
                pipeline,
                str(model_path).encode(),
                str(tokenizer_path).encode(),
                gpu_device,
                backend_type,
                n_gpu_layers,
                codec_follow_backend,
            )
            if rc != 1:
                raise RuntimeError(f"InitializeS2PipelineFromFiles failed: {rc}")
            rc = self.init_params(
                params,
                max_new_tokens,
                float(temperature),
                float(top_p),
                top_k,
                min_tokens_before_end,
                threads,
                1 if verbose else 0,
            )
            if rc != 1:
                raise RuntimeError(f"InitializeS2GenerateParams failed: {rc}")

            prompt_codes_ptr = None
            ref_text = None
            voice_codes_keep = None
            if voice_name and voice_dirs:
                profile = load_s2voice(resolve_voice_path(voice_name, *voice_dirs))
                voice_vector, voice_array = _vector_from_codes(profile.codes)
                voice_codes_keep = (voice_vector, voice_array)
                prompt_codes_ptr = ctypes.byref(voice_vector)
                t_prompt = ctypes.c_int32(profile.t_prompt)
                transcript = profile.transcript.strip() or REFERENCE_PROMPT_PLACEHOLDER
                ref_text = transcript.encode("utf-8")

            write_synth_status(output_dir, "ready")
            for idx, text in enumerate(lines, start=1):
                if should_cancel and should_cancel():
                    raise SynthesisCancelled()
                out = chunk_wav_path(output_dir, idx)
                pause = parse_pause_seconds(text)
                if skip_existing:
                    if is_chunk_skipped(out) and is_complete_wav(out):
                        if progress:
                            progress(idx, len(lines), out)
                        continue
                    if pause is not None and is_complete_wav(out):
                        if progress:
                            progress(idx, len(lines), out)
                        continue
                    if pause is None and is_usable_speech_wav(out):
                        if progress:
                            progress(idx, len(lines), out)
                        continue
                    out.unlink(missing_ok=True)
                    skip_marker_path(out).unlink(missing_ok=True)
                write_synth_status(output_dir, f"line {idx}")
                if pause is not None:
                    write_silence(out, pause)
                else:
                    n_samples = ctypes.c_int32(0)
                    rc = self.synthesize(
                        pipeline,
                        params,
                        None,
                        prompt_codes_ptr,
                        ctypes.byref(t_prompt) if prompt_codes_ptr else None,
                        None,
                        ref_text,
                        text.encode("utf-8"),
                        str(out).encode(),
                        ctypes.byref(n_samples),
                    )
                    if rc <= -4 or rc in (0, -6, -7, -8):
                        raise RuntimeError(f"S2Synthesize failed on line {idx}: {rc}")
                    if not is_usable_speech_wav(out, generated_samples=n_samples.value):
                        stats = read_wav_stats(out) or {}
                        out.unlink(missing_ok=True)
                        raise RuntimeError(
                            f"S2Synthesize produced unusable audio on line {idx}: "
                            f"rms={float(stats.get('rms', 0)):.4f} "
                            f"peak={float(stats.get('peak', 0)):.4f} "
                            f"samples={int(stats.get('n_samples', 0))}/"
                            f"{n_samples.value}"
                        )
                if progress:
                    progress(idx, len(lines), out)
            write_synth_status(output_dir, "done")
        finally:
            if prompt_codes:
                self.release_prompt_codes(prompt_codes)
            self.release_params(params)
            self.release_pipeline(pipeline)
