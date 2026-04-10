from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.tcp_client_profiles import (
    TcpClientDraft,
    TcpClientPreset,
    default_tcp_client_profile_path,
    load_tcp_client_profile,
    save_tcp_client_profile,
)
from protolink.core.transport import ConnectionState, TransportConfig, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout


class TcpClientSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


class TcpClientLineEnding(StrEnum):
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class TcpClientSessionSnapshot:
    host: str = "127.0.0.1"
    port: int = 502
    send_mode: TcpClientSendEncoding = TcpClientSendEncoding.HEX
    line_ending: TcpClientLineEnding = TcpClientLineEnding.NONE
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class TcpClientSessionService(MappedProfileSessionServiceBase[TcpClientSessionSnapshot, TcpClientDraft, TcpClientPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("host", "host"),
        SnapshotValueMapping("port", "port"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=TcpClientSendEncoding),
        SnapshotValueMapping("line_ending", "line_ending", encode=lambda value: value.value, decode=TcpClientLineEnding),
        SnapshotValueMapping("send_text", "send_text"),
    )

    def __init__(
        self,
        transport_registry: TransportRegistry,
        event_bus: EventBus,
        workspace: WorkspaceLayout,
    ) -> None:
        super().__init__(
            transport_registry,
            event_bus,
            transport_kind=TransportKind.TCP_CLIENT,
            initial_snapshot=TcpClientSessionSnapshot(),
            unknown_error_message="Unknown TCP client error.",
            profile_path=default_tcp_client_profile_path(workspace.profiles),
            profile_loader=load_tcp_client_profile,
            profile_saver=save_tcp_client_profile,
            draft_type=TcpClientDraft,
            preset_type=TcpClientPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )

    def set_host(self, host: str) -> None:
        self._set_snapshot(host=host.strip(), last_error=None, selected_preset_name=None)

    def set_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="TCP port must be an integer.")
            return
        if not 1 <= value <= 65535:
            self._set_snapshot(last_error="TCP port must be between 1 and 65535.")
            return
        self._set_snapshot(port=value, last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: TcpClientSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_line_ending(self, line_ending: TcpClientLineEnding) -> None:
        self._set_snapshot(line_ending=line_ending, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def open_session(self) -> None:
        if not self._snapshot.host:
            self._set_snapshot(last_error="Enter a TCP host before opening.")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.TCP_CLIENT,
                name="TCP Client",
                target=self._target(),
                options={"connect_timeout": 3.0},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if self._adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="Open the TCP client session before sending.")
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
            },
            not_connected_error="Open the TCP client session before sending.",
        )

    def _target(self) -> str:
        return f"{self._snapshot.host}:{self._snapshot.port}"

    def _encode_payload(
        self,
        text: str,
        mode: TcpClientSendEncoding,
        line_ending: TcpClientLineEnding,
    ) -> bytes:
        if not text.strip():
            raise ValueError("Enter payload text before sending.")

        if mode == TcpClientSendEncoding.UTF8:
            payload = text.encode("utf-8")
        elif mode == TcpClientSendEncoding.ASCII:
            try:
                payload = text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII payload can only contain 7-bit ASCII characters.") from exc
        else:
            try:
                payload = bytes.fromhex(text)
            except ValueError as exc:
                raise ValueError("HEX payload must contain complete hexadecimal bytes.") from exc

        return payload + {
            TcpClientLineEnding.NONE: b"",
            TcpClientLineEnding.CR: b"\r",
            TcpClientLineEnding.LF: b"\n",
            TcpClientLineEnding.CRLF: b"\r\n",
        }[line_ending]
