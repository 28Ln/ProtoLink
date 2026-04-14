from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.udp_profiles import UdpDraft, UdpPreset, default_udp_profile_path, load_udp_profile, save_udp_profile
from protolink.core.transport import ConnectionState, TransportConfig, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import display_transport_name


class UdpSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


class UdpLineEnding(StrEnum):
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class UdpSessionSnapshot:
    local_host: str = "127.0.0.1"
    local_port: int = 0
    remote_host: str = "127.0.0.1"
    remote_port: int = 502
    send_mode: UdpSendEncoding = UdpSendEncoding.HEX
    line_ending: UdpLineEnding = UdpLineEnding.NONE
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class UdpSessionService(MappedProfileSessionServiceBase[UdpSessionSnapshot, UdpDraft, UdpPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("local_host", "local_host"),
        SnapshotValueMapping("local_port", "local_port"),
        SnapshotValueMapping("remote_host", "remote_host"),
        SnapshotValueMapping("remote_port", "remote_port"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=UdpSendEncoding),
        SnapshotValueMapping("line_ending", "line_ending", encode=lambda value: value.value, decode=UdpLineEnding),
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
            transport_kind=TransportKind.UDP,
            initial_snapshot=UdpSessionSnapshot(),
            unknown_error_message="UDP 传输出现未知异常。",
            profile_path=default_udp_profile_path(workspace.profiles),
            profile_loader=load_udp_profile,
            profile_saver=save_udp_profile,
            draft_type=UdpDraft,
            preset_type=UdpPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )

    def set_local_host(self, host: str) -> None:
        self._set_snapshot(local_host=host.strip(), last_error=None, selected_preset_name=None)

    def set_local_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="UDP 本地端口必须是整数。")
            return
        if not 0 <= value <= 65535:
            self._set_snapshot(last_error="UDP 本地端口必须在 0 到 65535 之间。")
            return
        self._set_snapshot(local_port=value, last_error=None, selected_preset_name=None)

    def set_remote_host(self, host: str) -> None:
        self._set_snapshot(remote_host=host.strip(), last_error=None, selected_preset_name=None)

    def set_remote_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="UDP 远端端口必须是整数。")
            return
        if not 0 <= value <= 65535:
            self._set_snapshot(last_error="UDP 远端端口必须在 0 到 65535 之间。")
            return
        self._set_snapshot(remote_port=value, last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: UdpSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_line_ending(self, line_ending: UdpLineEnding) -> None:
        self._set_snapshot(line_ending=line_ending, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def open_session(self) -> None:
        if not self._snapshot.local_host:
            self._set_snapshot(last_error="打开前请输入 UDP 本地主机地址。")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.UDP,
                name=display_transport_name(TransportKind.UDP),
                target=self._local_target(),
                options={"remote_host": self._snapshot.remote_host, "remote_port": self._snapshot.remote_port},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if not self._snapshot.remote_host:
            self._set_snapshot(last_error="发送前请输入 UDP 远端主机地址。")
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
                "peer": self._remote_target(),
            },
            not_connected_error="发送前请先打开 UDP 传输。",
        )

    def _local_target(self) -> str:
        return f"{self._snapshot.local_host}:{self._snapshot.local_port}"

    def _remote_target(self) -> str:
        return f"{self._snapshot.remote_host}:{self._snapshot.remote_port}"

    def _encode_payload(self, text: str, mode: UdpSendEncoding, line_ending: UdpLineEnding) -> bytes:
        if not text.strip():
            raise ValueError("发送前请输入报文内容。")

        if mode == UdpSendEncoding.UTF8:
            payload = text.encode("utf-8")
        elif mode == UdpSendEncoding.ASCII:
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
            UdpLineEnding.NONE: b"",
            UdpLineEnding.CR: b"\r",
            UdpLineEnding.LF: b"\n",
            UdpLineEnding.CRLF: b"\r\n",
        }[line_ending]
