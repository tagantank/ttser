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


def is_complete_wav(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > WAV_HEADER_MIN
    except OSError:
        return False


def first_incomplete_index(n_lines: int, output_dir: Path) -> int | None:
    for idx in range(1, n_lines + 1):
        if not is_complete_wav(chunk_wav_path(output_dir, idx)):
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


def write_silence(path: Path, seconds: float, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(sample_rate * seconds)))
    data = b"\x00\x00\x00\x00" * frames
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        3,
        1,
        sample_rate,
        sample_rate * 4,
        4,
        32,
        b"data",
        len(data),
    )
    path.write_bytes(header + data)


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
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        if codec_follow_backend is None:
            # Vulkan on shared iGPU RAM: keep the codec on CPU so AR inference
            # does not compete with a second Vulkan context for UMA memory.
            codec_follow_backend = 0 if backend_type == 0 else 1
        write_synth_status(output_dir, "init")
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
            rc = self.init_params(params, 768, 0.8, 0.8, 30, -1, threads, 0)
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
                if skip_existing and is_complete_wav(out):
                    if progress:
                        progress(idx, len(lines), out)
                    continue
                write_synth_status(output_dir, f"line {idx}")
                pause = parse_pause_seconds(text)
                if pause is not None:
                    write_silence(out, pause)
                else:
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
                        None,
                    )
                    if rc <= -4 or rc in (0, -6, -7, -8):
                        raise RuntimeError(f"S2Synthesize failed on line {idx}: {rc}")
                if progress:
                    progress(idx, len(lines), out)
            write_synth_status(output_dir, "done")
        finally:
            if prompt_codes:
                self.release_prompt_codes(prompt_codes)
            self.release_params(params)
            self.release_pipeline(pipeline)
