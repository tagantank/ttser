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


class DictionaryEditorDialog(QDialog):
    def __init__(self, dictionary_paths: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Словари")
        self.resize(900, 520)
        self.dictionary_paths = list(dictionary_paths)
        self._current_rules: list[Rule] = []
        self._dirty = False

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 1)
        root.addLayout(right, 3)

        self.list_widget = QListWidget()
        for path in self.dictionary_paths:
            self.list_widget.addItem(path)
        self.list_widget.currentRowChanged.connect(self._load_selected)
        left.addWidget(QLabel("Подключенные словари"))
        left.addWidget(self.list_widget)

        btn_add_file = QPushButton("Подключить JSON")
        btn_add_file.clicked.connect(self._add_file)
        btn_remove_file = QPushButton("Отключить")
        btn_remove_file.clicked.connect(self._remove_file)
        left.addWidget(btn_add_file)
        left.addWidget(btn_remove_file)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["from", "to", "note"])
        self.table.itemChanged.connect(self._mark_dirty)
        right.addWidget(self.table)

        row_buttons = QHBoxLayout()
        for text, handler in [
            ("Добавить строку", self._add_row),
            ("Удалить строку", self._delete_row),
            ("Сохранить", self._save_current),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            row_buttons.addWidget(btn)
        right.addLayout(row_buttons)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        right.addWidget(box)
        if self.dictionary_paths:
            self.list_widget.setCurrentRow(0)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать JSON словарь", "", "JSON (*.json)")
        if not path:
            return
        if path not in self.dictionary_paths:
            self.dictionary_paths.append(path)
            self.list_widget.addItem(path)
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)

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
            QMessageBox.warning(self, "Ошибка словаря", "\n".join(errors))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        save_rules(path, rules)
        self._dirty = False

    def _confirm_discard(self) -> bool:
        return QMessageBox.question(
            self,
            "Несохраненные правки",
            "Есть несохраненные изменения. Продолжить без сохранения?",
        ) == QMessageBox.StandardButton.Yes

