from __future__ import annotations

import json
from collections import Counter, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from protolink.core.logging import (
    LogLevel,
    StructuredLogEntry,
    render_payload_ascii,
    render_payload_hex,
    render_payload_utf8,
)
from protolink.core.modbus_rtu_parser import parse_modbus_rtu_frame, render_modbus_rtu_result
from protolink.core.modbus_tcp_parser import parse_modbus_tcp_frame, render_modbus_tcp_result


class PayloadViewMode(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


@dataclass(slots=True)
class PacketInspectorFilter:
    level: LogLevel | None = None
    session_id: str | None = None
    category_query: str = ""
    text_query: str = ""


@dataclass(frozen=True, slots=True)
class PacketInspectorRow:
    entry_id: str
    timestamp: datetime
    level: LogLevel
    category: str
    message: str
    session_id: str | None
    payload_size: int


class PacketInspectorState:
    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: deque[StructuredLogEntry] = deque(maxlen=max_entries)
        self._listeners: list[Callable[[], None]] = []
        self.filter = PacketInspectorFilter()
        self.payload_view_mode = PayloadViewMode.HEX
        self.selected_entry_id: str | None = None

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def append(self, entry: StructuredLogEntry) -> None:
        self._entries.append(entry)
        self._sync_selection()
        self._notify()

    def extend(self, entries: Iterable[StructuredLogEntry]) -> None:
        for entry in entries:
            self._entries.append(entry)
        self._sync_selection()
        self._notify()

    def set_filter(self, packet_filter: PacketInspectorFilter) -> None:
        self.filter = packet_filter
        self._sync_selection()
        self._notify()

    def clear_filter(self) -> None:
        self.filter = PacketInspectorFilter()
        self._sync_selection()
        self._notify()

    def set_payload_view_mode(self, mode: PayloadViewMode) -> None:
        self.payload_view_mode = mode
        self._notify()

    def select(self, entry_id: str | None) -> None:
        self.selected_entry_id = entry_id
        self._notify()

    def visible_entries(self) -> list[StructuredLogEntry]:
        entries = list(self._entries)
        packet_filter = self.filter
        if not isinstance(packet_filter, PacketInspectorFilter):
            packet_filter = PacketInspectorFilter()
            self.filter = packet_filter

        if packet_filter.level is not None:
            entries = [entry for entry in entries if entry.level == packet_filter.level]

        if packet_filter.session_id:
            entries = [entry for entry in entries if entry.session_id == packet_filter.session_id]

        if packet_filter.category_query.strip():
            query = packet_filter.category_query.strip().lower()
            entries = [entry for entry in entries if query in entry.category.lower()]

        if packet_filter.text_query.strip():
            query = packet_filter.text_query.strip().lower()
            entries = [
                entry
                for entry in entries
                if query in entry.message.lower() or query in self.render_payload(entry).lower()
            ]

        return entries

    def rows(self) -> list[PacketInspectorRow]:
        return [
            PacketInspectorRow(
                entry_id=entry.entry_id,
                timestamp=entry.timestamp,
                level=entry.level,
                category=entry.category,
                message=entry.message,
                session_id=entry.session_id,
                payload_size=len(entry.raw_payload or b""),
            )
            for entry in self.visible_entries()
        ]

    def selected_entry(self) -> StructuredLogEntry | None:
        if self.selected_entry_id is None:
            return None
        for entry in reversed(self._entries):
            if entry.entry_id == self.selected_entry_id:
                return entry
        return None

    def selected_payload_text(self) -> str:
        entry = self.selected_entry()
        if entry is None:
            return ""
        return self.render_payload(entry)

    def selected_metadata_text(self) -> str:
        entry = self.selected_entry()
        if entry is None:
            return ""
        if not entry.metadata:
            return "{}"
        return json.dumps(dict(entry.metadata), ensure_ascii=False, indent=2, sort_keys=True)

    def selected_modbus_rtu_text(self) -> str:
        entry = self.selected_entry()
        if entry is None:
            return "No packet selected."
        return render_modbus_rtu_result(parse_modbus_rtu_frame(entry.raw_payload))

    def selected_protocol_decode_text(self) -> str:
        entry = self.selected_entry()
        if entry is None:
            return "No packet selected."

        tcp_result = parse_modbus_tcp_frame(entry.raw_payload)
        if tcp_result.is_frame:
            return render_modbus_tcp_result(tcp_result)
        return render_modbus_rtu_result(parse_modbus_rtu_frame(entry.raw_payload))

    def counts_by_level(self) -> dict[LogLevel, int]:
        counts = Counter(entry.level for entry in self._entries)
        return {level: counts.get(level, 0) for level in LogLevel}

    def available_session_ids(self) -> tuple[str, ...]:
        session_ids = {entry.session_id for entry in self._entries if entry.session_id}
        return tuple(sorted(session_ids))

    def filter_is_active(self) -> bool:
        return self.filter != PacketInspectorFilter()

    def render_payload(self, entry: StructuredLogEntry) -> str:
        if self.payload_view_mode == PayloadViewMode.ASCII:
            return render_payload_ascii(entry.raw_payload)
        if self.payload_view_mode == PayloadViewMode.UTF8:
            return render_payload_utf8(entry.raw_payload)
        return render_payload_hex(entry.raw_payload)

    def __len__(self) -> int:
        return len(self._entries)

    def _sync_selection(self) -> None:
        visible_entries = self.visible_entries()
        if not visible_entries:
            self.selected_entry_id = None
            return

        if self.selected_entry_id is None:
            self.selected_entry_id = visible_entries[-1].entry_id
            return

        if any(entry.entry_id == self.selected_entry_id for entry in visible_entries):
            return

        self.selected_entry_id = visible_entries[-1].entry_id

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
