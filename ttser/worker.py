from __future__ import annotations

from pathlib import Path
import os

from PySide6.QtCore import QThread, Signal

from engine.concat_to_mp3 import main as concat_main
from engine.errors import SynthesisCancelled
from engine.pronunciation import apply_rules, load_rules
from engine.s2_lib import S2Library


class SynthesisWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        input_text: str,
        output_mp3: str,
        wav_dir: str,
        library_path: str,
        model_path: str,
        tokenizer_path: str,
        backend_type: int,
        gpu_device: int,
        threads: int,
        dictionary_paths: list[str],
        dictionaries_enabled: bool,
        reference_audio_path: str | None,
    ):
        super().__init__()
        self.input_text = input_text
        self.output_mp3 = output_mp3
        self.wav_dir = wav_dir
        self.library_path = library_path
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.backend_type = backend_type
        self.gpu_device = gpu_device
        self.threads = threads
        self.dictionary_paths = dictionary_paths
        self.dictionaries_enabled = dictionaries_enabled
        self.reference_audio_path = reference_audio_path
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            text = self.input_text
            if self.dictionaries_enabled:
                total = 0
                for path in self.dictionary_paths:
                    rules = load_rules(Path(path))
                    text, stats = apply_rules(text, rules)
                    total += sum(stats.values())
                self.log.emit(f"Pronunciation replacements: {total}")

            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError("No lines to synthesize")

            lib_dir = Path(self.library_path).parent
            prev_ld = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev_ld}" if prev_ld else str(lib_dir)

            lib = S2Library(Path(self.library_path))
            lib.synthesize_batch(
                lines=lines,
                output_dir=Path(self.wav_dir),
                model_path=Path(self.model_path),
                tokenizer_path=Path(self.tokenizer_path),
                backend_type=self.backend_type,
                gpu_device=self.gpu_device,
                n_gpu_layers=-1 if self.backend_type in (0, 1, 2) else 0,
                threads=self.threads,
                voice_name=None,
                voice_dir=None,
                reference_audio_path=Path(self.reference_audio_path) if self.reference_audio_path else None,
                progress=lambda i, n, _: self.progress.emit(i, n),
                should_cancel=lambda: self._cancel_requested,
            )

            if self._cancel_requested:
                self.cancelled.emit()
                return

            import sys

            prev = sys.argv[:]
            sys.argv = [
                "concat_to_mp3.py",
                self.wav_dir,
                self.output_mp3,
                "--bitrate",
                "128k",
                "--stereo",
                "--overwrite",
            ]
            try:
                concat_main()
            finally:
                sys.argv = prev
            if self._cancel_requested:
                self.cancelled.emit()
                return
            self.done.emit(self.output_mp3)
        except SynthesisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
