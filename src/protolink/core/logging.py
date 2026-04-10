from __future__ import annotations

import json
from pathlib import Path
import threading
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from protolink.core.transport import MessageDirection, RawTransportMessage, TransportEvent, TransportEventType

DEFAULT_SERIALIZED_PAYLOAD_BYTES = 4096


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StructuredLogEntry:
    entry_id: str
    timestamp: datetime
    level: LogLevel
    category: str
    message: str
    session_id: str | None = None
    transport_kind: str | None = None
    raw_payload: bytes | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


def create_log_entry(
    *,
    level: LogLevel,
    category: str,
    message: str,
    session_id: str | None = None,
    transport_kind: str | None = None,
    raw_payload: bytes | None = None,
    metadata: Mapping[str, str] | None = None,
) -> StructuredLogEntry:
    return StructuredLogEntry(
        entry_id=uuid4().hex,
        timestamp=datetime.now(UTC),
        level=level,
        category=category,
        message=message,
        session_id=session_id,
        transport_kind=transport_kind,
        raw_payload=raw_payload,
        metadata=metadata or {},
    )


def create_log_entry_from_transport_event(event: TransportEvent) -> StructuredLogEntry:
    if event.event_type == TransportEventType.STATE_CHANGED:
        return create_log_entry(
            level=LogLevel.INFO,
            category="transport.state",
            message=f"{event.session.kind} state changed to {event.session.state}",
            session_id=event.session.session_id,
            transport_kind=event.session.kind,
            metadata={"target": event.session.target},
        )

    if event.event_type == TransportEventType.MESSAGE and event.message is not None:
        direction = event.message.direction
        return create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message=_format_message_summary(direction, event.message),
            session_id=event.session.session_id,
            transport_kind=event.session.kind,
            raw_payload=event.message.payload,
            metadata=dict(event.message.metadata),
        )

    return create_log_entry(
        level=LogLevel.ERROR,
        category="transport.error",
        message=event.error or "Unknown transport error",
        session_id=event.session.session_id,
        transport_kind=event.session.kind,
        metadata={"target": event.session.target},
    )


def _format_message_summary(direction: MessageDirection, message: RawTransportMessage) -> str:
    direction_label = {
        MessageDirection.INBOUND: "Inbound",
        MessageDirection.OUTBOUND: "Outbound",
        MessageDirection.INTERNAL: "Internal",
    }[direction]
    return f"{direction_label} payload ({len(message.payload)} bytes)"


class InMemoryLogStore:
    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: deque[StructuredLogEntry] = deque(maxlen=max_entries)

    def append(self, entry: StructuredLogEntry) -> None:
        self._entries.append(entry)

    def extend(self, entries: Iterable[StructuredLogEntry]) -> None:
        self._entries.extend(entries)

    def latest(self, limit: int = 100) -> list[StructuredLogEntry]:
        if limit <= 0:
            return []
        return list(self._entries)[-limit:]

    def by_session(self, session_id: str) -> list[StructuredLogEntry]:
        return [entry for entry in self._entries if entry.session_id == session_id]

    def __len__(self) -> int:
        return len(self._entries)


def serialize_log_entry(
    entry: StructuredLogEntry,
    *,
    max_raw_payload_bytes: int = DEFAULT_SERIALIZED_PAYLOAD_BYTES,
) -> dict[str, object]:
    metadata = dict(entry.metadata)
    raw_payload_hex = None
    if entry.raw_payload is not None:
        payload_limit = max(max_raw_payload_bytes, 0)
        serialized_payload = entry.raw_payload[:payload_limit]
        raw_payload_hex = serialized_payload.hex()
        if len(serialized_payload) < len(entry.raw_payload):
            metadata.setdefault("raw_payload_truncated", "true")
            metadata.setdefault("raw_payload_original_bytes", str(len(entry.raw_payload)))
            metadata.setdefault("raw_payload_serialized_bytes", str(len(serialized_payload)))

    return {
        "entry_id": entry.entry_id,
        "timestamp": entry.timestamp.isoformat(),
        "level": entry.level.value,
        "category": entry.category,
        "message": entry.message,
        "session_id": entry.session_id,
        "transport_kind": entry.transport_kind,
        "raw_payload_hex": raw_payload_hex,
        "metadata": metadata,
    }


def default_workspace_log_path(logs_dir: Path) -> Path:
    return logs_dir / "transport-events.jsonl"


class WorkspaceJsonlLogWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.failed_write_count = 0
        self.last_error: str | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: StructuredLogEntry) -> None:
        payload = json.dumps(serialize_log_entry(entry), ensure_ascii=False)
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.write("\n")
            except OSError as exc:
                self.failed_write_count += 1
                self.last_error = str(exc)


def render_payload_hex(payload: bytes | None) -> str:
    if not payload:
        return ""
    return " ".join(f"{byte:02X}" for byte in payload)


def render_payload_ascii(payload: bytes | None) -> str:
    if not payload:
        return ""
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in payload)


def render_payload_utf8(payload: bytes | None) -> str:
    if not payload:
        return ""
    return payload.decode("utf-8", errors="replace")
