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
            unknown_error_message="Unknown MQTT client error.",
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
            self._set_snapshot(last_error="MQTT port must be an integer.")
            return
        if not 1 <= value <= 65535:
            self._set_snapshot(last_error="MQTT port must be between 1 and 65535.")
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
            self._set_snapshot(last_error="Enter an MQTT host before opening.")
            return

        self._open_transport(
            TransportConfig(
                kind=TransportKind.MQTT_CLIENT,
                name="MQTT Client",
                target=self._target(),
                options={"client_id": self._snapshot.client_id, "open_timeout": 2.0},
            )
        )

    def close_session(self) -> None:
        self._close_transport()

    def subscribe_current_topic(self) -> None:
        adapter = self._adapter
        if adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="Open the MQTT client before subscribing.")
            return
        if not self._snapshot.subscribe_topic:
            self._set_snapshot(last_error="Enter a subscribe topic before subscribing.")
            return

        future = self._ensure_runtime().submit(adapter.subscribe(self._snapshot.subscribe_topic))
        future.add_done_callback(lambda completed: self._handle_future_result("subscribe", completed, adapter))
        self._set_snapshot(last_error=None)

    def send_current_payload(self) -> None:
        if not self._snapshot.publish_topic:
            self._set_snapshot(last_error="Enter a publish topic before sending.")
            return
        if self._adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error="Open the MQTT client before sending.")
            return

        try:
            payload = self._encode_payload(self._snapshot.send_text, self._snapshot.send_mode)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            return

        self._send_payload(
            payload,
            {"encoding": self._snapshot.send_mode.value, "topic": self._snapshot.publish_topic},
            not_connected_error="Open the MQTT client before sending.",
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
            raise ValueError("Enter payload text before sending.")

        if mode == MqttClientSendEncoding.UTF8:
            return text.encode("utf-8")
        if mode == MqttClientSendEncoding.ASCII:
            try:
                return text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII payload can only contain 7-bit ASCII characters.") from exc
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("HEX payload must contain complete hexadecimal bytes.") from exc
