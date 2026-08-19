from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from engine.s2_voice import (
    DEFAULT_VOICE_ID,
    list_voice_ids,
    preferred_voice_id,
    resolve_voice_path,
    voice_search_dirs,
)
from ttser.backends import backend_type_for, library_path_for_backend, normalize_backend
from ttser.dictionary_editor import DictionaryEditorDialog
from ttser.i18n import apply_language, t
from ttser.settings import AppSettings, load_settings, save_settings
from ttser.settings_dialog import SettingsDialog
from ttser.voice_create_dialog import VoiceCreateDialog
from ttser.worker import SynthesisWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_obj: AppSettings = load_settings()
        self.worker: SynthesisWorker | None = None
        self.resize(920, 680)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.input_path = QLineEdit()
        self.lbl_input = QLabel()
        self.btn_input = QPushButton()
        self.btn_input.clicked.connect(self.pick_input)
        top.addWidget(self.lbl_input)
        top.addWidget(self.input_path, 1)
        top.addWidget(self.btn_input)
        layout.addLayout(top)

        mid = QHBoxLayout()
        self.output_path = QLineEdit("output/result.mp3")
        self.lbl_output = QLabel()
        self.btn_output = QPushButton()
        self.btn_output.clicked.connect(self.pick_output)
        mid.addWidget(self.lbl_output)
        mid.addWidget(self.output_path, 1)
        mid.addWidget(self.btn_output)
        layout.addLayout(mid)

        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        self.voice_combo.currentIndexChanged.connect(self.on_voice_choice_changed)
        self.lbl_voice = QLabel()
        self.btn_create_voice = QPushButton()
        self.btn_create_voice.clicked.connect(self.open_create_voice)
        voice_row.addWidget(self.lbl_voice)
        voice_row.addWidget(self.voice_combo, 1)
        voice_row.addWidget(self.btn_create_voice)
        layout.addLayout(voice_row)

        flags = QHBoxLayout()
        self.apply_dicts = QCheckBox()
        self.apply_dicts.setChecked(self.settings_obj.dictionaries_enabled)
        flags.addWidget(self.apply_dicts)
        layout.addLayout(flags)

        buttons = QHBoxLayout()
        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_dicts = QPushButton()
        self.btn_dicts.clicked.connect(self.open_dicts)
        self.btn_start = QPushButton()
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton()
        self.btn_stop.clicked.connect(self.stop)
        buttons.addWidget(self.btn_settings)
        buttons.addWidget(self.btn_dicts)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_stop)
        buttons.addWidget(self.btn_start)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        self.retranslate()
        self.reload_voices()
        self._set_synthesis_running(False)

    def retranslate(self) -> None:
        self.setWindowTitle(t("main.title"))
        self.lbl_input.setText(t("main.input"))
        self.btn_input.setText(t("main.text_btn"))
        self.lbl_output.setText(t("main.output_mp3"))
        self.btn_output.setText(t("main.mp3_btn"))
        self.lbl_voice.setText(t("main.voice"))
        self.btn_create_voice.setText(t("main.create_voice"))
        self.apply_dicts.setText(t("main.apply_dicts"))
        self.btn_settings.setText(t("main.settings"))
        self.btn_dicts.setText(t("main.dictionaries"))
        self.btn_start.setText(t("main.synthesize"))
        self.btn_stop.setText(t("main.stop"))
        self._refresh_default_voice_label()

    def _refresh_default_voice_label(self) -> None:
        idx = self.voice_combo.findData(DEFAULT_VOICE_ID)
        if idx >= 0:
            self.voice_combo.setItemText(idx, t("voice.default_label"))

    def voice_dirs(self) -> list[str]:
        return [str(path) for path in voice_search_dirs(self.settings_obj.voice_dir)]

    def reload_voices(self, select_voice_id: str | None = None) -> None:
        requested = select_voice_id if select_voice_id is not None else self.settings_obj.selected_voice_id
        dirs = self.voice_dirs()
        selected = preferred_voice_id(*dirs, requested=requested)
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        self.voice_combo.addItem(t("voice.default_label"), DEFAULT_VOICE_ID)
        for voice_id in list_voice_ids(*dirs):
            self.voice_combo.addItem(voice_id, voice_id)
        idx = self.voice_combo.findData(selected)
        self.voice_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.voice_combo.blockSignals(False)
        self.settings_obj.selected_voice_id = self.selected_voice_id()
        save_settings(self.settings_obj)

    def selected_voice_id(self) -> str:
        data = self.voice_combo.currentData()
        return DEFAULT_VOICE_ID if data is None else str(data)

    def on_voice_choice_changed(self, _index: int) -> None:
        self.settings_obj.selected_voice_id = self.selected_voice_id()
        save_settings(self.settings_obj)

    def pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("main.pick_input"), "", "Text (*.txt *.md)")
        if path:
            self.input_path.setText(path)

    def pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("main.pick_output"), "output/result.mp3", "MP3 (*.mp3)"
        )
        if path:
            self.output_path.setText(path)

    def open_create_voice(self) -> None:
        dialog = VoiceCreateDialog(self.settings_obj, self)
        if dialog.exec():
            self.reload_voices(select_voice_id=dialog.created_voice_id)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings_obj, self)
        if dialog.exec():
            self.settings_obj = dialog.to_settings()
            self.settings_obj.backend = normalize_backend(self.settings_obj)
            self.settings_obj.dictionaries_enabled = self.apply_dicts.isChecked()
            save_settings(self.settings_obj)
            app = QApplication.instance()
            if app is not None:
                apply_language(app, self.settings_obj.ui_language)
            self.retranslate()
            self.reload_voices()

    def open_dicts(self) -> None:
        dialog = DictionaryEditorDialog(self.settings_obj.dictionary_paths, self)
        if dialog.exec():
            self.settings_obj.dictionary_paths = dialog.dictionary_paths
            save_settings(self.settings_obj)

    def _idle_controls(self) -> list:
        return [
            self.input_path,
            self.btn_input,
            self.output_path,
            self.btn_output,
            self.voice_combo,
            self.btn_create_voice,
            self.apply_dicts,
            self.btn_settings,
            self.btn_dicts,
            self.btn_start,
        ]

    def _set_synthesis_running(self, running: bool) -> None:
        for widget in self._idle_controls():
            widget.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def start(self) -> None:
        input_file = Path(self.input_path.text().strip())
        output_mp3 = Path(self.output_path.text().strip())
        if not input_file.is_file():
            QMessageBox.warning(self, t("main.error"), t("main.input_not_found"))
            return

        self.settings_obj.backend = normalize_backend(self.settings_obj)
        library_path = library_path_for_backend(self.settings_obj)
        if not library_path.is_file():
            QMessageBox.warning(
                self,
                t("main.error"),
                t("main.library_not_found", path=library_path),
            )
            return

        voice_name = None
        voice_dirs = None
        voice_id = self.selected_voice_id()
        if voice_id:
            try:
                resolve_voice_path(voice_id, *self.voice_dirs())
            except FileNotFoundError:
                QMessageBox.warning(
                    self,
                    t("main.error"),
                    t("main.voice_not_found", voice_id=voice_id),
                )
                return
            voice_name = voice_id
            voice_dirs = self.voice_dirs()

        text = input_file.read_text(encoding="utf-8")
        output_mp3.parent.mkdir(parents=True, exist_ok=True)
        wav_dir = output_mp3.with_suffix("").as_posix() + "_wav"

        self._set_synthesis_running(True)
        self.progress.setValue(0)
        self.log.clear()
        self.settings_obj.dictionaries_enabled = self.apply_dicts.isChecked()
        self.settings_obj.selected_voice_id = self.selected_voice_id()
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
            voice_name=voice_name,
            voice_dirs=voice_dirs,
        )
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.start()

    def stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.log.appendPlainText(t("main.stopping"))
            self.btn_stop.setEnabled(False)
            self.worker.request_cancel()

    def on_progress(self, idx: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(idx)
        self.log.appendPlainText(f"[{idx}/{total}]")

    def on_done(self, output: str) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText(t("main.done_log", output=output))
        QMessageBox.information(self, t("main.done"), t("main.mp3_created", path=output))

    def on_cancelled(self) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText(t("main.synthesis_stopped"))

    def on_failed(self, error: str) -> None:
        self._set_synthesis_running(False)
        self.log.appendPlainText(t("main.error_log", error=error))
        QMessageBox.critical(self, t("main.error"), error)
