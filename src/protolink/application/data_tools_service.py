from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from protolink.core.data_tools import hex_modbus_crc16, hex_to_utf8, pretty_json, utf8_to_base64, utf8_to_hex


class DataToolMode(StrEnum):
    UTF8_TO_HEX = "utf8_to_hex"
    HEX_TO_UTF8 = "hex_to_utf8"
    HEX_MODBUS_CRC16 = "hex_modbus_crc16"
    PRETTY_JSON = "pretty_json"
    UTF8_TO_BASE64 = "utf8_to_base64"


@dataclass(frozen=True, slots=True)
class DataToolsSnapshot:
    selected_mode: DataToolMode = DataToolMode.UTF8_TO_HEX
    input_text: str = ""
    output_text: str = ""
    execution_count: int = 0
    last_error: str | None = None


class DataToolsService:
    def __init__(self) -> None:
        self._snapshot = DataToolsSnapshot()
        self._listeners: list[Callable[[DataToolsSnapshot], None]] = []

    @property
    def snapshot(self) -> DataToolsSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[DataToolsSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_mode(self, mode: DataToolMode | str) -> None:
        if not isinstance(mode, DataToolMode):
            mode = DataToolMode(str(mode))
        self._set_snapshot(selected_mode=mode)

    def set_input_text(self, text: str) -> None:
        self._set_snapshot(input_text=text)

    def run(self) -> str | None:
        text = self._snapshot.input_text
        if not text.strip():
            self._set_snapshot(last_error="运行数据工具前请输入待处理文本。")
            return None

        try:
            output = self._run_mode(self._snapshot.selected_mode, text)
        except Exception as exc:
            self._set_snapshot(last_error=str(exc))
            return None

        self._set_snapshot(
            output_text=output,
            execution_count=self._snapshot.execution_count + 1,
            last_error=None,
        )
        return output

    def _run_mode(self, mode: DataToolMode, text: str) -> str:
        if mode == DataToolMode.UTF8_TO_HEX:
            return utf8_to_hex(text)
        if mode == DataToolMode.HEX_TO_UTF8:
            return hex_to_utf8(text)
        if mode == DataToolMode.HEX_MODBUS_CRC16:
            return hex_modbus_crc16(text)
        if mode == DataToolMode.PRETTY_JSON:
            return pretty_json(text)
        if mode == DataToolMode.UTF8_TO_BASE64:
            return utf8_to_base64(text)
        raise ValueError(f"Unsupported data tool mode: {mode}")

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)
