from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass

from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportKind,
    TransportSession,
)
from protolink.presentation import display_transport_name


def _default_udp_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.UDP,
        display_name=display_transport_name(TransportKind.UDP),
        capabilities=TransportCapabilities(can_listen=True, supports_binary_payloads=True),
    )


@dataclass(frozen=True, slots=True)
class UdpEndpoint:
    host: str
    port: int

    def render(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class UdpTransportSettings:
    local_endpoint: UdpEndpoint
    remote_endpoint: UdpEndpoint | None = None

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "UdpTransportSettings":
        options = dict(config.options)
        remote_host = options.get("remote_host")
        remote_port = options.get("remote_port")
        remote_endpoint = None
        if remote_host and remote_port is not None:
            remote_endpoint = UdpEndpoint(str(remote_host), int(remote_port))
        return cls(
            local_endpoint=parse_udp_target(config.target),
            remote_endpoint=remote_endpoint,
        )


def parse_udp_target(target: str) -> UdpEndpoint:
    host, separator, port_text = target.strip().rpartition(":")
    if separator != ":" or not host or not port_text:
        raise ValueError("UDP 目标必须使用 host:port 格式。")

    port = int(port_text)
    if not 0 <= port <= 65535:
        raise ValueError("UDP 端口必须在 0 到 65535 之间。")
    return UdpEndpoint(host, port)


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, adapter: "UdpTransportAdapter") -> None:
        self.adapter = adapter

    def datagram_received(self, data: bytes, addr) -> None:
        peer = f"{addr[0]}:{addr[1]}" if isinstance(addr, tuple) and len(addr) >= 2 else "未知"
        self.adapter.emit_message(
            MessageDirection.INBOUND,
            bytes(data),
            {"source": "udp", "peer": peer},
        )

    def error_received(self, exc: Exception | None) -> None:
        if exc is not None:
            self.adapter.emit_error(str(exc))

    def connection_lost(self, exc: Exception | None) -> None:
        if exc is not None and not self.adapter._closing:
            self.adapter.emit_error(str(exc))
            return
        if not self.adapter._closing and self.adapter.session is not None and self.adapter.session.state != ConnectionState.DISCONNECTED:
            self.adapter.emit_state(ConnectionState.DISCONNECTED)


class UdpTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor | None = None) -> None:
        super().__init__(descriptor or _default_udp_descriptor())
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._remote_endpoint: UdpEndpoint | None = None
        self._closing = False

    async def open(self, config: TransportConfig) -> None:
        if self._transport is not None:
            raise RuntimeError("UDP 传输已打开。")

        settings = UdpTransportSettings.from_transport_config(config)
        self.bind_session(config)
        self._remote_endpoint = settings.remote_endpoint
        self.emit_state(ConnectionState.CONNECTING)

        loop = asyncio.get_running_loop()
        try:
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _UdpProtocol(self),
                local_addr=(settings.local_endpoint.host, settings.local_endpoint.port),
            )
        except Exception as exc:
            self.emit_error(str(exc))
            raise

        self._transport = transport
        self._protocol = protocol
        self._closing = False
        self._sync_bound_target()
        self.emit_state(ConnectionState.CONNECTED)

    async def close(self) -> None:
        if self.session is None:
            return

        if self.session.state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPING}:
            self.emit_state(ConnectionState.STOPPING)

        self._closing = True
        transport = self._transport
        self._transport = None
        self._protocol = None
        if transport is not None:
            transport.close()

        if self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        transport = self._require_transport()
        remote_endpoint = self._require_remote_endpoint()
        outbound_metadata = dict(metadata or {})
        outbound_metadata.setdefault("peer", remote_endpoint.render())
        self.emit_message(MessageDirection.OUTBOUND, payload, outbound_metadata)
        transport.sendto(payload, (remote_endpoint.host, remote_endpoint.port))

    def _require_transport(self) -> asyncio.DatagramTransport:
        if self._transport is None:
            raise RuntimeError("UDP 传输未打开。")
        return self._transport

    def _require_remote_endpoint(self) -> UdpEndpoint:
        if self._remote_endpoint is None:
            raise RuntimeError("UDP 远端端点尚未配置。")
        return self._remote_endpoint

    def _sync_bound_target(self) -> None:
        if self._transport is None or self._session is None:
            return
        sockname = self._transport.get_extra_info("sockname")
        if isinstance(sockname, tuple) and len(sockname) >= 2:
            self._session = TransportSession(
                session_id=self._session.session_id,
                kind=self._session.kind,
                name=self._session.name,
                target=f"{sockname[0]}:{sockname[1]}",
                state=self._session.state,
            )
