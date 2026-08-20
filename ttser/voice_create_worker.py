from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from engine.runtime import prepend_library_path
from engine.s2_lib import S2Library
from ttser.backends import backend_type_for
from ttser.settings import AppSettings


class VoiceCreateWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        library_path: str,
        model_path: str,
        tokenizer_path: str,
        backend: str,
        gpu_device: int,
        threads: int,
        reference_audio_path: str,
        transcript: str,
        output_path: str,
    ):
        super().__init__()
        self.library_path = library_path
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.backend = backend
        self.gpu_device = gpu_device
        self.threads = threads
        self.reference_audio_path = reference_audio_path
        self.transcript = transcript
        self.output_path = output_path

    def run(self) -> None:
        try:
            prepend_library_path(os.environ, Path(self.library_path).parent)

            settings = AppSettings(backend=self.backend, vulkan_device=self.gpu_device)
            backend_type = backend_type_for(settings)

            lib = S2Library(Path(self.library_path))
            saved = lib.encode_and_save_voice(
                model_path=Path(self.model_path),
                tokenizer_path=Path(self.tokenizer_path),
                backend_type=backend_type,
                gpu_device=self.gpu_device,
                threads=self.threads,
                reference_audio_path=Path(self.reference_audio_path),
                transcript=self.transcript,
                output_path=Path(self.output_path),
                codec_follow_backend=0 if backend_type == 0 else None,
            )
            self.done.emit(str(saved))
        except Exception as exc:
            self.failed.emit(str(exc))
