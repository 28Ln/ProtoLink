import socket
import time
from pathlib import Path

from protolink.application.mqtt_server_service import MqttServerSendEncoding
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.transport import ConnectionState
from tests.support import MqttExternalClient


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


def test_mqtt_server_service_start_publish_receive_and_close(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_server_service
    port = _find_unused_port()
    service.set_host("127.0.0.1")
    service.set_port(port)
    service.set_publish_topic("bench/topic")
    service.set_send_mode(MqttServerSendEncoding.ASCII)
    service.set_send_text("READY")

    service.open_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.CONNECTED)

    with MqttExternalClient("127.0.0.1", port, client_id="external-mqtt") as client:
        client.subscribe("bench/topic")
        time.sleep(0.2)
        service.send_current_payload()
        time.sleep(0.5)
        topic, payload = client.recv(timeout=3.0)
        assert topic == "bench/topic"
        assert payload == b"READY"
        client.publish("bench/topic", b"PING")
        _wait_until(lambda: len([entry for entry in context.log_store.latest(20) if entry.category == "transport.message"]) >= 2)
        assert context.packet_inspector.rows()

    service.close_session()
    _wait_until(lambda: service.snapshot.connection_state == ConnectionState.DISCONNECTED)
    service.shutdown()


def test_mqtt_server_service_surfaces_open_errors(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_server_service
    port = _find_unused_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        service.set_host("127.0.0.1")
        service.set_port(port)
        service.open_session()
        _wait_until(lambda: service.snapshot.connection_state == ConnectionState.ERROR, timeout=8.0)
        assert service.snapshot.last_error is not None
        assert any(entry.category == "transport.error" for entry in context.log_store.latest(10))
    finally:
        blocker.close()
        service.shutdown()


def test_mqtt_server_service_persists_presets_and_restores_publish_topic(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    service = context.mqtt_server_service
    service.set_host("127.0.0.1")
    service.set_port(1884)
    service.set_publish_topic("bench/out")
    service.set_send_mode(MqttServerSendEncoding.ASCII)
    service.set_send_text("READY")
    service.save_preset("Bench Broker")

    reloaded_context = bootstrap_app_context(tmp_path, persist_settings=False)
    reloaded = reloaded_context.mqtt_server_service
    assert reloaded.snapshot.preset_names == ("Bench Broker",)
    reloaded.load_preset("Bench Broker")

    assert reloaded.snapshot.selected_preset_name == "Bench Broker"
    assert reloaded.snapshot.publish_topic == "bench/out"
    assert reloaded.snapshot.send_mode == MqttServerSendEncoding.ASCII
    assert reloaded.snapshot.send_text == "READY"

    service.shutdown()
    reloaded.shutdown()
