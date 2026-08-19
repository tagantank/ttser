from __future__ import annotations

import ctypes
import struct
from pathlib import Path
from typing import Callable

from engine.errors import SynthesisCancelled

PAUSE_PREFIX = "[pause"
# s2 export API requires a non-empty transcript when reference codes are used.
# Voice timbre comes from encoded audio; this placeholder satisfies the API only.
REFERENCE_PROMPT_PLACEHOLDER = "."


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
        voice_dir: Path | None,
        reference_audio_path: Path | None = None,
        progress: Callable[[int, int, Path], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
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
                1,
            )
            if rc != 1:
                raise RuntimeError(f"InitializeS2PipelineFromFiles failed: {rc}")
            rc = self.init_params(params, 768, 0.8, 0.8, 30, -1, threads, 0)
            if rc != 1:
                raise RuntimeError(f"InitializeS2GenerateParams failed: {rc}")

            prompt_codes_ptr = None
            ref_text = None
            if reference_audio_path:
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
                prompt_codes_ptr = prompt_codes
                ref_text = REFERENCE_PROMPT_PLACEHOLDER.encode("utf-8")

            for idx, text in enumerate(lines, start=1):
                if should_cancel and should_cancel():
                    raise SynthesisCancelled()
                out = output_dir / f"output_{idx:03d}.wav"
                pause = parse_pause_seconds(text)
                if pause is not None:
                    write_silence(out, pause)
                else:
                    if voice_name:
                        _ = voice_name, voice_dir
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
        finally:
            if prompt_codes:
                self.release_prompt_codes(prompt_codes)
            self.release_params(params)
            self.release_pipeline(pipeline)
