from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.tcp_server_profiles import (
    TcpServerDraft,
    TcpServerPreset,
    default_tcp_server_profile_path,
    load_tcp_server_profile,
    save_tcp_server_profile,
)
from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEvent, TransportEventType, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import display_transport_name


class TcpServerSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


class TcpServerLineEnding(StrEnum):
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class TcpServerSessionSnapshot:
    host: str = "127.0.0.1"
    port: int = 502
    send_mode: TcpServerSendEncoding = TcpServerSendEncoding.HEX
    line_ending: TcpServerLineEnding = TcpServerLineEnding.NONE
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    client_count: int = 0
    connected_clients: tuple[str, ...] = ()
    selected_client_peer: str | None = None
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class TcpServerSessionService(MappedProfileSessionServiceBase[TcpServerSessionSnapshot, TcpServerDraft, TcpServerPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("host", "host"),
        SnapshotValueMapping("port", "port"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=TcpServerSendEncoding),
        SnapshotValueMapping("line_ending", "line_ending", encode=lambda value: value.value, decode=TcpServerLineEnding),
        SnapshotValueMapping("send_text", "send_text"),
    )

    def __init__(self, transport_registry: TransportRegistry, event_bus: EventBus, workspace: WorkspaceLayout) -> None:
        super().__init__(
            transport_registry,
            event_bus,
            transport_kind=TransportKind.TCP_SERVER,
            initial_snapshot=TcpServerSessionSnapshot(),
            unknown_error_message="TCP 服务端出现未知异常。",
            profile_path=default_tcp_server_profile_path(workspace.profiles),
            profile_loader=load_tcp_server_profile,
            profile_saver=save_tcp_server_profile,
            draft_type=TcpServerDraft,
            preset_type=TcpServerPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )

    def set_host(self, host: str) -> None:
        self._set_snapshot(host=host.strip(), last_error=None, selected_preset_name=None)

    def set_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="TCP 服务端端口必须是整数。")
            return
        if not 0 <= value <= 65535:
            self._set_snapshot(last_error="TCP 服务端端口必须在 0 到 65535 之间。")
            return
        self._set_snapshot(port=value, last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: TcpServerSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_line_ending(self, line_ending: TcpServerLineEnding) -> None:
        self._set_snapshot(line_ending=line_ending, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def set_selected_client_peer(self, peer: str | None) -> None:
        self._set_snapshot(selected_client_peer=peer, last_error=None)

    def open_session(self) -> None:
        if not self._snapshot.host:
            self._set_snapshot(last_error="打开前请输入 TCP 服务端主机地址。")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.TCP_SERVER,
                name=display_transport_name(TransportKind.TCP_SERVER),
                target=self._target(),
                options={"read_size": 4096},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if self._snapshot.client_count <= 0:
            self._set_snapshot(last_error="当前没有已连接的 TCP 客户端。")
            return
        if self._adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="发送前请先打开 TCP 服务端。")
            return

        if self._snapshot.selected_client_peer and self._snapshot.selected_client_peer not in self._snapshot.connected_clients:
            self._set_snapshot(last_error=f"TCP 客户端“{self._snapshot.selected_client_peer}”已断开连接。")
            return

        try:
            payload = self._encode_payload(self._snapshot.send_text, self._snapshot.send_mode, self._snapshot.line_ending)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        self._send_payload(
            payload,
            {
                "encoding": self._snapshot.send_mode.value,
                "line_ending": self._snapshot.line_ending.value,
                "client_count": str(self._snapshot.client_count),
                "peer": self._snapshot.selected_client_peer or "broadcast",
            },
            not_connected_error="发送前请先打开 TCP 服务端。",
        )

    def _target(self) -> str:
        return f"{self._snapshot.host}:{self._snapshot.port}"

    def _handle_transport_event(self, event: TransportEvent) -> None:
        if (
            event.session.kind == TransportKind.TCP_SERVER
            and self._adapter is not None
            and self._adapter.session is not None
            and event.session.session_id == self._adapter.session.session_id
            and event.message is not None
            and event.message.direction == MessageDirection.INTERNAL
        ):
            raw_count = event.message.metadata.get("client_count", str(self._snapshot.client_count))
            try:
                client_count = int(raw_count)
            except ValueError:
                client_count = self._snapshot.client_count
            connected_clients = self._update_connected_clients(event.message.metadata.get("event"), event.message.metadata.get("peer"))
            selected_client_peer = self._snapshot.selected_client_peer
            if selected_client_peer and selected_client_peer not in connected_clients:
                selected_client_peer = None
            self._set_snapshot(
                client_count=client_count,
                connected_clients=connected_clients,
                selected_client_peer=selected_client_peer,
            )
        super()._handle_transport_event(event)
        if (
            event.session.kind == TransportKind.TCP_SERVER
            and event.event_type == TransportEventType.STATE_CHANGED
            and event.session.state == ConnectionState.DISCONNECTED
        ):
            self._set_snapshot(client_count=0, connected_clients=(), selected_client_peer=None)

    def _encode_payload(
        self,
        text: str,
        mode: TcpServerSendEncoding,
        line_ending: TcpServerLineEnding,
    ) -> bytes:
        if not text.strip():
            raise ValueError("发送前请输入报文内容。")

        if mode == TcpServerSendEncoding.UTF8:
            payload = text.encode("utf-8")
        elif mode == TcpServerSendEncoding.ASCII:
            try:
                payload = text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII 报文只能包含 7 位 ASCII 字符。") from exc
        else:
            try:
                payload = bytes.fromhex(text)
            except ValueError as exc:
                raise ValueError("HEX 报文必须由完整的十六进制字节组成。") from exc

        return payload + {
            TcpServerLineEnding.NONE: b"",
            TcpServerLineEnding.CR: b"\r",
            TcpServerLineEnding.LF: b"\n",
            TcpServerLineEnding.CRLF: b"\r\n",
        }[line_ending]

    def _update_connected_clients(self, event_name: str | None, peer: str | None) -> tuple[str, ...]:
        clients = list(self._snapshot.connected_clients)
        if event_name == "client_connected" and peer:
            if peer not in clients:
                clients.append(peer)
        elif event_name == "client_disconnected" and peer:
            clients = [item for item in clients if item != peer]
        return tuple(sorted(clients))
