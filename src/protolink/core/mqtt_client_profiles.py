from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


@dataclass(frozen=True, slots=True)
class MqttClientPreset:
    name: str
    host: str
    port: int
    client_id: str
    publish_topic: str
    subscribe_topic: str
    send_mode: str
    send_text: str


@dataclass(frozen=True, slots=True)
class MqttClientDraft:
    host: str = "127.0.0.1"
    port: int = 1883
    client_id: str = ""
    publish_topic: str = "bench/topic"
    subscribe_topic: str = "bench/topic"
    send_mode: str = "hex"
    send_text: str = ""
    selected_preset_name: str | None = None


@dataclass(slots=True)
class MqttClientProfile:
    format_version: str = "protolink-mqtt-client-v1"
    selected_preset_name: str | None = None
    draft: MqttClientDraft = field(default_factory=MqttClientDraft)
    presets: list[MqttClientPreset] = field(default_factory=list)


def default_mqtt_client_profile_path(profiles_dir: Path) -> Path:
    return profiles_dir / "mqtt_client.json"


def load_mqtt_client_profile(path: Path) -> MqttClientProfile:
    return load_transport_profile(
        path,
        format_version="protolink-mqtt-client-v1",
        default_values={
            "host": "127.0.0.1",
            "port": 1883,
            "client_id": "",
            "publish_topic": "bench/topic",
            "subscribe_topic": "bench/topic",
            "send_mode": "hex",
            "send_text": "",
        },
        build_draft=lambda values, selected: MqttClientDraft(
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 1883)),
            client_id=str(values.get("client_id", "")),
            publish_topic=str(values.get("publish_topic", "bench/topic")),
            subscribe_topic=str(values.get("subscribe_topic", "bench/topic")),
            send_mode=str(values.get("send_mode", "hex")),
            send_text=str(values.get("send_text", "")),
            selected_preset_name=selected,
        ),
        build_preset=lambda name, values: MqttClientPreset(
            name=name,
            host=str(values.get("host", "127.0.0.1")),
            port=int(values.get("port", 1883)),
            client_id=str(values.get("client_id", "")),
            publish_topic=str(values.get("publish_topic", "bench/topic")),
            subscribe_topic=str(values.get("subscribe_topic", "bench/topic")),
            send_mode=str(values.get("send_mode", "hex")),
            send_text=str(values.get("send_text", "")),
        ),
        build_profile=lambda version, selected, draft, presets: MqttClientProfile(
            format_version=version,
            selected_preset_name=selected,
            draft=draft,
            presets=presets,
        ),
    )


def save_mqtt_client_profile(path: Path, profile: MqttClientProfile) -> None:
    save_transport_profile(
        path,
        profile_format_version=profile.format_version,
        profile_selected_preset_name=profile.selected_preset_name,
        draft_values={
            "host": profile.draft.host,
            "port": profile.draft.port,
            "client_id": profile.draft.client_id,
            "publish_topic": profile.draft.publish_topic,
            "subscribe_topic": profile.draft.subscribe_topic,
            "send_mode": profile.draft.send_mode,
            "send_text": profile.draft.send_text,
        },
        draft_selected_preset_name=profile.draft.selected_preset_name,
        presets=profile.presets,
        preset_name_getter=lambda preset: preset.name,
        preset_values_getter=lambda preset: {
            "host": preset.host,
            "port": preset.port,
            "client_id": preset.client_id,
            "publish_topic": preset.publish_topic,
            "subscribe_topic": preset.subscribe_topic,
            "send_mode": preset.send_mode,
            "send_text": preset.send_text,
        },
    )
