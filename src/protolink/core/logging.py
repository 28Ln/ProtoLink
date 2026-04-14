from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import threading
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from protolink.core.transport import MessageDirection, RawTransportMessage, TransportEvent, TransportEventType
from protolink.presentation import display_connection_state, display_transport_name

DEFAULT_SERIALIZED_PAYLOAD_BYTES = 4096
RUNTIME_FAILURE_EVIDENCE_FILE = "runtime-failure-evidence.jsonl"
RUNTIME_FAILURE_EVIDENCE_FILE_ALIASES = (
    RUNTIME_FAILURE_EVIDENCE_FILE,
    "runtime-failure-events.jsonl",
    "runtime-failures.jsonl",
)
CONFIG_FAILURE_EVIDENCE_FILE = "config-failure-evidence.jsonl"


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


@dataclass(frozen=True, slots=True)
class RuntimeFailureEvidence:
    entry_id: str
    timestamp: datetime
    source: str
    code: str
    message: str
    details: Mapping[str, str] = field(default_factory=dict)


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


def create_runtime_failure_evidence(
    *,
    source: str,
    code: str,
    message: str,
    details: Mapping[str, str] | None = None,
) -> RuntimeFailureEvidence:
    return RuntimeFailureEvidence(
        entry_id=uuid4().hex,
        timestamp=datetime.now(UTC),
        source=source,
        code=code,
        message=message,
        details=details or {},
    )


def create_log_entry_from_transport_event(event: TransportEvent) -> StructuredLogEntry:
    if event.event_type == TransportEventType.STATE_CHANGED:
        return create_log_entry(
            level=LogLevel.INFO,
            category="transport.state",
            message=f"{display_transport_name(event.session.kind)}状态切换为{display_connection_state(event.session.state)}",
            session_id=event.session.session_id,
            transport_kind=event.session.kind,
            metadata={"target": event.session.target},
        )

    if event.event_type == TransportEventType.MESSAGE and event.message is not None:
        direction = event.message.direction
        metadata = dict(event.message.metadata)
        metadata.setdefault("direction", direction.value)
        return create_log_entry(
            level=LogLevel.INFO,
            category="transport.message",
            message=_format_message_summary(direction, event.message),
            session_id=event.session.session_id,
            transport_kind=event.session.kind,
            raw_payload=event.message.payload,
            metadata=metadata,
        )

    return create_log_entry(
        level=LogLevel.ERROR,
        category="transport.error",
        message=event.error or "未知传输异常",
        session_id=event.session.session_id,
        transport_kind=event.session.kind,
        metadata={"target": event.session.target},
    )


def _format_message_summary(direction: MessageDirection, message: RawTransportMessage) -> str:
    direction_label = {
        MessageDirection.INBOUND: "入站",
        MessageDirection.OUTBOUND: "出站",
        MessageDirection.INTERNAL: "内部",
    }[direction]
    return f"{direction_label}报文（{len(message.payload)} 字节）"


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


def serialize_runtime_failure_evidence(entry: RuntimeFailureEvidence) -> dict[str, object]:
    return {
        "entry_id": entry.entry_id,
        "timestamp": entry.timestamp.isoformat(),
        "source": entry.source,
        "code": entry.code,
        "message": entry.message,
        "details": dict(entry.details),
    }


def default_workspace_log_path(logs_dir: Path) -> Path:
    return logs_dir / "transport-events.jsonl"


def default_runtime_failure_evidence_path(logs_dir: Path) -> Path:
    return logs_dir / RUNTIME_FAILURE_EVIDENCE_FILE


def default_config_failure_evidence_path(root: Path) -> Path:
    return root / CONFIG_FAILURE_EVIDENCE_FILE


def failure_evidence_fallback_path(path: Path) -> Path:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "protolink-failure-evidence" / f"{digest}-{path.name}"


def runtime_failure_evidence_candidate_paths(logs_dir: Path) -> tuple[Path, ...]:
    primary_paths = tuple(logs_dir / name for name in RUNTIME_FAILURE_EVIDENCE_FILE_ALIASES)
    fallback_paths = tuple(failure_evidence_fallback_path(path) for path in primary_paths)
    return primary_paths + fallback_paths


def config_failure_evidence_candidate_paths(root: Path) -> tuple[Path, ...]:
    primary = default_config_failure_evidence_path(root)
    return (primary, failure_evidence_fallback_path(primary))


def _load_failure_evidence_file(path: Path) -> tuple[Path | None, list[dict[str, object]], str | None]:
    if not path.exists():
        return None, [], None

    entries: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    return path, [], f"line {line_number} must contain a JSON object"
                if not all(
                    isinstance(payload.get(key), str) and str(payload.get(key, "")).strip()
                    for key in ("entry_id", "timestamp", "source", "code", "message")
                ):
                    return path, [], f"line {line_number} is missing required failure-evidence fields"
                details = payload.get("details", {})
                if not isinstance(details, dict):
                    return path, [], f"line {line_number} must contain an object details field"
                entries.append(
                    {
                        "entry_id": str(payload["entry_id"]),
                        "timestamp": str(payload["timestamp"]),
                        "source": str(payload["source"]),
                        "code": str(payload["code"]),
                        "message": str(payload["message"]),
                        "details": {str(key): str(value) for key, value in details.items()},
                    }
                )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return path, [], str(exc)

    return path, entries, None


def load_runtime_failure_evidence(logs_dir: Path) -> tuple[Path | None, list[dict[str, object]], str | None]:
    for candidate in runtime_failure_evidence_candidate_paths(logs_dir):
        evidence_file, entries, error = _load_failure_evidence_file(candidate)
        if evidence_file is None:
            continue
        return evidence_file, entries, error

    return None, [], None


def load_config_failure_evidence(root: Path) -> tuple[Path | None, list[dict[str, object]], str | None]:
    for candidate in config_failure_evidence_candidate_paths(root):
        evidence_file, entries, error = _load_failure_evidence_file(candidate)
        if evidence_file is None:
            continue
        return evidence_file, entries, error

    return None, [], None


class RuntimeFailureEvidenceRecorder:
    def __init__(self, path: Path, *, fallback_path: Path | None = None) -> None:
        self.path = path
        self.fallback_path = fallback_path or failure_evidence_fallback_path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        source: str,
        code: str,
        message: str,
        details: Mapping[str, str] | None = None,
    ) -> None:
        entry = create_runtime_failure_evidence(
            source=source,
            code=code,
            message=message,
            details=details,
        )
        payload = json.dumps(serialize_runtime_failure_evidence(entry), ensure_ascii=False)
        with self._lock:
            for destination in (self.path, self.fallback_path):
                try:
                    with destination.open("a", encoding="utf-8") as handle:
                        handle.write(payload)
                        handle.write("\n")
                    return
                except OSError:
                    continue

    def append_handler_error(self, *, event_type: str, handler_name: str, error: str) -> None:
        self.append(
            source="event_bus",
            code="event_handler_error",
            message=error,
            details={
                "event_type": event_type,
                "handler_name": handler_name,
            },
        )

    def append_log_write_failure(self, *, log_file: Path, error: str) -> None:
        self.append(
            source="workspace_log_writer",
            code="workspace_log_write_failure",
            message=error,
            details={"log_file": str(log_file)},
        )


class WorkspaceJsonlLogWriter:
    def __init__(
        self,
        path: Path,
        *,
        failure_evidence_recorder: RuntimeFailureEvidenceRecorder | None = None,
    ) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._failure_evidence_recorder = failure_evidence_recorder
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
                if self._failure_evidence_recorder is not None:
                    self._failure_evidence_recorder.append_log_write_failure(
                        log_file=self.path,
                        error=str(exc),
                    )


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
