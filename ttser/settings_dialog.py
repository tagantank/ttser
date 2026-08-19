from __future__ import annotations

import platform
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
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
from ttser.model_catalog import MODELS, find_downloaded_model, model_by_id, model_destination
from ttser.model_download_worker import ModelDownloadWorker
from ttser.settings import AppSettings, default_models_dir, model_lookup_dirs

PROGRESS_MAX = 1000


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(720, 520)
        self.settings = settings
        self.download_worker: ModelDownloadWorker | None = None
        self._available_backends = available_backends(settings)
        self.lib_fields: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)

        model_box = QGroupBox("Модель Fish Audio S2 Pro")
        model_layout = QVBoxLayout(model_box)

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

        model_form.addRow("Вариант", self.model_choice)
        model_form.addRow("Описание", self.model_description)
        model_form.addRow("Каталог моделей", models_dir_row)
        model_form.addRow("Путь к модели", self.model_path)
        model_layout.addLayout(model_form)

        download_row = QHBoxLayout()
        self.btn_download = QPushButton("Скачать модель")
        self.btn_download.clicked.connect(self.start_download)
        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        download_row.addWidget(self.btn_download)
        download_row.addWidget(self.download_progress, 1)
        model_layout.addLayout(download_row)

        layout.addWidget(model_box)

        runtime_box = QGroupBox("Runtime")
        self.runtime_form = QFormLayout(runtime_box)

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
        self.gpu_device_label = QLabel("GPU device")
        self.runtime_form.addRow(self.gpu_device_label, self.gpu_device_row)
        self.runtime_form.addRow("Threads", self.threads)
        self.runtime_form.addRow("Tokenizer", self.tokenizer_path)
        self.runtime_form.addRow("Voice dir", self.voice_dir)

        for backend in self._available_backends:
            field = QLineEdit(str(resolve_library_path(settings, backend.lib_attr)))
            self.lib_fields[backend.id] = field
            self.runtime_form.addRow(f"lib {backend.id}", field)

        layout.addWidget(runtime_box)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self.on_model_changed()
        self.on_backend_changed()

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

    def accept(self) -> None:
        self._stop_download()
        super().accept()

    def reject(self) -> None:
        self._stop_download()
        super().reject()

    def closeEvent(self, event: QEvent) -> None:
        self._stop_download()
        super().closeEvent(event)

    def selected_model(self):
        model_id = self.model_choice.currentData()
        return model_by_id(model_id) or MODELS[1]

    def on_model_changed(self) -> None:
        model = self.selected_model()
        self.model_description.setText(f"{model.description} Размер: {model.size}.")
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
                self.gpu_device_label.setText("CUDA device")
            elif backend.id == "vulkan":
                self.gpu_device_label.setText("Vulkan device")
            elif backend.id == "metal":
                self.gpu_device_label.setText("Metal device")
            else:
                self.gpu_device_label.setText("GPU device")

    def selected_models_dir(self) -> str:
        return self.models_dir.text().strip() or default_models_dir()

    def update_download_button(self) -> None:
        if self.is_downloading():
            self.btn_download.setEnabled(False)
            self.btn_download.setText("Скачать модель")
            return
        model = self.selected_model()
        found = find_downloaded_model(
            model,
            self.model_path.text().strip(),
            *model_lookup_dirs(self.selected_models_dir()),
        )
        self.btn_download.setEnabled(found is None)
        self.btn_download.setText("Модель уже скачана" if found else "Скачать модель")
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
        path = QFileDialog.getExistingDirectory(self, "Каталог для моделей", self.models_dir.text())
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
        self.download_progress.setFormat("Определение размера...")
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
        self.download_progress.setFormat("Готово")
        self.model_path.setText(path)
        self.set_download_ui_enabled(True)
        self.update_download_button()
        QMessageBox.information(self, "Готово", f"Модель скачана:\n{path}")

    def on_download_failed(self, error: str) -> None:
        self.download_progress.setVisible(False)
        self.set_download_ui_enabled(True)
        self.update_download_button()
        QMessageBox.critical(self, "Ошибка скачивания", error)

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
        )
        for backend in self._available_backends:
            field = self.lib_fields.get(backend.id)
            if field is not None:
                setattr(result, backend.lib_attr, field.text().strip())
        return result
