from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from engine.errors import DownloadCancelled
from engine.model_download import download_file, format_bytes, resolve_content_length
from ttser.i18n import t
from ttser.model_catalog import ModelOption

PROGRESS_MAX = 1000


class ModelDownloadWorker(QThread):
    progress = Signal(int, str)
    status = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, model: ModelOption, destination: Path):
        super().__init__()
        self.model = model
        self.destination = destination
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _emit_progress(self, received: int, total: int) -> None:
        if total > 0:
            percent = min(PROGRESS_MAX, int(received * PROGRESS_MAX / total))
            if received >= total:
                label = f"{format_bytes(received)} / {format_bytes(total)} (100%)"
            else:
                label = f"{format_bytes(received)} / {format_bytes(total)} ({percent / 10:.1f}%)"
            self.progress.emit(percent, label)
            return
        self.progress.emit(0, f"{format_bytes(received)}...")

    def run(self) -> None:
        try:
            self.status.emit(t("download.downloading", filename=self.model.filename))
            total = resolve_content_length(self.model.url, expected_size=self.model.size_bytes)
            if self._cancel_requested:
                return
            self._emit_progress(0, total)
            download_file(
                self.model.url,
                self.destination,
                progress=self._emit_progress,
                expected_size=total,
                should_cancel=lambda: self._cancel_requested,
            )
            if self._cancel_requested:
                return
            self.done.emit(str(self.destination))
        except DownloadCancelled:
            return
        except Exception as exc:
            if not self._cancel_requested:
                self.failed.emit(str(exc))
