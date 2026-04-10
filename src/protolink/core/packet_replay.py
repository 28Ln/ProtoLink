from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from protolink.core.import_export import sanitize_artifact_name
from protolink.core.logging import StructuredLogEntry


class ReplayDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PacketReplayStep:
    delay_ms: int
    payload: bytes
    direction: ReplayDirection
    session_id: str | None = None
    transport_kind: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    source_message: str = ""


@dataclass(frozen=True, slots=True)
class PacketReplayPlan:
    name: str
    created_at: datetime
    steps: tuple[PacketReplayStep, ...]
    format_version: str = "protolink-packet-replay-v1"


def build_packet_replay_plan(
    entries: Iterable[StructuredLogEntry],
    *,
    name: str,
    include_directions: Set[ReplayDirection] | None = None,
    created_at: datetime | None = None,
) -> PacketReplayPlan:
    include_directions = include_directions or {ReplayDirection.OUTBOUND}
    sorted_entries = sorted(entries, key=lambda entry: entry.timestamp)
    steps: list[PacketReplayStep] = []
    previous_timestamp: datetime | None = None

    for entry in sorted_entries:
        if entry.category != "transport.message":
            continue
        if not entry.raw_payload:
            continue

        direction = infer_replay_direction(entry)
        if direction not in include_directions:
            continue

        delay_ms = 0
        if previous_timestamp is not None:
            delta_ms = int((entry.timestamp - previous_timestamp).total_seconds() * 1000)
            delay_ms = max(delta_ms, 0)

        steps.append(
            PacketReplayStep(
                delay_ms=delay_ms,
                payload=entry.raw_payload,
                direction=direction,
                session_id=entry.session_id,
                transport_kind=entry.transport_kind,
                metadata=dict(entry.metadata),
                source_message=entry.message,
            )
        )
        previous_timestamp = entry.timestamp

    return PacketReplayPlan(
        name=sanitize_artifact_name(name),
        created_at=created_at or datetime.now(UTC),
        steps=tuple(steps),
    )


def infer_replay_direction(entry: StructuredLogEntry) -> ReplayDirection:
    explicit = entry.metadata.get("direction")
    if explicit:
        try:
            return ReplayDirection(str(explicit).strip().lower())
        except ValueError:
            pass

    message = entry.message.strip().lower()
    if message.startswith("outbound "):
        return ReplayDirection.OUTBOUND
    if message.startswith("inbound "):
        return ReplayDirection.INBOUND
    if message.startswith("internal "):
        return ReplayDirection.INTERNAL
    return ReplayDirection.UNKNOWN


def default_packet_replay_path(captures_dir: Path, name: str, *, created_at: datetime | None = None) -> Path:
    created_at = created_at or datetime.now(UTC)
    timestamp = created_at.strftime("%Y%m%d-%H%M%S")
    return captures_dir / f"{timestamp}-replay-{sanitize_artifact_name(name)}.json"


def serialize_packet_replay_plan(plan: PacketReplayPlan) -> dict[str, object]:
    return {
        "format_version": plan.format_version,
        "name": plan.name,
        "created_at": plan.created_at.isoformat(),
        "steps": [
            {
                "delay_ms": step.delay_ms,
                "direction": step.direction.value,
                "session_id": step.session_id,
                "transport_kind": step.transport_kind,
                "payload_hex": step.payload.hex(" "),
                "metadata": dict(step.metadata),
                "source_message": step.source_message,
            }
            for step in plan.steps
        ],
    }


def save_packet_replay_plan(path: Path, plan: PacketReplayPlan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_packet_replay_plan(plan)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_packet_replay_plan(path: Path) -> PacketReplayPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    format_version = str(data.get("format_version", ""))
    if format_version != "protolink-packet-replay-v1":
        raise ValueError(f"Unsupported packet replay format version: {format_version or '<missing>'}")

    created_at_raw = str(data.get("created_at", ""))
    created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    steps_data = data.get("steps", [])
    if not isinstance(steps_data, list):
        raise ValueError("Packet replay steps must be a list.")

    steps: list[PacketReplayStep] = []
    for raw_step in steps_data:
        if not isinstance(raw_step, dict):
            continue
        payload_hex = str(raw_step.get("payload_hex", "")).strip()
        payload = bytes.fromhex(payload_hex) if payload_hex else b""
        direction_raw = str(raw_step.get("direction", ReplayDirection.UNKNOWN.value)).strip().lower()
        try:
            direction = ReplayDirection(direction_raw)
        except ValueError:
            direction = ReplayDirection.UNKNOWN

        metadata_raw = raw_step.get("metadata", {})
        metadata: dict[str, str] = {}
        if isinstance(metadata_raw, dict):
            metadata = {str(key): str(value) for key, value in metadata_raw.items()}

        steps.append(
            PacketReplayStep(
                delay_ms=max(int(raw_step.get("delay_ms", 0)), 0),
                payload=payload,
                direction=direction,
                session_id=str(raw_step["session_id"]) if raw_step.get("session_id") is not None else None,
                transport_kind=str(raw_step["transport_kind"]) if raw_step.get("transport_kind") is not None else None,
                metadata=metadata,
                source_message=str(raw_step.get("source_message", "")),
            )
        )

    return PacketReplayPlan(
        name=str(data.get("name", "packet-replay")).strip() or "packet-replay",
        created_at=created_at,
        steps=tuple(steps),
        format_version=format_version,
    )
