import asyncio

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.tcp_client import TcpClientTransportAdapter, parse_tcp_client_target
from tests.support import TcpEchoServer


def test_parse_tcp_client_target_splits_host_and_port() -> None:
    assert parse_tcp_client_target("127.0.0.1:502") == ("127.0.0.1", 502)


def test_tcp_client_transport_open_send_receive_and_close() -> None:
    with TcpEchoServer() as server:
        adapter = TcpClientTransportAdapter()
        events = []
        adapter.set_event_handler(events.append)

        async def scenario() -> None:
            await adapter.open(
                TransportConfig(
                    kind=TransportKind.TCP_CLIENT,
                    name="Bench TCP",
                    target=server.target,
                )
            )
            await adapter.send(b"PING")
            for _ in range(50):
                inbound_events = [
                    event
                    for event in events
                    if event.event_type == TransportEventType.MESSAGE
                    and event.message is not None
                    and event.message.direction == MessageDirection.INBOUND
                ]
                if inbound_events:
                    break
                await asyncio.sleep(0.02)
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
            and event.message.payload == b"PING"
            for event in message_events
        )
        inbound_payload = b"".join(
            event.message.payload
            for event in message_events
            if event.message is not None and event.message.direction == MessageDirection.INBOUND
        )
        assert inbound_payload == b"PING"
