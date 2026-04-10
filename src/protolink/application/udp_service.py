from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.udp_profiles import UdpDraft, UdpPreset, default_udp_profile_path, load_udp_profile, save_udp_profile
from protolink.core.transport import ConnectionState, TransportConfig, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout


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
            unknown_error_message="Unknown UDP transport error.",
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
            self._set_snapshot(last_error="UDP local port must be an integer.")
            return
        if not 0 <= value <= 65535:
            self._set_snapshot(last_error="UDP local port must be between 0 and 65535.")
            return
        self._set_snapshot(local_port=value, last_error=None, selected_preset_name=None)

    def set_remote_host(self, host: str) -> None:
        self._set_snapshot(remote_host=host.strip(), last_error=None, selected_preset_name=None)

    def set_remote_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="UDP remote port must be an integer.")
            return
        if not 0 <= value <= 65535:
            self._set_snapshot(last_error="UDP remote port must be between 0 and 65535.")
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
            self._set_snapshot(last_error="Enter a UDP local host before opening.")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.UDP,
                name="UDP Lab",
                target=self._local_target(),
                options={"remote_host": self._snapshot.remote_host, "remote_port": self._snapshot.remote_port},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if not self._snapshot.remote_host:
            self._set_snapshot(last_error="Enter a UDP remote host before sending.")
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
            not_connected_error="Open the UDP transport before sending.",
        )

    def _local_target(self) -> str:
        return f"{self._snapshot.local_host}:{self._snapshot.local_port}"

    def _remote_target(self) -> str:
        return f"{self._snapshot.remote_host}:{self._snapshot.remote_port}"

    def _encode_payload(self, text: str, mode: UdpSendEncoding, line_ending: UdpLineEnding) -> bytes:
        if not text.strip():
            raise ValueError("Enter payload text before sending.")

        if mode == UdpSendEncoding.UTF8:
            payload = text.encode("utf-8")
        elif mode == UdpSendEncoding.ASCII:
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
            UdpLineEnding.NONE: b"",
            UdpLineEnding.CR: b"\r",
            UdpLineEnding.LF: b"\n",
            UdpLineEnding.CRLF: b"\r\n",
        }[line_ending]
