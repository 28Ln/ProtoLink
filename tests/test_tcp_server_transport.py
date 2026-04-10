import asyncio
import socket

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.tcp_server import TcpServerTransportAdapter, parse_tcp_server_target
from tests.support import TcpSocketClient


def test_parse_tcp_server_target_splits_host_and_port() -> None:
    assert parse_tcp_server_target("127.0.0.1:502") == ("127.0.0.1", 502)


def test_tcp_server_transport_open_receive_send_and_close() -> None:
    adapter = TcpServerTransportAdapter()
    events = []
    adapter.set_event_handler(events.append)

    async def scenario() -> None:
        await adapter.open(
            TransportConfig(
                kind=TransportKind.TCP_SERVER,
                name="Bench TCP Server",
                target="127.0.0.1:0",
            )
        )
        assert adapter.session is not None
        host, port = parse_tcp_server_target(adapter.session.target)
        with TcpSocketClient(host, port) as client:
            await asyncio.sleep(0.05)
            client.send(b"PING")
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
            await adapter.send(b"PONG")
            assert client.recv() == b"PONG"
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
        and event.message.direction == MessageDirection.INBOUND
        and event.message.payload == b"PING"
        for event in message_events
    )
    assert any(
        event.message is not None
        and event.message.direction == MessageDirection.OUTBOUND
        and event.message.payload == b"PONG"
        for event in message_events
    )


def test_tcp_server_transport_can_target_single_client() -> None:
    adapter = TcpServerTransportAdapter()

    async def scenario() -> None:
        await adapter.open(
            TransportConfig(
                kind=TransportKind.TCP_SERVER,
                name="Bench TCP Server",
                target="127.0.0.1:0",
            )
        )
        assert adapter.session is not None
        host, port = parse_tcp_server_target(adapter.session.target)
        with TcpSocketClient(host, port) as client_a, TcpSocketClient(host, port) as client_b:
            await asyncio.sleep(0.05)
            peer_a = f"{client_a._socket.getsockname()[0]}:{client_a._socket.getsockname()[1]}"
            await adapter.send(b"A-ONLY", {"peer": peer_a})
            assert client_a.recv() == b"A-ONLY"
            client_b._socket.settimeout(0.2)
            try:
                payload = client_b.recv()
            except (TimeoutError, socket.timeout):
                payload = b""
            assert payload == b""
        await adapter.close()

    asyncio.run(scenario())
