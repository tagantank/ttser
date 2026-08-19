from __future__ import annotations

import platform
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ttser.backends import available_backends, backend_by_id, resolve_library_path
from ttser.i18n import LANGUAGES, apply_language, model_description, model_size_label, t
from ttser.model_catalog import MODELS, find_downloaded_model, model_by_id, model_destination
from ttser.model_download_worker import ModelDownloadWorker
from ttser.settings import AppSettings, default_models_dir, model_lookup_dirs

PROGRESS_MAX = 1000


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._saved_language = settings.ui_language
        self.download_worker: ModelDownloadWorker | None = None
        self._available_backends = available_backends(settings)
        self.lib_fields: dict[str, QLineEdit] = {}
        self._form_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        self.resize(720, 560)

        self.interface_box = QGroupBox()
        interface_form = QFormLayout(self.interface_box)
        self.language_choice = QComboBox()
        for code, label in LANGUAGES:
            self.language_choice.addItem(label, code)
        lang_idx = max(0, self.language_choice.findData(settings.ui_language))
        self.language_choice.blockSignals(True)
        self.language_choice.setCurrentIndex(lang_idx)
        self.language_choice.blockSignals(False)
        self.language_choice.currentIndexChanged.connect(self.on_language_changed)
        self._form_labels["language"] = QLabel()
        interface_form.addRow(self._form_labels["language"], self.language_choice)
        layout.addWidget(self.interface_box)

        self.model_box = QGroupBox()
        model_layout = QVBoxLayout(self.model_box)

        model_form = QFormLayout()
        self.model_choice = QComboBox()
        for model in MODELS:
            self.model_choice.addItem(model.combo_label, model.id)
        selected_idx = max(0, self.model_choice.findData(settings.selected_model_id))
        self.model_choice.setCurrentIndex(selected_idx)
        self.model_choice.currentIndexChanged.connect(self.on_model_changed)

        self.model_description = QLabel()
        self.model_description.setWordWrap(True)
        self.model_description.setStyleSheet("color: palette(mid);")

        self.models_dir = QLineEdit(settings.models_dir or default_models_dir())
        self.models_dir.textChanged.connect(self.on_model_changed)
        btn_models_dir = QPushButton("...")
        btn_models_dir.clicked.connect(self.pick_models_dir)
        models_dir_row = QHBoxLayout()
        models_dir_row.addWidget(self.models_dir, 1)
        models_dir_row.addWidget(btn_models_dir)

        self.model_path = QLineEdit(settings.model_path)

        self._form_labels["variant"] = QLabel()
        model_form.addRow(self._form_labels["variant"], self.model_choice)
        self._form_labels["description"] = QLabel()
        model_form.addRow(self._form_labels["description"], self.model_description)
        self._form_labels["models_dir"] = QLabel()
        model_form.addRow(self._form_labels["models_dir"], models_dir_row)
        self._form_labels["model_path"] = QLabel()
        model_form.addRow(self._form_labels["model_path"], self.model_path)
        model_layout.addLayout(model_form)

        download_row = QHBoxLayout()
        self.btn_download = QPushButton()
        self.btn_download.clicked.connect(self.start_download)
        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        download_row.addWidget(self.btn_download)
        download_row.addWidget(self.download_progress, 1)
        model_layout.addLayout(download_row)

        layout.addWidget(self.model_box)

        self.runtime_box = QGroupBox("Runtime")
        self.runtime_form = QFormLayout(self.runtime_box)

        self.backend = QComboBox()
        for backend in self._available_backends:
            self.backend.addItem(backend.label, backend.id)
        backend_idx = max(0, self.backend.findData(settings.backend))
        self.backend.setCurrentIndex(backend_idx)
        self.backend.currentIndexChanged.connect(self.on_backend_changed)

        self.gpu_device = QSpinBox()
        self.gpu_device.setRange(0, 16)
        self.gpu_device.setValue(settings.vulkan_device)
        self.gpu_device_row = QWidget()
        gpu_row_layout = QHBoxLayout(self.gpu_device_row)
        gpu_row_layout.setContentsMargins(0, 0, 0, 0)
        gpu_row_layout.addWidget(self.gpu_device)

        self.threads = QSpinBox()
        self.threads.setRange(1, 64)
        self.threads.setValue(settings.threads)

        self.tokenizer_path = QLineEdit(settings.tokenizer_path)
        self.voice_dir = QLineEdit(settings.voice_dir)

        self.runtime_form.addRow("Backend", self.backend)
        self.gpu_device_label = QLabel()
        self.runtime_form.addRow(self.gpu_device_label, self.gpu_device_row)
        self.runtime_form.addRow("Threads", self.threads)
        self.runtime_form.addRow("Tokenizer", self.tokenizer_path)
        self.runtime_form.addRow("Voice dir", self.voice_dir)

        for backend in self._available_backends:
            field = QLineEdit(str(resolve_library_path(settings, backend.lib_attr)))
            self.lib_fields[backend.id] = field
            self.runtime_form.addRow(f"lib {backend.id}", field)

        layout.addWidget(self.runtime_box)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.retranslate()
        self.on_model_changed()
        self.on_backend_changed()

    def retranslate(self) -> None:
        self.setWindowTitle(t("settings.title"))
        self.interface_box.setTitle(t("settings.interface"))
        self._form_labels["language"].setText(t("settings.language"))
        self.model_box.setTitle(t("settings.model_group"))
        self._form_labels["variant"].setText(t("settings.variant"))
        self._form_labels["description"].setText(t("settings.description"))
        self._form_labels["models_dir"].setText(t("settings.models_dir"))
        self._form_labels["model_path"].setText(t("settings.model_path"))
        self.button_box.button(QDialogButtonBox.Ok).setText(t("dialog.ok"))
        self.button_box.button(QDialogButtonBox.Cancel).setText(t("dialog.cancel"))
        self._refresh_model_combo_labels()
        self.on_model_changed()
        self.on_backend_changed()
        self.update_download_button()

    def _refresh_model_combo_labels(self) -> None:
        current_id = self.model_choice.currentData()
        self.model_choice.blockSignals(True)
        self.model_choice.clear()
        for model in MODELS:
            self.model_choice.addItem(model.combo_label, model.id)
        idx = max(0, self.model_choice.findData(current_id))
        self.model_choice.setCurrentIndex(idx)
        self.model_choice.blockSignals(False)

    def on_language_changed(self) -> None:
        code = self.language_choice.currentData()
        app = QApplication.instance()
        if app is not None:
            apply_language(app, code)
        self.retranslate()
        parent = self.parent()
        if parent is not None and hasattr(parent, "retranslate"):
            parent.retranslate()

    def is_downloading(self) -> bool:
        return self.download_worker is not None and self.download_worker.isRunning()

    def _stop_download(self) -> None:
        worker = self.download_worker
        if worker is None:
            return
        try:
            worker.progress.disconnect(self.on_download_progress)
            worker.done.disconnect(self.on_download_done)
            worker.failed.disconnect(self.on_download_failed)
        except RuntimeError:
            pass
        if worker.isRunning():
            worker.request_cancel()
            worker.finished.connect(worker.deleteLater)
        self.download_worker = None
        self.download_progress.setVisible(False)
        self.update_download_button()

    def _restore_saved_language(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_language(app, self._saved_language)
        parent = self.parent()
        if parent is not None and hasattr(parent, "retranslate"):
            parent.retranslate()

    def accept(self) -> None:
        self._stop_download()
        super().accept()

    def reject(self) -> None:
        self._stop_download()
        self._restore_saved_language()
        super().reject()

    def closeEvent(self, event: QEvent) -> None:
        self._stop_download()
        super().closeEvent(event)

    def selected_model(self):
        model_id = self.model_choice.currentData()
        return model_by_id(model_id) or MODELS[1]

    def on_model_changed(self) -> None:
        model = self.selected_model()
        description = model_description(model.id)
        size = model_size_label(model.id)
        self.model_description.setText(f"{description} {t('settings.size_label', size=size)}")
        models_dir = Path(self.models_dir.text().strip() or default_models_dir())
        self.model_path.setText(str(models_dir / model.filename))
        self.update_download_button()

    def on_backend_changed(self) -> None:
        backend = backend_by_id(self.backend.currentData())
        uses_gpu = backend.uses_gpu_device() if backend else False
        self.gpu_device_label.setVisible(uses_gpu)
        self.gpu_device_row.setVisible(uses_gpu)
        if backend:
            if backend.id == "cuda":
                self.gpu_device_label.setText(t("settings.cuda_device"))
            elif backend.id == "vulkan":
                self.gpu_device_label.setText(t("settings.vulkan_device"))
            elif backend.id == "metal":
                self.gpu_device_label.setText(t("settings.metal_device"))
            else:
                self.gpu_device_label.setText(t("settings.gpu_device"))

    def selected_models_dir(self) -> str:
        return self.models_dir.text().strip() or default_models_dir()

    def update_download_button(self) -> None:
        if self.is_downloading():
            self.btn_download.setEnabled(False)
            self.btn_download.setText(t("settings.download"))
            return
        model = self.selected_model()
        found = find_downloaded_model(
            model,
            self.model_path.text().strip(),
            *model_lookup_dirs(self.selected_models_dir()),
        )
        self.btn_download.setEnabled(found is None)
        self.btn_download.setText(
            t("settings.already_downloaded") if found else t("settings.download")
        )
        if found is None:
            return
        parent = str(found.parent)
        if self.models_dir.text().strip() != parent:
            self.models_dir.blockSignals(True)
            self.models_dir.setText(parent)
            self.models_dir.blockSignals(False)
        if self.model_path.text().strip() != str(found):
            self.model_path.setText(str(found))

    def pick_models_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, t("settings.pick_models_dir"), self.models_dir.text()
        )
        if path:
            self.models_dir.setText(path)

    def set_download_ui_enabled(self, enabled: bool) -> None:
        self.model_choice.setEnabled(enabled)
        self.models_dir.setEnabled(enabled)
        if enabled:
            self.update_download_button()
        else:
            self.btn_download.setEnabled(False)

    def start_download(self) -> None:
        model = self.selected_model()
        destination = model_destination(self.selected_models_dir(), model)
        if find_downloaded_model(model, destination, *model_lookup_dirs(self.selected_models_dir())):
            self.update_download_button()
            return

        self.download_progress.setVisible(True)
        self.download_progress.setRange(0, PROGRESS_MAX)
        self.download_progress.setValue(0)
        self.download_progress.setFormat(t("settings.resolving_size"))
        self.set_download_ui_enabled(False)

        self.download_worker = ModelDownloadWorker(model, destination)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.done.connect(self.on_download_done)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()

    def on_download_progress(self, percent: int, label: str) -> None:
        if label.endswith("..."):
            self.download_progress.setRange(0, 0)
            self.download_progress.setFormat(label)
            return

        self.download_progress.setRange(0, PROGRESS_MAX)
        self.download_progress.setValue(percent)
        self.download_progress.setFormat(label)

    def on_download_done(self, path: str) -> None:
        self.download_progress.setRange(0, PROGRESS_MAX)
        self.download_progress.setValue(PROGRESS_MAX)
        self.download_progress.setFormat(t("settings.download_done"))
        self.model_path.setText(path)
        self.set_download_ui_enabled(True)
        self.update_download_button()
        QMessageBox.information(
            self, t("settings.download_done"), t("settings.model_downloaded", path=path)
        )

    def on_download_failed(self, error: str) -> None:
        self.download_progress.setVisible(False)
        self.set_download_ui_enabled(True)
        self.update_download_button()
        QMessageBox.critical(self, t("settings.download_error"), error)

    def to_settings(self) -> AppSettings:
        model = self.selected_model()
        models_dir = self.models_dir.text().strip() or default_models_dir()
        model_path = self.model_path.text().strip() or str(Path(models_dir) / model.filename)
        result = AppSettings(
            backend=self.backend.currentData(),
            vulkan_device=self.gpu_device.value(),
            threads=self.threads.value(),
            model_path=model_path,
            models_dir=models_dir,
            selected_model_id=model.id,
            tokenizer_path=self.tokenizer_path.text().strip(),
            voice_dir=self.voice_dir.text().strip(),
            lib_cpu=self.settings.lib_cpu,
            lib_vulkan=self.settings.lib_vulkan,
            lib_cuda=self.settings.lib_cuda,
            lib_metal=self.settings.lib_metal,
            dictionary_paths=self.settings.dictionary_paths,
            dictionaries_enabled=self.settings.dictionaries_enabled,
            selected_voice_id=self.settings.selected_voice_id,
            ui_language=self.language_choice.currentData(),
        )
        for backend in self._available_backends:
            field = self.lib_fields.get(backend.id)
            if field is not None:
                setattr(result, backend.lib_attr, field.text().strip())
        return result
