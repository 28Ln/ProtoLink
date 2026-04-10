from __future__ import annotations

from dataclasses import dataclass

from protolink.core.transport import TransportKind


@dataclass(frozen=True, slots=True)
class CaptureReplayJob:
    name: str
    replay_plan_path: str
    target_transport_kind: TransportKind
    repeat_count: int = 1
    enabled: bool = True
