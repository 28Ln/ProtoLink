from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.serial_profiles import (
    SerialStudioDraft,
    SerialStudioPreset,
    default_serial_studio_profile_path,
    load_serial_studio_profile,
    save_serial_studio_profile,
)
from protolink.core.transport import ConnectionState, TransportConfig, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import display_transport_name
from protolink.transports.serial import SerialPortSummary, list_serial_ports


class SerialSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


class SerialLineEnding(StrEnum):
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class SerialSessionSnapshot:
    available_ports: tuple[SerialPortSummary, ...] = ()
    target: str = ""
    baudrate: int = 9600
    send_mode: SerialSendEncoding = SerialSendEncoding.HEX
    line_ending: SerialLineEnding = SerialLineEnding.NONE
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class SerialSessionService(MappedProfileSessionServiceBase[SerialSessionSnapshot, SerialStudioDraft, SerialStudioPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("target", "target"),
        SnapshotValueMapping("baudrate", "baudrate"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=SerialSendEncoding),
        SnapshotValueMapping("line_ending", "line_ending", encode=lambda value: value.value, decode=SerialLineEnding),
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
            transport_kind=TransportKind.SERIAL,
            initial_snapshot=SerialSessionSnapshot(),
            unknown_error_message="串口传输出现未知异常。",
            profile_path=default_serial_studio_profile_path(workspace.profiles),
            profile_loader=load_serial_studio_profile,
            profile_saver=save_serial_studio_profile,
            draft_type=SerialStudioDraft,
            preset_type=SerialStudioPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )
        self.refresh_ports()

    def refresh_ports(self) -> None:
        available_ports = tuple(list_serial_ports())
        target = self._snapshot.target
        if not target and available_ports:
            target = available_ports[0].device
        self._set_snapshot(available_ports=available_ports, target=target)

    def set_target(self, target: str) -> None:
        self._set_snapshot(target=target.strip(), selected_preset_name=None)

    def set_baudrate(self, baudrate: int | str) -> None:
        try:
            value = int(str(baudrate).strip())
        except ValueError:
            self._set_snapshot(last_error="波特率必须是整数。")
            return
        self._set_snapshot(baudrate=value, last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: SerialSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_line_ending(self, line_ending: SerialLineEnding) -> None:
        self._set_snapshot(line_ending=line_ending, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def open_session(self) -> None:
        if not self._snapshot.target:
            self._set_snapshot(last_error="打开前请先选择或输入串口目标。")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.SERIAL,
                name=display_transport_name(TransportKind.SERIAL),
                target=self._snapshot.target,
                options={"baudrate": self._snapshot.baudrate},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if self._adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="发送前请先打开串口会话。")
            return

        try:
            payload = self._encode_payload(self._snapshot.send_text, self._snapshot.send_mode)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        self._send_payload(
            payload,
            {"encoding": self._snapshot.send_mode.value},
            not_connected_error="发送前请先打开串口会话。",
        )

    def _encode_payload(self, text: str, mode: SerialSendEncoding) -> bytes:
        if not text.strip():
            raise ValueError("发送前请输入报文内容。")
        payload: bytes
        if mode == SerialSendEncoding.UTF8:
            payload = text.encode("utf-8")
        elif mode == SerialSendEncoding.ASCII:
            try:
                payload = text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII 报文只能包含 7 位 ASCII 字符。") from exc
        else:
            try:
                payload = bytes.fromhex(text)
            except ValueError as exc:
                raise ValueError("HEX 报文必须由完整的十六进制字节组成。") from exc
        return payload + self._line_ending_bytes(self._snapshot.line_ending)

    def _line_ending_bytes(self, line_ending: SerialLineEnding) -> bytes:
        return {
            SerialLineEnding.NONE: b"",
            SerialLineEnding.CR: b"\r",
            SerialLineEnding.LF: b"\n",
            SerialLineEnding.CRLF: b"\r\n",
        }[line_ending]
