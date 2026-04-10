import asyncio
from types import SimpleNamespace

from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEventType, TransportKind
from protolink.transports.serial import SerialPortSettings, SerialTransportAdapter, list_serial_ports


def test_serial_port_settings_are_coerced_from_transport_options() -> None:
    config = TransportConfig(
        kind=TransportKind.SERIAL,
        name="Bench Port",
        target="COM7",
        options={
            "baudrate": "19200",
            "bytesize": "7",
            "parity": "e",
            "stopbits": "2",
            "timeout": "0.25",
            "write_timeout": "2.0",
            "xonxoff": "true",
        },
    )

    settings = SerialPortSettings.from_transport_config(config)

    assert settings.baudrate == 19200
    assert settings.bytesize == 7
    assert settings.parity == "E"
    assert settings.stopbits == 2.0
    assert settings.timeout == 0.25
    assert settings.write_timeout == 2.0
    assert settings.xonxoff is True


def test_list_serial_ports_maps_pyserial_port_metadata(monkeypatch) -> None:
    fake_ports = [
        SimpleNamespace(device="COM9", description="Bench Port", hwid="USB VID:PID=1234:5678"),
        SimpleNamespace(device="COM3", description="", hwid="ACME"),
    ]

    monkeypatch.setattr("protolink.transports.serial.list_ports.comports", lambda: fake_ports)

    ports = list_serial_ports()

    assert [port.device for port in ports] == ["COM3", "COM9"]
    assert ports[0].description == "COM3"
    assert ports[1].hardware_id == "USB VID:PID=1234:5678"


def test_serial_transport_loopback_open_send_receive_and_close() -> None:
    adapter = SerialTransportAdapter()
    events = []
    adapter.set_event_handler(events.append)

    async def scenario() -> None:
        await adapter.open(
            TransportConfig(
                kind=TransportKind.SERIAL,
                name="Loopback Port",
                target="loop://",
                options={"timeout": 0.05},
            )
        )
        await adapter.send(b"\x01\x03\x00\x01", {"encoding": "hex"})
        await asyncio.sleep(0.15)
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
    assert [event.message.direction for event in message_events] == [
        MessageDirection.OUTBOUND,
        MessageDirection.INBOUND,
    ]
    assert message_events[0].message.payload == b"\x01\x03\x00\x01"
    assert message_events[0].message.metadata["encoding"] == "hex"
    assert message_events[1].message.payload == b"\x01\x03\x00\x01"
