from pathlib import Path

from protolink.core.mqtt_server_profiles import (
    MqttServerDraft,
    MqttServerPreset,
    MqttServerProfile,
    default_mqtt_server_profile_path,
    load_mqtt_server_profile,
    save_mqtt_server_profile,
)


def test_mqtt_server_profile_roundtrip(tmp_path: Path) -> None:
    path = default_mqtt_server_profile_path(tmp_path)
    profile = MqttServerProfile(
        selected_preset_name="Bench Broker",
        draft=MqttServerDraft(
            host="127.0.0.1",
            port=1884,
            publish_topic="bench/out",
            send_mode="ascii",
            send_text="READY",
            selected_preset_name="Bench Broker",
        ),
        presets=[
            MqttServerPreset(
                name="Bench Broker",
                host="127.0.0.1",
                port=1884,
                publish_topic="bench/out",
                send_mode="ascii",
                send_text="READY",
            )
        ],
    )

    save_mqtt_server_profile(path, profile)
    loaded = load_mqtt_server_profile(path)

    assert loaded.selected_preset_name == "Bench Broker"
    assert loaded.draft.publish_topic == "bench/out"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.presets[0].port == 1884
