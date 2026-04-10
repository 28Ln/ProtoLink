from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal


class QtCallbackDispatcher(QObject):
    callback_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.callback_requested.connect(self._execute, Qt.ConnectionType.QueuedConnection)

    def dispatch(self, callback: Callable[[], None]) -> None:
        self.callback_requested.emit(callback)

    def _execute(self, callback: Callable[[], None]) -> None:
        callback()
