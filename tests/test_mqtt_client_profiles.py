from pathlib import Path

from protolink.core.mqtt_client_profiles import (
    MqttClientDraft,
    MqttClientPreset,
    MqttClientProfile,
    default_mqtt_client_profile_path,
    load_mqtt_client_profile,
    save_mqtt_client_profile,
)


def test_mqtt_client_profile_roundtrip(tmp_path: Path) -> None:
    path = default_mqtt_client_profile_path(tmp_path)
    profile = MqttClientProfile(
        selected_preset_name="Bench MQTT",
        draft=MqttClientDraft(
            host="127.0.0.1",
            port=1883,
            client_id="bench",
            publish_topic="bench/out",
            subscribe_topic="bench/in",
            send_mode="ascii",
            send_text="PING",
            selected_preset_name="Bench MQTT",
        ),
        presets=[
            MqttClientPreset(
                name="Bench MQTT",
                host="127.0.0.1",
                port=1883,
                client_id="bench",
                publish_topic="bench/out",
                subscribe_topic="bench/in",
                send_mode="ascii",
                send_text="PING",
            )
        ],
    )

    save_mqtt_client_profile(path, profile)
    loaded = load_mqtt_client_profile(path)

    assert loaded.selected_preset_name == "Bench MQTT"
    assert loaded.draft.publish_topic == "bench/out"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.presets[0].client_id == "bench"
