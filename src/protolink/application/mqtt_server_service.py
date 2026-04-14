from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.mqtt_server_profiles import (
    MqttServerDraft,
    MqttServerPreset,
    default_mqtt_server_profile_path,
    load_mqtt_server_profile,
    save_mqtt_server_profile,
)
from protolink.core.transport import ConnectionState, TransportConfig, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import display_transport_name


class MqttServerSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


@dataclass(frozen=True, slots=True)
class MqttServerSessionSnapshot:
    host: str = "127.0.0.1"
    port: int = 1883
    publish_topic: str = "bench/topic"
    send_mode: MqttServerSendEncoding = MqttServerSendEncoding.HEX
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class MqttServerSessionService(MappedProfileSessionServiceBase[MqttServerSessionSnapshot, MqttServerDraft, MqttServerPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("host", "host"),
        SnapshotValueMapping("port", "port"),
        SnapshotValueMapping("publish_topic", "publish_topic"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=MqttServerSendEncoding),
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
            transport_kind=TransportKind.MQTT_SERVER,
            initial_snapshot=MqttServerSessionSnapshot(),
            unknown_error_message="MQTT 服务端出现未知异常。",
            profile_path=default_mqtt_server_profile_path(workspace.profiles),
            profile_loader=load_mqtt_server_profile,
            profile_saver=save_mqtt_server_profile,
            draft_type=MqttServerDraft,
            preset_type=MqttServerPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )

    def set_host(self, host: str) -> None:
        self._set_snapshot(host=host.strip(), last_error=None, selected_preset_name=None)

    def set_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="MQTT 服务端端口必须是整数。")
            return
        if not 1 <= value <= 65535:
            self._set_snapshot(last_error="MQTT 服务端端口必须在 1 到 65535 之间。")
            return
        self._set_snapshot(port=value, last_error=None, selected_preset_name=None)

    def set_publish_topic(self, topic: str) -> None:
        self._set_snapshot(publish_topic=topic.strip(), last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: MqttServerSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def open_session(self) -> None:
        if not self._snapshot.host:
            self._set_snapshot(last_error="打开前请输入 MQTT 服务端主机地址。")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.MQTT_SERVER,
                name=display_transport_name(TransportKind.MQTT_SERVER),
                target=self._target(),
                options={},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def send_current_payload(self) -> None:
        if not self._snapshot.publish_topic:
            self._set_snapshot(last_error="发送前请输入发布主题。")
            return

        try:
            payload = self._encode_payload(self._snapshot.send_text, self._snapshot.send_mode)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        self._send_payload(
            payload,
            {"topic": self._snapshot.publish_topic, "encoding": self._snapshot.send_mode.value},
            not_connected_error="发送前请先打开 MQTT 服务端。",
        )

    def _target(self) -> str:
        return f"{self._snapshot.host}:{self._snapshot.port}"

    def _encode_payload(self, text: str, mode: MqttServerSendEncoding) -> bytes:
        if not text.strip():
            raise ValueError("发送前请输入报文内容。")

        if mode == MqttServerSendEncoding.UTF8:
            return text.encode("utf-8")
        if mode == MqttServerSendEncoding.ASCII:
            try:
                return text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII 报文只能包含 7 位 ASCII 字符。") from exc
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("HEX 报文必须由完整的十六进制字节组成。") from exc
