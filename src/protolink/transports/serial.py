from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from serial import serial_for_url
from serial.tools import list_ports

from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportKind,
)


def _default_serial_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.SERIAL,
        display_name="Serial Studio",
        capabilities=TransportCapabilities(supports_binary_payloads=True, supports_reconnect=True),
    )


@dataclass(frozen=True, slots=True)
class SerialPortSummary:
    device: str
    description: str
    hardware_id: str


@dataclass(frozen=True, slots=True)
class SerialPortSettings:
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.1
    write_timeout: float = 1.0
    xonxoff: bool = False
    rtscts: bool = False
    dsrdtr: bool = False

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "SerialPortSettings":
        options = dict(config.options)
        return cls(
            baudrate=_coerce_int(options, "baudrate", 9600),
            bytesize=_coerce_int(options, "bytesize", 8),
            parity=_coerce_str(options, "parity", "N").upper(),
            stopbits=_coerce_float(options, "stopbits", 1.0),
            timeout=_coerce_float(options, "timeout", 0.1),
            write_timeout=_coerce_float(options, "write_timeout", 1.0),
            xonxoff=_coerce_bool(options, "xonxoff", False),
            rtscts=_coerce_bool(options, "rtscts", False),
            dsrdtr=_coerce_bool(options, "dsrdtr", False),
        )

    def to_pyserial_kwargs(self) -> dict[str, Any]:
        return {
            "baudrate": self.baudrate,
            "bytesize": self.bytesize,
            "parity": self.parity,
            "stopbits": self.stopbits,
            "timeout": self.timeout,
            "write_timeout": self.write_timeout,
            "xonxoff": self.xonxoff,
            "rtscts": self.rtscts,
            "dsrdtr": self.dsrdtr,
        }


def list_serial_ports() -> list[SerialPortSummary]:
    ports = [
        SerialPortSummary(
            device=port.device,
            description=getattr(port, "description", "") or port.device,
            hardware_id=getattr(port, "hwid", ""),
        )
        for port in list_ports.comports()
    ]
    return sorted(ports, key=lambda port: port.device)


class SerialTransportAdapter(TransportAdapter):
    def __init__(
        self,
        descriptor: TransportDescriptor | None = None,
        *,
        serial_factory: Callable[..., Any] = serial_for_url,
    ) -> None:
        super().__init__(descriptor or _default_serial_descriptor())
        self._serial_factory = serial_factory
        self._serial_handle: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_stop = threading.Event()
        self._coalesce_window = 0.02

    async def open(self, config: TransportConfig) -> None:
        if self._serial_handle is not None:
            raise RuntimeError("Serial transport is already open.")

        settings = SerialPortSettings.from_transport_config(config)
        self.bind_session(config)
        self._loop = asyncio.get_running_loop()
        self.emit_state(ConnectionState.CONNECTING)

        try:
            self._serial_handle = await asyncio.to_thread(
                self._serial_factory,
                config.target,
                **settings.to_pyserial_kwargs(),
            )
        except Exception as exc:
            self.emit_error(str(exc))
            raise

        self._reader_stop = threading.Event()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"ProtoLinkSerialReader-{self.session.session_id[:8]}",
            daemon=True,
        )
        self._reader_thread.start()
        self.emit_state(ConnectionState.CONNECTED)

    async def close(self) -> None:
        if self.session is None:
            return

        if self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.STOPPING)

        self._reader_stop.set()
        serial_handle = self._serial_handle
        if serial_handle is not None:
            await asyncio.to_thread(serial_handle.close)
        reader_thread = self._reader_thread
        if reader_thread is not None and reader_thread.is_alive():
            reader_thread.join(timeout=1.0)

        self._serial_handle = None
        self._reader_thread = None
        self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        serial_handle = self._require_serial_handle()
        self.emit_message(MessageDirection.OUTBOUND, payload, metadata)
        await asyncio.to_thread(serial_handle.write, payload)
        flush = getattr(serial_handle, "flush", None)
        if callable(flush):
            await asyncio.to_thread(flush)

    def _require_serial_handle(self) -> Any:
        if self._serial_handle is None:
            raise RuntimeError("Serial transport is not open.")
        return self._serial_handle

    def _reader_loop(self) -> None:
        while not self._reader_stop.is_set():
            serial_handle = self._serial_handle
            if serial_handle is None:
                return

            read_size = max(1, min(4096, int(getattr(serial_handle, "in_waiting", 0) or 1)))
            try:
                payload = serial_handle.read(read_size)
            except Exception as exc:
                if self._reader_stop.is_set():
                    return
                self._schedule(self.emit_error, str(exc))
                return

            if not payload:
                continue

            payload = self._coalesce_payload(serial_handle, payload)
            self._schedule(self.emit_message, MessageDirection.INBOUND, payload, {"source": "serial"})

    def _schedule(self, callback: Callable[..., None], *args: Any) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(callback, *args)

    def _coalesce_payload(self, serial_handle: Any, payload: bytes) -> bytes:
        buffer = bytearray(payload)
        idle_deadline = time.monotonic() + self._coalesce_window

        while not self._reader_stop.is_set() and time.monotonic() < idle_deadline:
            waiting = int(getattr(serial_handle, "in_waiting", 0) or 0)
            if waiting <= 0:
                time.sleep(0.005)
                continue

            buffer.extend(serial_handle.read(min(4096, waiting)))
            idle_deadline = time.monotonic() + self._coalesce_window

        return bytes(buffer)


def _coerce_int(options: Mapping[str, object], key: str, default: int) -> int:
    value = options.get(key, default)
    if value is None:
        return default
    return int(value)


def _coerce_float(options: Mapping[str, object], key: str, default: float) -> float:
    value = options.get(key, default)
    if value is None:
        return default
    return float(value)


def _coerce_str(options: Mapping[str, object], key: str, default: str) -> str:
    value = options.get(key, default)
    if value is None:
        return default
    return str(value)


def _coerce_bool(options: Mapping[str, object], key: str, default: bool) -> bool:
    value = options.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
