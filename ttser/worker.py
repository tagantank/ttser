from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from queue import Empty, Queue

from PySide6.QtCore import QThread, Signal

from engine.concat_to_mp3 import main as concat_main
from engine.errors import SynthesisCancelled
from engine.pronunciation import apply_rules, load_rules
from engine.s2_lib import (
    SYNTH_STATUS_NAME,
    S2Library,
    chunk_wav_path,
    first_incomplete_index,
    mark_chunk_skipped,
    pad_speech_chunks,
    read_synth_status,
    skip_marker_path,
    write_silence,
    write_synth_status,
)

from ttser.i18n import t

GPU_BACKENDS = {0, 1, 2}
MAX_LINE_ATTEMPTS = 2
JOB_NAME = ".ttser-synth-job.json"


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
        voice_name: str | None = None,
        voice_dirs: list[str] | None = None,
        n_gpu_layers: int = -1,
        codec_follow_backend: int | None = None,
        max_new_tokens: int = 1024,
        temperature: float = 0.8,
        top_p: float = 0.8,
        top_k: int = 30,
        min_tokens_before_end: int = 0,
        line_pause_ms: int = 180,
        verbose: bool = False,
        log_level: int = 2,
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
        self.voice_name = voice_name
        self.voice_dirs = voice_dirs
        self.n_gpu_layers = n_gpu_layers
        self.codec_follow_backend = codec_follow_backend
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.min_tokens_before_end = min_tokens_before_end
        self.line_pause_ms = line_pause_ms
        self.verbose = verbose
        self.log_level = log_level
        self._cancel_requested = False
        self._child: subprocess.Popen[str] | None = None

    def request_cancel(self) -> None:
        self._cancel_requested = True
        child = self._child
        if child is None or child.poll() is not None:
            return
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            child.terminate()

    def run(self) -> None:
        try:
            text = self.input_text
            if self.dictionaries_enabled:
                total = 0
                for path in self.dictionary_paths:
                    rules = load_rules(Path(path))
                    text, stats = apply_rules(text, rules)
                    total += sum(stats.values())
                self.log.emit(t("worker.pronunciation_replacements", total=total))

            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError(t("worker.no_lines"))

            output_dir = Path(self.wav_dir)
            if output_dir.is_dir():
                for old in output_dir.glob("output_*.wav"):
                    old.unlink(missing_ok=True)
                    skip_marker_path(old).unlink(missing_ok=True)
                for name in (JOB_NAME, SYNTH_STATUS_NAME):
                    (output_dir / name).unlink(missing_ok=True)

            if self.backend_type in GPU_BACKENDS:
                self._synthesize_isolated(lines)
            else:
                self._synthesize_in_process(lines)

            if self._cancel_requested:
                self.cancelled.emit()
                return

            pad_speech_chunks(lines, Path(self.wav_dir), self.line_pause_ms)

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

    def _synthesize_in_process(self, lines: list[str]) -> None:
        lib_dir = Path(self.library_path).parent
        prev_ld = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev_ld}" if prev_ld else str(lib_dir)

        lib = S2Library(Path(self.library_path))
        voice_dirs = [Path(path) for path in self.voice_dirs] if self.voice_dirs else None
        lib.synthesize_batch(
            lines=lines,
            output_dir=Path(self.wav_dir),
            model_path=Path(self.model_path),
            tokenizer_path=Path(self.tokenizer_path),
            backend_type=self.backend_type,
            gpu_device=self.gpu_device,
            n_gpu_layers=self.n_gpu_layers if self.backend_type in GPU_BACKENDS else 0,
            threads=self.threads,
            voice_name=self.voice_name,
            voice_dirs=voice_dirs,
            progress=lambda i, n, _: self.progress.emit(i, n),
            should_cancel=lambda: self._cancel_requested,
            codec_follow_backend=self.codec_follow_backend,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            min_tokens_before_end=self.min_tokens_before_end,
            verbose=self.verbose,
            log_level=self.log_level,
        )

    def _synthesize_isolated(self, lines: list[str]) -> None:
        output_dir = Path(self.wav_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        job_path = output_dir / JOB_NAME
        job = {
            "lines": lines,
            "output_dir": str(output_dir),
            "library_path": self.library_path,
            "model_path": self.model_path,
            "tokenizer_path": self.tokenizer_path,
            "backend_type": self.backend_type,
            "gpu_device": self.gpu_device,
            "n_gpu_layers": self.n_gpu_layers,
            "threads": self.threads,
            "voice_name": self.voice_name,
            "voice_dirs": self.voice_dirs,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_tokens_before_end": self.min_tokens_before_end,
            "verbose": self.verbose,
            "log_level": self.log_level,
        }
        if self.backend_type == 0:
            job["codec_follow_backend"] = 0
        elif self.codec_follow_backend is not None:
            job["codec_follow_backend"] = self.codec_follow_backend
        job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

        line_attempts: dict[int, int] = {}
        init_failures = 0
        max_restarts = len(lines) + 4
        try:
            for _ in range(max_restarts):
                if self._cancel_requested:
                    raise SynthesisCancelled()
                missing = first_incomplete_index(lines, output_dir)
                if missing is None:
                    return
                self.progress.emit(missing - 1, len(lines))
                rc = self._run_synth_child(job_path)
                if self._cancel_requested:
                    raise SynthesisCancelled()
                if rc == 2:
                    raise SynthesisCancelled()
                if rc == 0 and first_incomplete_index(lines, output_dir) is None:
                    return

                status = read_synth_status(output_dir)
                missing = first_incomplete_index(lines, output_dir)
                if missing is None:
                    return
                if status in ("", "init"):
                    init_failures += 1
                    if init_failures >= 2:
                        raise RuntimeError(t("worker.gpu_pipeline_failed"))
                    self.log.emit(t("worker.gpu_init_retry"))
                    continue

                line_attempts[missing] = line_attempts.get(missing, 0) + 1
                snippet = lines[missing - 1]
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                if line_attempts[missing] < MAX_LINE_ATTEMPTS:
                    self.log.emit(
                        t(
                            "worker.gpu_device_lost",
                            line=missing,
                            snippet=snippet,
                        )
                    )
                    continue
                out = chunk_wav_path(output_dir, missing)
                write_silence(out, 0.4)
                mark_chunk_skipped(out)
                write_synth_status(output_dir, f"skipped {missing}")
                self.log.emit(
                    t(
                        "worker.gpu_skip_line",
                        line=missing,
                        snippet=snippet,
                    )
                )

            if first_incomplete_index(lines, output_dir) is not None:
                raise RuntimeError(t("worker.gpu_repeated_crash"))
        finally:
            job_path.unlink(missing_ok=True)

    def _run_synth_child(self, job_path: Path) -> int:
        env = os.environ.copy()
        lib_dir = Path(self.library_path).parent
        prev_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev_ld}" if prev_ld else str(lib_dir)
        env["PYTHONUNBUFFERED"] = "1"
        if self.backend_type == 0:
            env.setdefault("GGML_VK_DISABLE_COOPMAT", "1")
            env.setdefault("GGML_VK_ALLOW_SYSMEM_FALLBACK", "1")

        cmd = [sys.executable, "-m", "engine.s2_synth", "--job", str(job_path)]
        self._child = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            env=env,
            start_new_session=True,
        )
        proc = self._child
        assert proc.stdout is not None
        lines_q: Queue[str | None] = Queue()

        def _pump() -> None:
            try:
                for line in proc.stdout:
                    lines_q.put(line)
            finally:
                lines_q.put(None)

        reader = threading.Thread(target=_pump, daemon=True)
        reader.start()
        try:
            while True:
                if self._cancel_requested and proc.poll() is None:
                    self.request_cancel()
                try:
                    line = lines_q.get(timeout=0.2)
                except Empty:
                    continue
                if line is None:
                    break
                text = line.rstrip()
                if text.startswith("PROGRESS "):
                    parts = text.split()
                    if len(parts) >= 3:
                        self.progress.emit(int(parts[1]), int(parts[2]))
                    continue
                if text:
                    self.log.emit(text)
            try:
                return proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.kill()
                return proc.wait(timeout=3)
        finally:
            self._child = None
