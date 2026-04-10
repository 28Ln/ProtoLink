from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


@dataclass(frozen=True, slots=True)
class SerialStudioPreset:
    name: str
    target: str
    baudrate: int
    send_mode: str
    line_ending: str
    send_text: str


@dataclass(frozen=True, slots=True)
class SerialStudioDraft:
    target: str = ""
    baudrate: int = 9600
    send_mode: str = "hex"
    line_ending: str = "none"
    send_text: str = ""
    selected_preset_name: str | None = None


@dataclass(slots=True)
class SerialStudioProfile:
    format_version: str = "protolink-serial-studio-v1"
    selected_preset_name: str | None = None
    draft: SerialStudioDraft = field(default_factory=SerialStudioDraft)
    presets: list[SerialStudioPreset] = field(default_factory=list)


def default_serial_studio_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "serial_studio.json"


def load_serial_studio_profile(path: Path) -> SerialStudioProfile:
    return load_transport_profile(
        path,
        format_version="protolink-serial-studio-v1",
        default_values={
            "target": "",
            "baudrate": 9600,
            "send_mode": "hex",
            "line_ending": "none",
            "send_text": "",
        },
        build_draft=lambda values, selected: SerialStudioDraft(
            target=str(values.get("target", "")),
            baudrate=int(values.get("baudrate", 9600)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
            selected_preset_name=selected,
        ),
        build_preset=lambda name, values: SerialStudioPreset(
            name=name,
            target=str(values.get("target", "")),
            baudrate=int(values.get("baudrate", 9600)),
            send_mode=str(values.get("send_mode", "hex")),
            line_ending=str(values.get("line_ending", "none")),
            send_text=str(values.get("send_text", "")),
        ),
        build_profile=lambda version, selected, draft, presets: SerialStudioProfile(
            format_version=version,
            selected_preset_name=selected,
            draft=draft,
            presets=presets,
        ),
    )


def save_serial_studio_profile(path: Path, profile: SerialStudioProfile) -> None:
    save_transport_profile(
        path,
        profile_format_version=profile.format_version,
        profile_selected_preset_name=profile.selected_preset_name,
        draft_values={
            "target": profile.draft.target,
            "baudrate": profile.draft.baudrate,
            "send_mode": profile.draft.send_mode,
            "line_ending": profile.draft.line_ending,
            "send_text": profile.draft.send_text,
        },
        draft_selected_preset_name=profile.draft.selected_preset_name,
        presets=profile.presets,
        preset_name_getter=lambda preset: preset.name,
        preset_values_getter=lambda preset: {
            "target": preset.target,
            "baudrate": preset.baudrate,
            "send_mode": preset.send_mode,
            "line_ending": preset.line_ending,
            "send_text": preset.send_text,
        },
    )
