from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protolink.application.connection_service import MappedProfileSessionServiceBase, SnapshotValueMapping
from protolink.core.event_bus import EventBus
from protolink.core.mqtt_client_profiles import (
    MqttClientDraft,
    MqttClientPreset,
    default_mqtt_client_profile_path,
    load_mqtt_client_profile,
    save_mqtt_client_profile,
)
from protolink.core.transport import ConnectionState, MessageDirection, TransportConfig, TransportEvent, TransportEventType, TransportKind, TransportRegistry
from protolink.core.workspace import WorkspaceLayout
from protolink.presentation import display_transport_name


class MqttClientSendEncoding(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


@dataclass(frozen=True, slots=True)
class MqttClientSessionSnapshot:
    host: str = "127.0.0.1"
    port: int = 1883
    client_id: str = ""
    publish_topic: str = "bench/topic"
    subscribe_topic: str = "bench/topic"
    send_mode: MqttClientSendEncoding = MqttClientSendEncoding.HEX
    send_text: str = ""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    active_session_id: str | None = None
    last_error: str | None = None
    subscribed_topics: tuple[str, ...] = ()
    preset_names: tuple[str, ...] = ()
    selected_preset_name: str | None = None


class MqttClientSessionService(MappedProfileSessionServiceBase[MqttClientSessionSnapshot, MqttClientDraft, MqttClientPreset]):
    PROFILE_MAPPINGS = (
        SnapshotValueMapping("host", "host"),
        SnapshotValueMapping("port", "port"),
        SnapshotValueMapping("client_id", "client_id"),
        SnapshotValueMapping("publish_topic", "publish_topic"),
        SnapshotValueMapping("subscribe_topic", "subscribe_topic"),
        SnapshotValueMapping("send_mode", "send_mode", encode=lambda value: value.value, decode=MqttClientSendEncoding),
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
            transport_kind=TransportKind.MQTT_CLIENT,
            initial_snapshot=MqttClientSessionSnapshot(),
            unknown_error_message="MQTT 客户端出现未知异常。",
            profile_path=default_mqtt_client_profile_path(workspace.profiles),
            profile_loader=load_mqtt_client_profile,
            profile_saver=save_mqtt_client_profile,
            draft_type=MqttClientDraft,
            preset_type=MqttClientPreset,
            profile_mappings=self.PROFILE_MAPPINGS,
        )

    def set_host(self, host: str) -> None:
        self._set_snapshot(host=host.strip(), last_error=None, selected_preset_name=None)

    def set_port(self, port: int | str) -> None:
        try:
            value = int(str(port).strip())
        except ValueError:
            self._set_snapshot(last_error="MQTT 端口必须是整数。")
            return
        if not 1 <= value <= 65535:
            self._set_snapshot(last_error="MQTT 端口必须在 1 到 65535 之间。")
            return
        self._set_snapshot(port=value, last_error=None, selected_preset_name=None)

    def set_client_id(self, client_id: str) -> None:
        self._set_snapshot(client_id=client_id.strip(), last_error=None, selected_preset_name=None)

    def set_publish_topic(self, topic: str) -> None:
        self._set_snapshot(publish_topic=topic.strip(), last_error=None, selected_preset_name=None)

    def set_subscribe_topic(self, topic: str) -> None:
        self._set_snapshot(subscribe_topic=topic.strip(), last_error=None, selected_preset_name=None)

    def set_send_mode(self, mode: MqttClientSendEncoding) -> None:
        self._set_snapshot(send_mode=mode, last_error=None, selected_preset_name=None)

    def set_send_text(self, text: str) -> None:
        self._set_snapshot(send_text=text, selected_preset_name=None)

    def open_session(self) -> None:
        if not self._snapshot.host:
            self._set_snapshot(last_error="打开前请输入 MQTT 主机地址。")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.MQTT_CLIENT,
                name=display_transport_name(TransportKind.MQTT_CLIENT),
                target=self._target(),
                options={"client_id": self._snapshot.client_id, "open_timeout": 2.0},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def subscribe_current_topic(self) -> None:
        adapter = self._adapter
        if adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="订阅前请先打开 MQTT 客户端。")
            return
        if not self._snapshot.subscribe_topic:
            self._set_snapshot(last_error="订阅前请输入订阅主题。")
            return

        future = self._ensure_runtime().submit(adapter.subscribe(self._snapshot.subscribe_topic))
        future.add_done_callback(lambda completed: self._handle_future_result("subscribe", completed, adapter))
        self._set_snapshot(last_error=None)

    def send_current_payload(self) -> None:
        if not self._snapshot.publish_topic:
            self._set_snapshot(last_error="发送前请输入发布主题。")
            return
        if self._adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="发送前请先打开 MQTT 客户端。")
            return

        try:
            payload = self._encode_payload(self._snapshot.send_text, self._snapshot.send_mode)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        self._send_payload(
            payload,
            {"encoding": self._snapshot.send_mode.value, "topic": self._snapshot.publish_topic},
            not_connected_error="发送前请先打开 MQTT 客户端。",
        )

    def _target(self) -> str:
        return f"{self._snapshot.host}:{self._snapshot.port}"

    def _handle_transport_event(self, event: TransportEvent) -> None:
        if (
            event.session.kind == TransportKind.MQTT_CLIENT
            and self._adapter is not None
            and self._adapter.session is not None
            and event.session.session_id == self._adapter.session.session_id
            and event.message is not None
            and event.message.direction == MessageDirection.INTERNAL
            and event.message.metadata.get("event") == "subscribed"
        ):
            topic = event.message.metadata.get("topic")
            subscribed_topics = list(self._snapshot.subscribed_topics)
            if topic and topic not in subscribed_topics:
                subscribed_topics.append(topic)
            self._set_snapshot(subscribed_topics=tuple(sorted(subscribed_topics)))
        super()._handle_transport_event(event)
        if (
            event.session.kind == TransportKind.MQTT_CLIENT
            and event.event_type == TransportEventType.STATE_CHANGED
            and event.session.state == ConnectionState.DISCONNECTED
        ):
            self._set_snapshot(subscribed_topics=())

    def _encode_payload(self, text: str, mode: MqttClientSendEncoding) -> bytes:
        if not text.strip():
            raise ValueError("发送前请输入报文内容。")

        if mode == MqttClientSendEncoding.UTF8:
            return text.encode("utf-8")
        if mode == MqttClientSendEncoding.ASCII:
            try:
                return text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII 报文只能包含 7 位 ASCII 字符。") from exc
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("HEX 报文必须由完整的十六进制字节组成。") from exc
