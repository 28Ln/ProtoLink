from __future__ import annotations

from dataclasses import dataclass

from protolink.core.script_host import ScriptLanguage
from protolink.core.transport import TransportKind


@dataclass(frozen=True, slots=True)
class ChannelBridgeConfig:
    name: str
    source_transport_kind: TransportKind
    target_transport_kind: TransportKind
    enabled: bool = True
    script_language: ScriptLanguage | None = None
    script_code: str = ""
