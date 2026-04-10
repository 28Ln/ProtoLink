import asyncio
import socket

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.udp import UdpTransportAdapter, parse_udp_target
from tests.support import UdpEchoServer


def test_parse_udp_target_splits_host_and_port() -> None:
    endpoint = parse_udp_target("127.0.0.1:502")
    assert endpoint.host == "127.0.0.1"
    assert endpoint.port == 502


def test_udp_transport_open_send_receive_and_close() -> None:
    with UdpEchoServer() as server:
        adapter = UdpTransportAdapter()
        events = []
        adapter.set_event_handler(events.append)

        async def scenario() -> None:
            await adapter.open(
                TransportConfig(
                    kind=TransportKind.UDP,
                    name="Bench UDP",
                    target="127.0.0.1:0",
                    options={"remote_host": server.host, "remote_port": server.port},
                )
            )
            await adapter.send(b"PING")
            for _ in range(60):
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
        assert any(
            event.message is not None
            and event.message.direction == MessageDirection.INBOUND
            and event.message.payload == b"PING"
            for event in message_events
        )
