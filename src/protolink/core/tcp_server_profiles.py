from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


@dataclass(frozen=True, slots=True)
class TcpServerPreset:
    name: str
    host: str
    port: int
    send_mode: str
    line_ending: str
    send_text: str


@dataclass(frozen=True, slots=True)
class TcpServerDraft:
    host: str = "127.0.0.1"
    port: int = 502
    send_mode: str = "hex"
    line_ending: str = "none"
    send_text: str = ""
    selected_preset_name: str | None = None


@dataclass(slots=True)
class TcpServerProfile:
    format_version: str = "protolink-tcp-server-v1"
    selected_preset_name: str | None = None
    draft: TcpServerDraft = field(default_factory=TcpServerDraft)
    presets: list[TcpServerPreset] = field(default_factory=list)


def default_tcp_server_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "tcp_server.json"


def load_tcp_server_profile(path: Path) -> TcpServerProfile:
    return load_transport_profile(
        path,
        format_version="protolink-tcp-server-v1",
        default_values={
            "host": "127.0.0.1",
            "port": 502,
            "send_mode": "hex",
            "line_ending": "none",
            "send_text": "",
        },
        build_draft=lambda values, selected: TcpServerDraft(
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 502)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
            selected_preset_name=selected,
        ),
        build_preset=lambda name, values: TcpServerPreset(
            name=name,
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 502)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
        ),
        build_profile=lambda version, selected, draft, presets: TcpServerProfile(
            format_version=version,
            selected_preset_name=selected,
            draft=draft,
            presets=presets,
        ),
    )


def save_tcp_server_profile(path: Path, profile: TcpServerProfile) -> None:
    save_transport_profile(
        path,
        profile_format_version=profile.format_version,
        profile_selected_preset_name=profile.selected_preset_name,
        draft_values={
            "host": profile.draft.host,
            "port": profile.draft.port,
            "send_mode": profile.draft.send_mode,
            "line_ending": profile.draft.line_ending,
            "send_text": profile.draft.send_text,
        },
        draft_selected_preset_name=profile.draft.selected_preset_name,
        presets=profile.presets,
        preset_name_getter=lambda preset: preset.name,
        preset_values_getter=lambda preset: {
            "host": preset.host,
            "port": preset.port,
            "send_mode": preset.send_mode,
            "line_ending": preset.line_ending,
            "send_text": preset.send_text,
        },
    )
