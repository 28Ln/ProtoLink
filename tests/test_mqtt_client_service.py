import socket
import time
from pathlib import Path

from protolink.application.mqtt_client_service import MqttClientSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from tests.support import MqttTestBroker


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


def _find_unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_mqtt_client_service_connect_subscribe_publish_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_client_service

    with MqttTestBroker() as broker:
        service.set_host(broker.host)
        service.set_port(broker.port)
        service.set_client_id("bench-mqtt")
        service.set_publish_topic("bench/topic")
        service.set_subscribe_topic("bench/topic")
        service.set_send_mode(MqttClientSendEncoding.ASCII)
        service.set_send_text("PING")

        service.open_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)
        service.subscribe_current_topic()
        _wait_until(lambda: "bench/topic" in service.snapshot.subscribed_topics)

        service.send_current_payload()
        _wait_until(lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 3)

        payloads = [entry.raw_payload for entry in context.log_store.latest(20) if entry.category == "transport.message"]
        assert b"PING" in payloads
        assert context.packet_inspector.rows()

        service.close_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)

    service.shutdown()


def test_mqtt_client_service_surfaces_open_errors(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_client_service
    service.set_host("127.0.0.1")
    service.set_port(_find_unused_port())

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.ERROR, timeout=8.0)

    assert service.snapshot.last_error is not None
    assert any(entry.category == "transport.error" for entry in context.log_store.latest(10))
    service.shutdown()


def test_mqtt_client_service_persists_presets_and_restores_topics(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_client_service
    service.set_host("127.0.0.1")
    service.set_port(1883)
    service.set_client_id("bench-mqtt")
    service.set_publish_topic("bench/out")
    service.set_subscribe_topic("bench/in")
    service.set_send_mode(MqttClientSendEncoding.ASCII)
    service.set_send_text("PING")
    service.save_preset("Bench MQTT")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.mqtt_client_service
    assert reloaded.snapshot.preset_names == ("Bench MQTT",)
    reloaded.load_preset("Bench MQTT")

    assert reloaded.snapshot.selected_preset_name == "Bench MQTT"
    assert reloaded.snapshot.client_id == "bench-mqtt"
    assert reloaded.snapshot.publish_topic == "bench/out"
    assert reloaded.snapshot.subscribe_topic == "bench/in"
    assert reloaded.snapshot.send_mode == MqttClientSendEncoding.ASCII

    service.shutdown()
    reloaded.shutdown()
