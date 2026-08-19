from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ttser.backends import backend_type_for, library_path_for_backend, normalize_backend
from ttser.dictionary_editor import DictionaryEditorDialog
from ttser.settings import AppSettings, load_settings, save_settings
from ttser.settings_dialog import SettingsDialog
from ttser.worker import SynthesisWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_obj: AppSettings = load_settings()
        self.worker: SynthesisWorker | None = None
        self.setWindowTitle("ttser — Fish Audio S2 Pro")
        self.resize(920, 680)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.input_path = QLineEdit()
        btn_input = QPushButton("Текст...")
        btn_input.clicked.connect(self.pick_input)
        top.addWidget(QLabel("Input"))
        top.addWidget(self.input_path, 1)
        top.addWidget(btn_input)
        layout.addLayout(top)

        mid = QHBoxLayout()
        self.output_path = QLineEdit("output/result.mp3")
        btn_output = QPushButton("MP3...")
        btn_output.clicked.connect(self.pick_output)
        mid.addWidget(QLabel("Output MP3"))
        mid.addWidget(self.output_path, 1)
        mid.addWidget(btn_output)
        layout.addLayout(mid)

        self.use_reference_voice = QCheckBox("Использовать пример голоса")
        self.use_reference_voice.setChecked(self.settings_obj.reference_voice_enabled)
        self.use_reference_voice.toggled.connect(self.on_reference_voice_toggled)
        layout.addWidget(self.use_reference_voice)

        self.reference_voice_widget = QWidget()
        voice_ref = QHBoxLayout(self.reference_voice_widget)
        voice_ref.setContentsMargins(0, 0, 0, 0)
        self.reference_audio_path = QLineEdit()
        self.btn_ref_audio = QPushButton("Голос...")
        self.btn_ref_audio.clicked.connect(self.pick_reference_audio)
        voice_ref.addWidget(QLabel("Пример голоса"))
        voice_ref.addWidget(self.reference_audio_path, 1)
        voice_ref.addWidget(self.btn_ref_audio)
        layout.addWidget(self.reference_voice_widget)

        flags = QHBoxLayout()
        self.apply_dicts = QCheckBox("Применять словари")
        self.apply_dicts.setChecked(self.settings_obj.dictionaries_enabled)
        flags.addWidget(self.apply_dicts)
        layout.addLayout(flags)

        buttons = QHBoxLayout()
        btn_settings = QPushButton("Настройки")
        btn_settings.clicked.connect(self.open_settings)
        btn_dicts = QPushButton("Словари")
        btn_dicts.clicked.connect(self.open_dicts)
        btn_start = QPushButton("Синтез")
        btn_start.clicked.connect(self.start)
        self.btn_start = btn_start
        btn_stop = QPushButton("Стоп")
        btn_stop.clicked.connect(self.stop)
        self.btn_stop = btn_stop
        buttons.addWidget(btn_settings)
        buttons.addWidget(btn_dicts)
        buttons.addStretch(1)
        buttons.addWidget(btn_stop)
        buttons.addWidget(btn_start)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        self.reference_audio_path.setText(self.settings_obj.reference_audio_path)
        self.reference_audio_path.editingFinished.connect(self.persist_voice_fields)
        self.on_reference_voice_toggled(self.use_reference_voice.isChecked())
        self._set_synthesis_running(False)

    def on_reference_voice_toggled(self, enabled: bool) -> None:
        self.reference_voice_widget.setVisible(enabled)
        self.persist_voice_fields()

    def persist_voice_fields(self) -> None:
        self.settings_obj.reference_voice_enabled = self.use_reference_voice.isChecked()
        self.settings_obj.reference_audio_path = self.reference_audio_path.text().strip()
        save_settings(self.settings_obj)

    def pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите текст", "", "Text (*.txt *.md)")
        if path:
            self.input_path.setText(path)

    def pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Куда сохранить mp3", "output/result.mp3", "MP3 (*.mp3)")
        if path:
            self.output_path.setText(path)

    def pick_reference_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите пример голоса",
            "",
            "Audio (*.wav *.mp3 *.flac *.m4a *.ogg)",
        )
        if path:
            self.reference_audio_path.setText(path)
            self.persist_voice_fields()

    def open_settings(self) -> None:
        self.persist_voice_fields()
        dialog = SettingsDialog(self.settings_obj, self)
        if dialog.exec():
            self.settings_obj = dialog.to_settings()
            self.settings_obj.backend = normalize_backend(self.settings_obj)
            self.settings_obj.dictionaries_enabled = self.apply_dicts.isChecked()
            save_settings(self.settings_obj)

    def open_dicts(self) -> None:
        self.persist_voice_fields()
        dialog = DictionaryEditorDialog(self.settings_obj.dictionary_paths, self)
        if dialog.exec():
            self.settings_obj.dictionary_paths = dialog.dictionary_paths
            save_settings(self.settings_obj)

    def _set_synthesis_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def start(self) -> None:
        input_file = Path(self.input_path.text().strip())
        output_mp3 = Path(self.output_path.text().strip())
        if not input_file.is_file():
            QMessageBox.warning(self, "Ошибка", "Input file not found")
            return

        self.settings_obj.backend = normalize_backend(self.settings_obj)
        library_path = library_path_for_backend(self.settings_obj)
        if not library_path.is_file():
            QMessageBox.warning(self, "Ошибка", f"Library not found: {library_path}")
            return

        reference_audio = ""
        if self.use_reference_voice.isChecked():
            reference_audio = self.reference_audio_path.text().strip()
            if not reference_audio:
                QMessageBox.warning(self, "Ошибка", "Укажите файл примера голоса")
                return
            if not Path(reference_audio).is_file():
                QMessageBox.warning(self, "Ошибка", "Файл примера голоса не найден")
                return

        text = input_file.read_text(encoding="utf-8")
        output_mp3.parent.mkdir(parents=True, exist_ok=True)
        wav_dir = output_mp3.with_suffix("").as_posix() + "_wav"

        self._set_synthesis_running(True)
        self.progress.setValue(0)
        self.log.clear()
        self.settings_obj.dictionaries_enabled = self.apply_dicts.isChecked()
        self.settings_obj.reference_voice_enabled = self.use_reference_voice.isChecked()
        self.settings_obj.reference_audio_path = reference_audio
        save_settings(self.settings_obj)

        self.worker = SynthesisWorker(
            input_text=text,
            output_mp3=str(output_mp3),
            wav_dir=wav_dir,
            library_path=str(library_path),
            model_path=self.settings_obj.model_path,
            tokenizer_path=self.settings_obj.tokenizer_path,
            backend_type=backend_type_for(self.settings_obj),
            gpu_device=self.settings_obj.vulkan_device,
            threads=self.settings_obj.threads,
            dictionary_paths=self.settings_obj.dictionary_paths,
            dictionaries_enabled=self.settings_obj.dictionaries_enabled,
            reference_audio_path=reference_audio or None,
        )
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.start()

    def stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.log.appendPlainText("Остановка после текущего фрагмента...")
            self.btn_stop.setEnabled(False)
            self.worker.request_cancel()

    def on_progress(self, idx: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(idx)
        self.log.appendPlainText(f"[{idx}/{total}]")

    def on_done(self, output: str) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText(f"Done: {output}")
        QMessageBox.information(self, "Готово", f"MP3 created:\n{output}")

    def on_cancelled(self) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText("Synthesis stopped.")

    def on_failed(self, error: str) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText(f"Error: {error}")
        QMessageBox.critical(self, "Ошибка", error)
