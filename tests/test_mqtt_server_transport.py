import asyncio
import socket
import time

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.mqtt_server import MqttServerTransportAdapter, parse_mqtt_server_target
from tests.support import MqttExternalClient


def test_parse_mqtt_server_target_splits_host_and_port() -> None:
    assert parse_mqtt_server_target("127.0.0.1:1883") == ("127.0.0.1", 1883)


def _find_unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_mqtt_server_transport_start_publish_receive_and_close() -> None:
    adapter = MqttServerTransportAdapter()
    events = []
    adapter.set_event_handler(events.append)
    port = _find_unused_port()

    async def scenario() -> None:
        await adapter.open(
            TransportConfig(
                kind=TransportKind.MQTT_SERVER,
                name="Bench MQTT Server",
                target=f"127.0.0.1:{port}",
            )
        )
        with MqttExternalClient("127.0.0.1", port, client_id=f"external-mqtt-{port}") as client:
            client.subscribe("bench/topic")
            await asyncio.sleep(1.0)
            await adapter.send(b"READY", {"topic": "bench/topic"})
            await asyncio.sleep(0.5)
            topic, payload = await asyncio.to_thread(client.recv, 3.0)
            assert topic == "bench/topic"
            assert payload == b"READY"
            client.publish("bench/topic", b"PING")
            for _ in range(80):
                inbound_events = [
                    event
                    for event in events
                    if event.event_type == TransportEventType.MESSAGE
                    and event.message is not None
                    and event.message.direction == MessageDirection.INBOUND
                    and event.message.payload == b"PING"
                ]
                if inbound_events:
                    break
                await asyncio.sleep(0.05)
        await adapter.close()

    asyncio.run(scenario())

    state_events = [event for event in events if event.event_type == TransportEventType.STATE_CHANGED]
    message_events = [event for event in events if event.event_type == TransportEventType.MESSAGE]

    assert [event.session.state for event in state_events] == [
        ConnectionState.CONNECTING,
        ConnectionState.CONNECTED,
        ConnectionState.STOPPING,
        ConnectionState.DISCONNECTED,
    ]
    assert any(
        event.message is not None
        and event.message.direction == MessageDirection.OUTBOUND
        and event.message.payload == b"READY"
        for event in message_events
    )
    assert any(
        event.message is not None
        and event.message.direction == MessageDirection.INBOUND
        and event.message.payload == b"PING"
        for event in message_events
    )
