from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from protolink.application.script_console_service import ScriptConsoleService, ScriptConsoleSnapshot
from protolink.core.script_host import ScriptLanguage


class ScriptConsolePanel(QWidget):
    def __init__(self, service: ScriptConsoleService) -> None:
        super().__init__()
        self.service = service
        self._syncing = False
        self._build_ui()
        self.service.subscribe(self.refresh)
        self.refresh(self.service.snapshot)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame = QFrame()
        frame.setObjectName("Panel")
        grid = QGridLayout(frame)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        title = QLabel("Script Console")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("MetaLabel")
        self.notice_label = QLabel(
            "Controlled execution only. Scripts are bounded by the script host and saved into the workspace."
        )
        self.notice_label.setObjectName("MetaLabel")
        self.notice_label.setWordWrap(True)
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.1, 30.0)
        self.timeout_spin.setSingleStep(0.1)
        self.timeout_spin.valueChanged.connect(self.service.set_timeout_seconds)
        self.context_input = QLineEdit()
        self.context_input.setPlaceholderText('JSON context, e.g. {"value": 21}')
        self.context_input.textChanged.connect(self.service.set_context_text)
        self.code_input = QTextEdit()
        self.code_input.textChanged.connect(self._on_code_changed)
        self.run_button = QPushButton("Run Script")
        self.run_button.clicked.connect(self.service.run_script)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.result_label = QLabel()
        self.result_label.setObjectName("MetaLabel")
        self.script_file_label = QLabel()
        self.script_file_label.setObjectName("MetaLabel")
        self.error_label = QLabel()
        self.error_label.setObjectName("MetaLabel")
        self.error_label.setWordWrap(True)

        grid.addWidget(title, 0, 0, 1, 2)
        grid.addWidget(self.status_label, 0, 2, 1, 2)
        grid.addWidget(self.notice_label, 1, 0, 1, 4)
        grid.addWidget(QLabel("Language"), 2, 0)
        grid.addWidget(self.language_combo, 2, 1)
        grid.addWidget(QLabel("Timeout (s)"), 2, 2)
        grid.addWidget(self.timeout_spin, 2, 3)
        grid.addWidget(QLabel("Context"), 3, 0)
        grid.addWidget(self.context_input, 3, 1, 1, 3)
        grid.addWidget(QLabel("Code"), 4, 0)
        grid.addWidget(self.code_input, 4, 1, 1, 3)
        grid.addWidget(self.run_button, 5, 3)
        grid.addWidget(QLabel("Output"), 6, 0)
        grid.addWidget(self.output_text, 6, 1, 1, 3)
        grid.addWidget(QLabel("Result"), 7, 0)
        grid.addWidget(self.result_label, 7, 1, 1, 3)
        grid.addWidget(QLabel("Saved Script"), 8, 0)
        grid.addWidget(self.script_file_label, 8, 1, 1, 3)
        grid.addWidget(QLabel("Error"), 9, 0)
        grid.addWidget(self.error_label, 9, 1, 1, 3)

        layout.addWidget(frame)

    def refresh(self, snapshot: ScriptConsoleSnapshot) -> None:
        self._syncing = True
        try:
            self._rebuild_languages(snapshot)
            self.timeout_spin.setValue(snapshot.timeout_seconds)
            if self.context_input.text() != snapshot.context_text:
                self.context_input.setText(snapshot.context_text)
            if self.code_input.toPlainText() != snapshot.code:
                self.code_input.setPlainText(snapshot.code)
        finally:
            self._syncing = False

        self.status_label.setText(
            f"Runs: {snapshot.execution_count}    Language: {(snapshot.selected_language.value if snapshot.selected_language else '-')}"
        )
        self.output_text.setPlainText(snapshot.last_output)
        self.result_label.setText(snapshot.last_result_text or "-")
        self.script_file_label.setText(snapshot.last_script_file or "-")
        self.error_label.setText(snapshot.last_error or "Ready.")
        self.run_button.setEnabled(snapshot.selected_language is not None and bool(snapshot.code.strip()))

    def _rebuild_languages(self, snapshot: ScriptConsoleSnapshot) -> None:
        current = [self.language_combo.itemData(index) for index in range(self.language_combo.count())]
        desired = [language for language in snapshot.available_languages]
        if current != desired:
            self.language_combo.blockSignals(True)
            self.language_combo.clear()
            for language in snapshot.available_languages:
                self.language_combo.addItem(language.value, language)
            self.language_combo.blockSignals(False)
        if snapshot.selected_language is not None:
            index = self.language_combo.findData(snapshot.selected_language)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)

    def _on_language_changed(self) -> None:
        if self._syncing:
            return
        value = self.language_combo.currentData()
        if value is None:
            return
        if not isinstance(value, ScriptLanguage):
            value = ScriptLanguage(str(value))
        self.service.set_language(value)

    def _on_code_changed(self) -> None:
        if self._syncing:
            return
        self.service.set_code(self.code_input.toPlainText())
