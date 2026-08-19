from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from engine.s2_voice import (
    PROTECTED_VOICE_IDS,
    resolve_voice_path,
    user_voice_dir,
    validate_voice_id,
    voice_search_dirs,
)
from ttser.backends import backend_type_for, library_path_for_backend, normalize_backend
from ttser.settings import AppSettings
from ttser.voice_create_worker import VoiceCreateWorker


class VoiceCreateDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.created_voice_id = ""
        self.worker: VoiceCreateWorker | None = None
        self.setWindowTitle("Создать голос")
        self.resize(640, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.voice_name = QLineEdit()
        self.audio_path = QLineEdit()
        audio_row = QHBoxLayout()
        audio_row.addWidget(self.audio_path, 1)
        btn_audio = QPushButton("...")
        btn_audio.clicked.connect(self.pick_audio)
        audio_row.addWidget(btn_audio)
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText("Точный текст, произнесённый в reference-аудио")
        form.addRow("Имя", self.voice_name)
        form.addRow("Аудио", audio_row)
        form.addRow("Транскрипт", self.transcript)
        layout.addLayout(form)
        layout.addWidget(
            QLabel("Нужен короткий клип 5–30 секунд (WAV или MP3) и точный транскрипт.")
        )

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.create_voice)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите reference-аудио",
            "",
            "Audio (*.wav *.mp3 *.flac *.m4a *.ogg)",
        )
        if path:
            self.audio_path.setText(path)

    def _set_busy(self, busy: bool) -> None:
        self.voice_name.setEnabled(not busy)
        self.audio_path.setEnabled(not busy)
        self.transcript.setEnabled(not busy)
        self.buttons.setEnabled(not busy)

    def create_voice(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            voice_id = validate_voice_id(self.voice_name.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return

        audio = self.audio_path.text().strip()
        if not audio or not Path(audio).is_file():
            QMessageBox.warning(self, "Ошибка", "Укажите существующий аудиофайл")
            return

        transcript = self.transcript.toPlainText().strip()
        if not transcript:
            QMessageBox.warning(self, "Ошибка", "Укажите транскрипт reference-аудио")
            return

        search_dirs = [str(path) for path in voice_search_dirs(self.settings.voice_dir)]
        output_path = user_voice_dir() / f"{voice_id}.s2voice"
        if output_path.is_file():
            answer = QMessageBox.question(
                self,
                "Перезаписать?",
                f"Профиль {voice_id}.s2voice уже существует. Перезаписать?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if voice_id in PROTECTED_VOICE_IDS:
            try:
                bundled = resolve_voice_path(voice_id, *search_dirs)
            except FileNotFoundError:
                bundled = None
            if bundled is not None and bundled.resolve() != output_path.resolve():
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Имя {voice_id} зарезервировано для встроенного профиля",
                )
                return

        self.settings.backend = normalize_backend(self.settings)
        library_path = library_path_for_backend(self.settings)
        if not library_path.is_file():
            QMessageBox.warning(self, "Ошибка", f"Library not found: {library_path}")
            return
        if not Path(self.settings.model_path).is_file():
            QMessageBox.warning(self, "Ошибка", "Модель не найдена. Скачайте её в Настройках.")
            return

        self._set_busy(True)
        self.worker = VoiceCreateWorker(
            library_path=str(library_path),
            model_path=self.settings.model_path,
            tokenizer_path=self.settings.tokenizer_path,
            backend=self.settings.backend,
            gpu_device=self.settings.vulkan_device,
            threads=self.settings.threads,
            reference_audio_path=audio,
            transcript=transcript,
            output_path=str(output_path),
        )
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_done(self, path: str) -> None:
        self._set_busy(False)
        self.created_voice_id = Path(path).stem
        self.accept()

    def on_failed(self, error: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "Ошибка", error)
