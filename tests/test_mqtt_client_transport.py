import asyncio

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.mqtt_client import MqttClientTransportAdapter, parse_mqtt_client_target
from tests.support import MqttTestBroker


def test_parse_mqtt_client_target_splits_host_and_port() -> None:
    assert parse_mqtt_client_target("127.0.0.1:1883") == ("127.0.0.1", 1883)


def test_mqtt_client_transport_connect_subscribe_publish_receive_and_close() -> None:
    with MqttTestBroker() as broker:
        adapter = MqttClientTransportAdapter()
        events = []
        adapter.set_event_handler(events.append)

        async def scenario() -> None:
            await adapter.open(
                TransportConfig(
                    kind=TransportKind.MQTT_CLIENT,
                    name="Bench MQTT",
                    target=broker.target,
                    options={"client_id": "bench-mqtt"},
                )
            )
            await adapter.subscribe("bench/topic")
            await adapter.send(b"PING", {"topic": "bench/topic"})
            for _ in range(80):
                inbound_events = [
                    event
                    for event in events
                    if event.event_type == TransportEventType.MESSAGE
                    and event.message is not None
                    and event.message.direction == MessageDirection.INBOUND
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
            and event.message.direction == MessageDirection.INTERNAL
            and event.message.metadata.get("event") == "subscribed"
            for event in message_events
        )
        assert any(
            event.message is not None
            and event.message.direction == MessageDirection.OUTBOUND
            and event.message.payload == b"PING"
            for event in message_events
        )
        assert any(
            event.message is not None
            and event.message.direction == MessageDirection.INBOUND
            and event.message.payload == b"PING"
            for event in message_events
        )
