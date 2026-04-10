from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from protolink.core.event_bus import EventBus
from protolink.core.logging import StructuredLogEntry
from protolink.core.modbus_rtu_parser import ModbusRtuFrameKind, parse_modbus_rtu_frame
from protolink.core.modbus_tcp_parser import ModbusTcpFrameKind, parse_modbus_tcp_frame
from protolink.core.register_monitor import RegisterByteOrder, RegisterDataType, RegisterPoint, decode_register_point


@dataclass(frozen=True, slots=True)
class RegisterMonitorSnapshot:
    point_names: tuple[str, ...] = ()
    selected_point_name: str | None = None
    register_words_text: str = ""
    decoded_value: str = ""
    last_live_source: str | None = None
    last_error: str | None = None


class RegisterMonitorService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._points_by_name: dict[str, RegisterPoint] = {}
        self._snapshot = RegisterMonitorSnapshot()
        self._listeners: list[Callable[[RegisterMonitorSnapshot], None]] = []
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._event_bus.subscribe(StructuredLogEntry, self._on_log_entry)

    @property
    def snapshot(self) -> RegisterMonitorSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[RegisterMonitorSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def upsert_point(
        self,
        *,
        name: str,
        address: int | str,
        data_type: RegisterDataType,
        byte_order: RegisterByteOrder,
        scale: float | str,
        offset: float | str,
        unit: str = "",
    ) -> None:
        normalized = " ".join(name.strip().split())
        if not normalized:
            self._set_snapshot(last_error="Point name is required.")
            return

        try:
            address_value = int(str(address).strip())
        except ValueError:
            self._set_snapshot(last_error="Address must be an integer.")
            return
        if address_value < 0:
            self._set_snapshot(last_error="Address must be zero or positive.")
            return

        try:
            scale_value = float(str(scale).strip())
            offset_value = float(str(offset).strip())
        except ValueError:
            self._set_snapshot(last_error="Scale and offset must be numeric values.")
            return

        self._points_by_name[normalized] = RegisterPoint(
            name=normalized,
            address=address_value,
            data_type=data_type,
            byte_order=byte_order,
            scale=scale_value,
            offset=offset_value,
            unit=unit.strip(),
        )
        self._set_snapshot(
            point_names=tuple(sorted(self._points_by_name)),
            selected_point_name=normalized,
            last_live_source=None,
            last_error=None,
        )

    def remove_point(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(last_error="Select a point before removing.")
            return
        removed = self._points_by_name.pop(name, None)
        if removed is None:
            self._set_snapshot(last_error=f"Point '{name}' was not found.")
            return

        selected = self._snapshot.selected_point_name
        if selected == name:
            selected = None
        self._set_snapshot(
            point_names=tuple(sorted(self._points_by_name)),
            selected_point_name=selected,
            decoded_value="" if selected is None else self._snapshot.decoded_value,
            last_live_source=None if selected is None else self._snapshot.last_live_source,
            last_error=None,
        )

    def select_point(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(selected_point_name=None, decoded_value="", last_live_source=None, last_error=None)
            return
        if name not in self._points_by_name:
            self._set_snapshot(last_error=f"Point '{name}' was not found.")
            return
        self._set_snapshot(selected_point_name=name, last_live_source=None, last_error=None)

    def set_register_words_text(self, text: str) -> None:
        self._set_snapshot(register_words_text=text)

    def decode_current_words(self) -> None:
        point = self._selected_point()
        if point is None:
            self._set_snapshot(last_error="Select a point before decoding.")
            return

        try:
            registers = self._parse_register_words(self._snapshot.register_words_text)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        try:
            decoded = decode_register_point(point, registers)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        value_text = str(decoded)
        if point.unit:
            value_text = f"{value_text} {point.unit}"
        self._set_snapshot(decoded_value=value_text, last_live_source="manual", last_error=None)

    def _on_log_entry(self, entry: StructuredLogEntry) -> None:
        point = self._selected_point()
        if point is None:
            return
        if entry.category != "transport.message" or not entry.raw_payload:
            return
        if not entry.message.lower().startswith("inbound "):
            return

        live_registers, source_label = self._extract_live_registers(entry.raw_payload)
        if live_registers is None:
            return
        try:
            decoded = decode_register_point(point, live_registers)
        except ValueError:
            return

        value_text = str(decoded)
        if point.unit:
            value_text = f"{value_text} {point.unit}"
        self._set_snapshot(decoded_value=value_text, last_live_source=source_label, last_error=None)

    def _selected_point(self) -> RegisterPoint | None:
        selected = self._snapshot.selected_point_name
        if not selected:
            return None
        return self._points_by_name.get(selected)

    def _parse_register_words(self, text: str) -> tuple[int, ...]:
        tokens = [token for token in text.replace(",", " ").split() if token]
        if not tokens:
            raise ValueError("Enter at least one register word.")
        values: list[int] = []
        for token in tokens:
            base = 16 if token.lower().startswith("0x") or any(char in token.lower() for char in "abcdef") else 10
            try:
                value = int(token, base)
            except ValueError as exc:
                raise ValueError(f"Invalid register word '{token}'.") from exc
            if not 0 <= value <= 0xFFFF:
                raise ValueError("Register words must be between 0 and 65535.")
            values.append(value)
        return tuple(values)

    def _extract_live_registers(self, payload: bytes) -> tuple[tuple[int, ...] | None, str | None]:
        tcp_result = parse_modbus_tcp_frame(payload)
        if tcp_result.is_frame and tcp_result.kind == ModbusTcpFrameKind.RESPONSE:
            registers = self._registers_from_read_response(tcp_result.function_code, tcp_result.data)
            if registers is not None:
                return registers, "modbus_tcp"

        rtu_result = parse_modbus_rtu_frame(payload)
        if rtu_result.is_frame and rtu_result.crc_ok and rtu_result.kind == ModbusRtuFrameKind.RESPONSE:
            registers = self._registers_from_read_response(rtu_result.function_code, rtu_result.data)
            if registers is not None:
                return registers, "modbus_rtu"
        return None, None

    def _registers_from_read_response(
        self,
        function_code: int | None,
        data: bytes,
    ) -> tuple[int, ...] | None:
        if function_code not in {0x03, 0x04}:
            return None
        if not data:
            return None
        byte_count = data[0]
        register_bytes = data[1 : 1 + byte_count]
        if len(register_bytes) != byte_count or byte_count % 2 != 0:
            return None
        return tuple(
            int.from_bytes(register_bytes[index : index + 2], "big")
            for index in range(0, len(register_bytes), 2)
        )

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)
