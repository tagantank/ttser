from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from engine.pronunciation import Rule, load_rules, save_rules, validate_rules
from ttser.i18n import t, translate_dict_validation_error
from ttser.settings import user_dictionary_dir


class DictionaryEditorDialog(QDialog):
    def __init__(self, dictionary_paths: list[str], parent=None):
        super().__init__(parent)
        self.dictionary_paths = list(dictionary_paths)
        self._current_rules: list[Rule] = []
        self._dirty = False

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 1)
        root.addLayout(right, 3)
        self.resize(900, 520)

        self.lbl_connected = QLabel()
        self.list_widget = QListWidget()
        for path in self.dictionary_paths:
            self.list_widget.addItem(path)
        self.list_widget.currentRowChanged.connect(self._load_selected)
        left.addWidget(self.lbl_connected)
        left.addWidget(self.list_widget)

        self.btn_create_file = QPushButton()
        self.btn_create_file.clicked.connect(self._create_file)
        self.btn_add_file = QPushButton()
        self.btn_add_file.clicked.connect(self._add_file)
        self.btn_remove_file = QPushButton()
        self.btn_remove_file.clicked.connect(self._remove_file)
        left.addWidget(self.btn_create_file)
        left.addWidget(self.btn_add_file)
        left.addWidget(self.btn_remove_file)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["from", "to", "note"])
        self.table.itemChanged.connect(self._mark_dirty)
        right.addWidget(self.table)

        row_buttons = QHBoxLayout()
        self.btn_add_row = QPushButton()
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_delete_row = QPushButton()
        self.btn_delete_row.clicked.connect(self._delete_row)
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self._save_current)
        row_buttons.addWidget(self.btn_add_row)
        row_buttons.addWidget(self.btn_delete_row)
        row_buttons.addWidget(self.btn_save)
        right.addLayout(row_buttons)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        right.addWidget(self.button_box)

        self.retranslate()
        if self.dictionary_paths:
            self.list_widget.setCurrentRow(0)

    def retranslate(self) -> None:
        self.setWindowTitle(t("dict.title"))
        self.lbl_connected.setText(t("dict.connected"))
        self.btn_create_file.setText(t("dict.create"))
        self.btn_add_file.setText(t("dict.attach_json"))
        self.btn_remove_file.setText(t("dict.detach"))
        self.btn_add_row.setText(t("dict.add_row"))
        self.btn_delete_row.setText(t("dict.delete_row"))
        self.btn_save.setText(t("dict.save"))
        self.button_box.button(QDialogButtonBox.Ok).setText(t("dialog.ok"))
        self.button_box.button(QDialogButtonBox.Cancel).setText(t("dialog.cancel"))

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _create_file(self) -> None:
        if self._dirty and not self._confirm_discard():
            return
        dest_dir = user_dictionary_dir()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        suggested = dest_dir / "custom.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("dict.save_json"),
            str(suggested),
            "JSON (*.json)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        dest = Path(path)
        if dest.exists():
            answer = QMessageBox.question(
                self,
                t("dict.overwrite_title"),
                t("dict.overwrite_message", path=dest.name),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            save_rules(dest, [])
        except OSError as exc:
            QMessageBox.warning(self, t("main.error"), t("dict.create_failed", error=str(exc)))
            return
        self._dirty = False
        self._attach_path(str(dest))

    def _add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("dict.pick_json"), "", "JSON (*.json)")
        if not path:
            return
        self._attach_path(path)

    def _attach_path(self, path: str) -> None:
        if path not in self.dictionary_paths:
            self.dictionary_paths.append(path)
            self.list_widget.addItem(path)
        row = self.dictionary_paths.index(path)
        if self.list_widget.currentRow() == row:
            self._load_selected(row)
        else:
            self.list_widget.setCurrentRow(row)

    def _remove_file(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self.list_widget.takeItem(row)
        del self.dictionary_paths[row]
        self.table.setRowCount(0)

    def _load_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.dictionary_paths):
            return
        if self._dirty and not self._confirm_discard():
            return
        path = Path(self.dictionary_paths[row])
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self._current_rules = load_rules(path) if path.exists() else []
        for rule in self._current_rules:
            self._append_rule(rule)
        self.table.blockSignals(False)
        self._dirty = False

    def _append_rule(self, rule: Rule) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(rule.source))
        self.table.setItem(row, 1, QTableWidgetItem(rule.replacement))
        self.table.setItem(row, 2, QTableWidgetItem(rule.note))

    def _add_row(self) -> None:
        self._append_rule(Rule("", "", ""))
        self._dirty = True

    def _delete_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._dirty = True

    def _rules_from_table(self) -> list[Rule]:
        rules: list[Rule] = []
        for row in range(self.table.rowCount()):
            source = (self.table.item(row, 0).text() if self.table.item(row, 0) else "").strip()
            repl = (self.table.item(row, 1).text() if self.table.item(row, 1) else "").strip()
            note = (self.table.item(row, 2).text() if self.table.item(row, 2) else "").strip()
            rules.append(Rule(source, repl, note))
        return rules

    def _save_current(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        path = Path(self.dictionary_paths[row])
        rules = self._rules_from_table()
        errors = validate_rules(rules)
        if errors:
            translated = [translate_dict_validation_error(error) for error in errors]
            QMessageBox.warning(self, t("dict.validation_error"), "\n".join(translated))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        save_rules(path, rules)
        self._dirty = False

    def _confirm_discard(self) -> bool:
        return (
            QMessageBox.question(
                self,
                t("dict.unsaved_title"),
                t("dict.unsaved_message"),
            )
            == QMessageBox.StandardButton.Yes
        )
