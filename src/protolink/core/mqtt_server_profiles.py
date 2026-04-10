from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


@dataclass(frozen=True, slots=True)
class MqttServerPreset:
    name: str
    host: str
    port: int
    publish_topic: str
    send_mode: str
    send_text: str


@dataclass(frozen=True, slots=True)
class MqttServerDraft:
    host: str = "127.0.0.1"
    port: int = 1883
    publish_topic: str = "bench/topic"
    send_mode: str = "hex"
    send_text: str = ""
    selected_preset_name: str | None = None


@dataclass(slots=True)
class MqttServerProfile:
    format_version: str = "protolink-mqtt-server-v1"
    selected_preset_name: str | None = None
    draft: MqttServerDraft = field(default_factory=MqttServerDraft)
    presets: list[MqttServerPreset] = field(default_factory=list)


def default_mqtt_server_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "mqtt_server.json"


def load_mqtt_server_profile(path: Path) -> MqttServerProfile:
    return load_transport_profile(
        path,
        format_version="protolink-mqtt-server-v1",
        default_values={
            "host": "127.0.0.1",
            "port": 1883,
            "publish_topic": "bench/topic",
            "send_mode": "hex",
            "send_text": "",
        },
        build_draft=lambda values, selected: MqttServerDraft(
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 1883)),
            publish_topic=str(values.get("publish_topic", "bench/topic")),
            send_mode=str(values.get("send_mode", "hex")),
            send_text=str(values.get("send_text", "")),
            selected_preset_name=selected,
        ),
        build_preset=lambda name, values: MqttServerPreset(
            name=name,
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 1883)),
            publish_topic=str(values.get("publish_topic", "bench/topic")),
            send_mode=str(values.get("send_mode", "hex")),
            send_text=str(values.get("send_text", "")),
        ),
        build_profile=lambda version, selected, draft, presets: MqttServerProfile(
            format_version=version,
            selected_preset_name=selected,
            draft=draft,
            presets=presets,
        ),
    )


def save_mqtt_server_profile(path: Path, profile: MqttServerProfile) -> None:
    save_transport_profile(
        path,
        profile_format_version=profile.format_version,
        profile_selected_preset_name=profile.selected_preset_name,
        draft_values={
            "host": profile.draft.host,
            "port": profile.draft.port,
            "publish_topic": profile.draft.publish_topic,
            "send_mode": profile.draft.send_mode,
            "send_text": profile.draft.send_text,
        },
        draft_selected_preset_name=profile.draft.selected_preset_name,
        presets=profile.presets,
        preset_name_getter=lambda preset: preset.name,
        preset_values_getter=lambda preset: {
            "host": preset.host,
            "port": preset.port,
            "publish_topic": preset.publish_topic,
            "send_mode": preset.send_mode,
            "send_text": preset.send_text,
        },
    )
