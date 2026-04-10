from datetime import UTC, datetime, timedelta
from pathlib import Path

from protolink.core.logging import LogLevel, StructuredLogEntry
from protolink.core.packet_replay import (
    ReplayDirection,
    build_packet_replay_plan,
    default_packet_replay_path,
    load_packet_replay_plan,
    save_packet_replay_plan,
)


def _message_entry(
    *,
    entry_id: str,
    timestamp: datetime,
    message: str,
    payload: bytes,
    session_id: str = "session-a",
    transport_kind: str = "serial",
) -> StructuredLogEntry:
    return StructuredLogEntry(
        entry_id=entry_id,
        timestamp=timestamp,
        level=LogLevel.INFO,
        category="transport.message",
        message=message,
        session_id=session_id,
        transport_kind=transport_kind,
        raw_payload=payload,
        metadata={},
    )


def test_build_packet_replay_plan_defaults_to_outbound_steps() -> None:
    base = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
    entries = [
        _message_entry(entry_id="2", timestamp=base + timedelta(milliseconds=120), message="Inbound payload", payload=b"\x02"),
        _message_entry(entry_id="1", timestamp=base, message="Outbound payload", payload=b"\x01"),
        _message_entry(entry_id="3", timestamp=base + timedelta(milliseconds=370), message="Outbound payload", payload=b"\x03"),
    ]

    plan = build_packet_replay_plan(entries, name="Bench Replay")

    assert plan.name == "Bench-Replay"
    assert len(plan.steps) == 2
    assert plan.steps[0].payload == b"\x01"
    assert plan.steps[0].delay_ms == 0
    assert plan.steps[1].payload == b"\x03"
    assert plan.steps[1].delay_ms == 370
    assert all(step.direction == ReplayDirection.OUTBOUND for step in plan.steps)


def test_build_packet_replay_plan_can_include_inbound_steps() -> None:
    base = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
    entries = [
        _message_entry(entry_id="1", timestamp=base, message="Outbound payload", payload=b"\x01"),
        _message_entry(
            entry_id="2",
            timestamp=base + timedelta(milliseconds=200),
            message="Inbound payload",
            payload=b"\x02",
        ),
    ]

    plan = build_packet_replay_plan(
        entries,
        name="both-directions",
        include_directions={ReplayDirection.OUTBOUND, ReplayDirection.INBOUND},
    )

    assert len(plan.steps) == 2
    assert plan.steps[1].direction == ReplayDirection.INBOUND
    assert plan.steps[1].delay_ms == 200


def test_packet_replay_plan_round_trip_persistence(tmp_path: Path) -> None:
    base = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
    entries = [
        _message_entry(entry_id="1", timestamp=base, message="Outbound payload", payload=b"\x10\x20"),
        _message_entry(
            entry_id="2",
            timestamp=base + timedelta(milliseconds=50),
            message="Internal payload",
            payload=b"\x30",
        ),
    ]
    plan = build_packet_replay_plan(
        entries,
        name="roundtrip",
        include_directions={ReplayDirection.OUTBOUND, ReplayDirection.INTERNAL},
        created_at=base,
    )
    replay_path = default_packet_replay_path(tmp_path, plan.name, created_at=base)
    save_packet_replay_plan(replay_path, plan)

    restored = load_packet_replay_plan(replay_path)

    assert restored.format_version == "protolink-packet-replay-v1"
    assert restored.name == "roundtrip"
    assert restored.created_at == base
    assert [step.payload for step in restored.steps] == [b"\x10\x20", b"\x30"]
    assert [step.direction for step in restored.steps] == [ReplayDirection.OUTBOUND, ReplayDirection.INTERNAL]
