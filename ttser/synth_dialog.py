from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ttser.i18n import t
from ttser.settings import AppSettings, effective_codec_follow_backend
from ttser.synth_params import (
    SynthParamSpec,
    params_for_backend,
    synthesis_defaults,
)


class SynthesisParamsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.backend = settings.backend
        self._widgets: dict[str, QWidget] = {}
        self._help_buttons: dict[str, QToolButton] = {}
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        self.backend_hint = QLabel()
        layout.addWidget(self.backend_hint)

        self.form = QFormLayout()
        for spec in params_for_backend(self.backend):
            self._add_param_row(spec)
        layout.addLayout(self.form)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        buttons.addWidget(self.btn_reset)
        buttons.addStretch(1)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        buttons.addWidget(self.button_box)
        layout.addLayout(buttons)

        self._load_from_settings(settings)
        self.retranslate()

    def _add_param_row(self, spec: SynthParamSpec) -> None:
        widget = self._make_widget(spec)
        self._widgets[spec.id] = widget
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setAutoRaise(True)
        help_btn.clicked.connect(
            lambda _checked=False, param_id=spec.id: self._show_help(param_id)
        )
        self._help_buttons[spec.id] = help_btn
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(widget, 1)
        row_layout.addWidget(help_btn)
        label = QLabel()
        label.setObjectName(f"label_{spec.id}")
        self.form.addRow(label, row)

    def _make_widget(self, spec: SynthParamSpec) -> QWidget:
        if spec.kind == "int":
            widget = QSpinBox()
            widget.setRange(int(spec.minimum or 0), int(spec.maximum or 100))
            return widget
        if spec.kind == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(spec.decimals)
            widget.setSingleStep(0.05)
            widget.setRange(float(spec.minimum or 0.0), float(spec.maximum or 1.0))
            return widget
        if spec.kind == "bool":
            return QCheckBox()
        if spec.kind == "choice":
            widget = QComboBox()
            for choice in spec.choices:
                widget.addItem(choice, choice)
            return widget
        if spec.kind == "codec":
            widget = QComboBox()
            widget.addItem("", 0)
            if self.backend != "vulkan":
                widget.addItem("", 1)
            return widget
        raise ValueError(f"unsupported synth param kind: {spec.kind}")

    def _label_for(self, param_id: str) -> QLabel | None:
        for i in range(self.form.rowCount()):
            item = self.form.itemAt(i, QFormLayout.LabelRole)
            if item is None:
                continue
            label = item.widget()
            if isinstance(label, QLabel) and label.objectName() == f"label_{param_id}":
                return label
        return None

    def retranslate(self) -> None:
        self.setWindowTitle(t("synth.title"))
        self.backend_hint.setText(t("synth.backend_hint", backend=self.backend.upper()))
        self.btn_reset.setText(t("synth.reset"))
        self.button_box.button(QDialogButtonBox.Ok).setText(t("synth.start"))
        self.button_box.button(QDialogButtonBox.Cancel).setText(t("dialog.cancel"))
        for param_id in self._widgets:
            label = self._label_for(param_id)
            if label is not None:
                label.setText(t(f"synth.param.{param_id}.label"))
        log_widget = self._widgets.get("log_level")
        if isinstance(log_widget, QComboBox):
            for i in range(log_widget.count()):
                key = log_widget.itemData(i)
                log_widget.setItemText(i, t(f"synth.log.{key}"))
        codec_widget = self._widgets.get("codec_follow_backend")
        if isinstance(codec_widget, QComboBox):
            codec_widget.setItemText(0, t("synth.codec_cpu"))
            codec_widget.setItemText(1, t("synth.codec_gpu"))

    def _show_help(self, param_id: str) -> None:
        QMessageBox.information(
            self,
            t(f"synth.param.{param_id}.label"),
            t(f"synth.param.{param_id}.help"),
        )

    def _set_value(self, param_id: str, value: object) -> None:
        widget = self._widgets.get(param_id)
        if widget is None:
            return
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            idx = widget.findData(value)
            if idx < 0 and param_id == "log_level":
                idx = widget.findData(str(value))
            if idx < 0 and param_id == "codec_follow_backend":
                idx = widget.findData(1 if value else 0)
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def _get_value(self, param_id: str) -> object | None:
        widget = self._widgets.get(param_id)
        if widget is None:
            return None
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentData()
        return None

    def _load_from_settings(self, settings: AppSettings) -> None:
        values = {
            "max_new_tokens": settings.max_new_tokens,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "top_k": settings.top_k,
            "min_tokens_before_end": settings.min_tokens_before_end,
            "line_pause_ms": settings.line_pause_ms,
            "threads": settings.threads,
            "log_level": settings.log_level,
            "verbose": settings.verbose,
            "n_gpu_layers": settings.n_gpu_layers,
            "gpu_device": settings.vulkan_device,
            "codec_follow_backend": effective_codec_follow_backend(settings),
        }
        for param_id, value in values.items():
            self._set_value(param_id, value)

    def reset_to_defaults(self) -> None:
        defaults = synthesis_defaults(self.backend)
        for param_id in self._widgets:
            self._set_value(param_id, defaults[param_id])

    def apply_to_settings(self, settings: AppSettings) -> AppSettings:
        """Mutate settings with visible dialog fields only; leave hidden ones intact."""
        for param_id in self._widgets:
            value = self._get_value(param_id)
            if value is None:
                continue
            if param_id == "gpu_device":
                settings.vulkan_device = int(value)
            elif param_id == "codec_follow_backend":
                settings.codec_follow_backend = 1 if value else 0
            elif param_id == "log_level":
                settings.log_level = str(value)
            elif param_id == "verbose":
                settings.verbose = bool(value)
            elif param_id == "temperature":
                settings.temperature = float(value)
            elif param_id == "top_p":
                settings.top_p = float(value)
            elif hasattr(settings, param_id):
                current = getattr(settings, param_id)
                if isinstance(current, bool):
                    setattr(settings, param_id, bool(value))
                elif isinstance(current, float):
                    setattr(settings, param_id, float(value))
                else:
                    setattr(settings, param_id, int(value))
        return settings
