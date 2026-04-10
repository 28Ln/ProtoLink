from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


@dataclass(frozen=True, slots=True)
class UdpPreset:
    name: str
    local_host: str
    local_port: int
    remote_host: str
    remote_port: int
    send_mode: str
    line_ending: str
    send_text: str


@dataclass(frozen=True, slots=True)
class UdpDraft:
    local_host: str = "127.0.0.1"
    local_port: int = 0
    remote_host: str = "127.0.0.1"
    remote_port: int = 502
    send_mode: str = "hex"
    line_ending: str = "none"
    send_text: str = ""
    selected_preset_name: str | None = None


@dataclass(slots=True)
class UdpProfile:
    format_version: str = "protolink-udp-lab-v1"
    selected_preset_name: str | None = None
    draft: UdpDraft = field(default_factory=UdpDraft)
    presets: list[UdpPreset] = field(default_factory=list)


def default_udp_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "udp_lab.json"


def load_udp_profile(path: Path) -> UdpProfile:
    return load_transport_profile(
        path,
        format_version="protolink-udp-lab-v1",
        default_values={
            "local_host": "127.0.0.1",
            "local_port": 0,
            "remote_host": "127.0.0.1",
            "remote_port": 502,
            "send_mode": "hex",
            "line_ending": "none",
            "send_text": "",
        },
        build_draft=lambda values, selected: UdpDraft(
            local_host=str(values.get("local_host", "127.0.0.1")),
            local_port=int(values.get("local_port", 0)),
            remote_host=str(values.get("remote_host", "127.0.0.1")),
            remote_port=int(values.get("remote_port", 502)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
            selected_preset_name=selected,
        ),
        build_preset=lambda name, values: UdpPreset(
            name=name,
            local_host=str(values.get("local_host", "127.0.0.1")),
            local_port=int(values.get("local_port", 0)),
            remote_host=str(values.get("remote_host", "127.0.0.1")),
            remote_port=int(values.get("remote_port", 502)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
        ),
        build_profile=lambda version, selected, draft, presets: UdpProfile(
            format_version=version,
            selected_preset_name=selected,
            draft=draft,
            presets=presets,
        ),
    )


def save_udp_profile(path: Path, profile: UdpProfile) -> None:
    save_transport_profile(
        path,
        profile_format_version=profile.format_version,
        profile_selected_preset_name=profile.selected_preset_name,
        draft_values={
            "local_host": profile.draft.local_host,
            "local_port": profile.draft.local_port,
            "remote_host": profile.draft.remote_host,
            "remote_port": profile.draft.remote_port,
            "send_mode": profile.draft.send_mode,
            "line_ending": profile.draft.line_ending,
            "send_text": profile.draft.send_text,
        },
        draft_selected_preset_name=profile.draft.selected_preset_name,
        presets=profile.presets,
        preset_name_getter=lambda preset: preset.name,
        preset_values_getter=lambda preset: {
            "local_host": preset.local_host,
            "local_port": preset.local_port,
            "remote_host": preset.remote_host,
            "remote_port": preset.remote_port,
            "send_mode": preset.send_mode,
            "line_ending": preset.line_ending,
            "send_text": preset.send_text,
        },
    )
