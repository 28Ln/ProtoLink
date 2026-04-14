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
    TransportSession,
)
from protolink.presentation import display_transport_name


def _default_tcp_server_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.TCP_SERVER,
        display_name=display_transport_name(TransportKind.TCP_SERVER),
        capabilities=TransportCapabilities(can_listen=True, can_accept_clients=True, supports_binary_payloads=True),
    )


@dataclass(frozen=True, slots=True)
class TcpServerConnectionSettings:
    host: str
    port: int
    read_size: int = 4096

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "TcpServerConnectionSettings":
        host, port = parse_tcp_server_target(config.target)
        options = dict(config.options)
        return cls(
            host=host,
            port=port,
            read_size=max(1, int(options.get("read_size", 4096) or 4096)),
        )


def parse_tcp_server_target(target: str) -> tuple[str, int]:
    host, separator, port_text = target.strip().rpartition(":")
    if separator != ":" or not host or not port_text:
        raise ValueError("TCP 服务端目标必须使用 host:port 格式。")

    port = int(port_text)
    if not 0 <= port <= 65535:
        raise ValueError("TCP 服务端端口必须在 0 到 65535 之间。")
    return host, port


class TcpServerTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor | None = None) -> None:
        super().__init__(descriptor or _default_tcp_server_descriptor())
        self._server: asyncio.AbstractServer | None = None
        self._client_writers: dict[str, asyncio.StreamWriter] = {}
        self._client_tasks: set[asyncio.Task[None]] = set()
        self._closing = False
        self._read_size = 4096

    async def open(self, config: TransportConfig) -> None:
        if self._server is not None:
            raise RuntimeError("TCP 服务端传输已打开。")

        settings = TcpServerConnectionSettings.from_transport_config(config)
        self.bind_session(config)
        self._read_size = settings.read_size
        self.emit_state(ConnectionState.CONNECTING)

        try:
            self._server = await asyncio.start_server(self._handle_client, settings.host, settings.port)
        except Exception as exc:
            self.emit_error(str(exc))
            raise

        self._closing = False
        self._sync_bound_target()
        self.emit_state(ConnectionState.CONNECTED)

    async def close(self) -> None:
        if self.session is None:
            return

        if self.session.state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPING}:
            self.emit_state(ConnectionState.STOPPING)

        self._closing = True
        server = self._server
        if server is not None:
            server.close()
            with suppress(Exception):
                await server.wait_closed()

        client_tasks = list(self._client_tasks)
        for task in client_tasks:
            task.cancel()
        for task in client_tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task

        writers = list(self._client_writers.values())
        for writer in writers:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

        self._client_tasks.clear()
        self._client_writers.clear()
        self._server = None

        if self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        if self._server is None:
            raise RuntimeError("TCP 服务端传输未打开。")

        outbound_metadata = dict(metadata or {})
        outbound_metadata.setdefault("client_count", str(len(self._client_writers)))
        target_peer = outbound_metadata.get("peer")
        if target_peer == "broadcast":
            target_peer = None
        writers: list[tuple[str, asyncio.StreamWriter]]
        if target_peer:
            try:
                writers = [(target_peer, self._client_writers[target_peer])]
            except KeyError as exc:
                raise RuntimeError(f"TCP 服务端客户端“{target_peer}”未连接。") from exc
        else:
            writers = list(self._client_writers.items())
            outbound_metadata.setdefault("peer", "broadcast")
        self.emit_message(MessageDirection.OUTBOUND, payload, outbound_metadata)

        for peer, writer in writers:
            try:
                writer.write(payload)
                await writer.drain()
            except Exception:
                await self._drop_client(peer)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = self._peer_label(writer)
        self._client_writers[peer] = writer
        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)
        self.emit_message(
            MessageDirection.INTERNAL,
            b"",
            {"event": "client_connected", "peer": peer, "client_count": str(len(self._client_writers))},
        )

        try:
            while True:
                payload = await reader.read(self._read_size)
                if not payload:
                    break
                self.emit_message(
                    MessageDirection.INBOUND,
                    bytes(payload),
                    {"source": "tcp_server", "peer": peer, "client_count": str(len(self._client_writers))},
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closing:
                self.emit_message(
                    MessageDirection.INTERNAL,
                    b"",
                    {"event": "client_error", "peer": peer, "error": str(exc)},
                )
        finally:
            await self._drop_client(peer)
            if task is not None:
                self._client_tasks.discard(task)

    async def _drop_client(self, peer: str) -> None:
        writer = self._client_writers.pop(peer, None)
        if writer is not None:
            self.emit_message(
                MessageDirection.INTERNAL,
                b"",
                {"event": "client_disconnected", "peer": peer, "client_count": str(len(self._client_writers))},
            )
        if writer is None:
            return
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    def _peer_label(self, writer: asyncio.StreamWriter) -> str:
        peer = writer.get_extra_info("peername")
        if isinstance(peer, tuple) and len(peer) >= 2:
            return f"{peer[0]}:{peer[1]}"
        return "未知"

    def _sync_bound_target(self) -> None:
        if self._server is None or self._session is None or not self._server.sockets:
            return
        sockname = self._server.sockets[0].getsockname()
        if isinstance(sockname, tuple) and len(sockname) >= 2:
            self._session = TransportSession(
                session_id=self._session.session_id,
                kind=self._session.kind,
                name=self._session.name,
                target=f"{sockname[0]}:{sockname[1]}",
                state=self._session.state,
            )
