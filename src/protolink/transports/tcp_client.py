from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass

from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportKind,
)
from protolink.presentation import display_transport_name


def _default_tcp_client_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.TCP_CLIENT,
        display_name=display_transport_name(TransportKind.TCP_CLIENT),
        capabilities=TransportCapabilities(supports_binary_payloads=True, supports_tls=True),
    )


@dataclass(frozen=True, slots=True)
class TcpClientConnectionSettings:
    host: str
    port: int
    connect_timeout: float = 3.0
    read_size: int = 4096

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "TcpClientConnectionSettings":
        host, port = parse_tcp_client_target(config.target)
        options = dict(config.options)
        return cls(
            host=host,
            port=port,
            connect_timeout=float(options.get("connect_timeout", 3.0) or 3.0),
            read_size=max(1, int(options.get("read_size", 4096) or 4096)),
        )


def parse_tcp_client_target(target: str) -> tuple[str, int]:
    host, separator, port_text = target.strip().rpartition(":")
    if separator != ":" or not host or not port_text:
        raise ValueError("TCP 客户端目标必须使用 host:port 格式。")

    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("TCP 客户端端口必须在 1 到 65535 之间。")
    return host, port


class TcpClientTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor | None = None) -> None:
        super().__init__(descriptor or _default_tcp_client_descriptor())
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._closing = False
        self._read_size = 4096

    async def open(self, config: TransportConfig) -> None:
        if self._writer is not None:
            raise RuntimeError("TCP 客户端传输已打开。")

        settings = TcpClientConnectionSettings.from_transport_config(config)
        self.bind_session(config)
        self._read_size = settings.read_size
        self.emit_state(ConnectionState.CONNECTING)

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(settings.host, settings.port),
                timeout=settings.connect_timeout,
            )
        except Exception as exc:
            self.emit_error(str(exc))
            raise

        self._closing = False
        self._reader_task = asyncio.create_task(self._reader_loop())
        self.emit_state(ConnectionState.CONNECTED)

    async def close(self) -> None:
        if self.session is None:
            return

        if self.session.state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPING}:
            self.emit_state(ConnectionState.STOPPING)

        self._closing = True
        writer = self._writer
        reader_task = self._reader_task

        if writer is not None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

        if reader_task is not None and reader_task is not asyncio.current_task():
            reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await reader_task

        self._reader = None
        self._writer = None
        self._reader_task = None

        if self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        writer = self._require_writer()
        outbound_metadata = dict(metadata or {})
        if self.session is not None:
            outbound_metadata.setdefault("peer", self.session.target)
        self.emit_message(MessageDirection.OUTBOUND, payload, outbound_metadata)
        writer.write(payload)
        await writer.drain()

    def _require_writer(self) -> asyncio.StreamWriter:
        if self._writer is None:
            raise RuntimeError("TCP 客户端传输未打开。")
        return self._writer

    async def _reader_loop(self) -> None:
        try:
            while True:
                reader = self._reader
                if reader is None:
                    return

                payload = await reader.read(self._read_size)
                if not payload:
                    break

                inbound_metadata = {"source": "tcp_client"}
                if self.session is not None:
                    inbound_metadata["peer"] = self.session.target
                self.emit_message(MessageDirection.INBOUND, bytes(payload), inbound_metadata)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closing:
                self.emit_error(str(exc))
            return

        if not self._closing and self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)
