from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from protolink.core.transport import (
    ConnectionState,
    MessageDirection,
    TransportAdapter,
    TransportCapabilities,
    TransportConfig,
    TransportDescriptor,
    TransportKind,
)
from protolink.presentation import display_transport_name


def _default_mqtt_client_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.MQTT_CLIENT,
        display_name=display_transport_name(TransportKind.MQTT_CLIENT),
        capabilities=TransportCapabilities(supports_topics=True, supports_binary_payloads=True, supports_tls=True),
    )


@dataclass(frozen=True, slots=True)
class MqttClientConnectionSettings:
    host: str
    port: int
    keepalive: int = 60
    client_id: str = ""
    open_timeout: float = 5.0

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "MqttClientConnectionSettings":
        host, port = parse_mqtt_client_target(config.target)
        options = dict(config.options)
        return cls(
            host=host,
            port=port,
            keepalive=int(options.get("keepalive", 60) or 60),
            client_id=str(options.get("client_id", "") or ""),
            open_timeout=float(options.get("open_timeout", 5.0) or 5.0),
        )


def parse_mqtt_client_target(target: str) -> tuple[str, int]:
    host, separator, port_text = target.strip().rpartition(":")
    if separator != ":" or not host or not port_text:
        raise ValueError("MQTT 客户端目标必须使用 host:port 格式。")

    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("MQTT 客户端端口必须在 1 到 65535 之间。")
    return host, port


class MqttClientTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor | None = None) -> None:
        super().__init__(descriptor or _default_mqtt_client_descriptor())
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: mqtt.Client | None = None
        self._closing = False
        self._open_future: asyncio.Future[None] | None = None
        self._disconnect_future: asyncio.Future[None] | None = None
        self._subscribe_futures: dict[int, asyncio.Future[None]] = {}

    async def open(self, config: TransportConfig) -> None:
        if self._client is not None:
            raise RuntimeError("MQTT 客户端传输已打开。")

        settings = MqttClientConnectionSettings.from_transport_config(config)
        self.bind_session(config)
        self._loop = asyncio.get_running_loop()
        self._closing = False
        self._open_future = self._loop.create_future()
        self.emit_state(ConnectionState.CONNECTING)

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.client_id,
            protocol=mqtt.MQTTv311,
        )
        client.enable_logger()
        client.on_connect = self._on_connect
        client.on_connect_fail = self._on_connect_fail
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe
        self._client = client

        try:
            await asyncio.to_thread(client.connect, settings.host, settings.port, settings.keepalive)
            client.loop_start()
            await asyncio.wait_for(self._open_future, timeout=settings.open_timeout)
        except Exception:
            self.emit_error("MQTT 连接失败。")
            if self._open_future is not None and not self._open_future.done():
                self._open_future.cancel()
            await self.close()
            raise

    async def close(self) -> None:
        client = self._client
        if client is None:
            return

        if self.session is not None and self.session.state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPING}:
            self.emit_state(ConnectionState.STOPPING)

        self._closing = True
        if self._loop is not None:
            self._disconnect_future = self._loop.create_future()
        client.disconnect()
        if self._disconnect_future is not None:
            try:
                await asyncio.wait_for(self._disconnect_future, timeout=3.0)
            except Exception:
                pass
        client.loop_stop()
        self._client = None
        self._open_future = None
        self._disconnect_future = None
        self._subscribe_futures.clear()

        if self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        client = self._require_client()
        message_metadata = dict(metadata or {})
        topic = message_metadata.get("topic")
        if not topic:
            raise RuntimeError("MQTT 发布需要在 metadata 中提供 topic。")

        self.emit_message(MessageDirection.OUTBOUND, payload, message_metadata)
        info = client.publish(topic, payload=payload, qos=int(message_metadata.get("qos", "0") or 0))
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(mqtt.error_string(info.rc))
        await asyncio.to_thread(info.wait_for_publish)

    async def subscribe(self, topic: str, qos: int = 0) -> None:
        client = self._require_client()
        if self._loop is None:
            raise RuntimeError("MQTT 客户端循环尚未就绪。")
        result, mid = client.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(mqtt.error_string(result))
        future = self._loop.create_future()
        self._subscribe_futures[mid] = future
        await asyncio.wait_for(future, timeout=3.0)
        self.emit_message(MessageDirection.INTERNAL, b"", {"event": "subscribed", "topic": topic, "qos": str(qos)})

    def _require_client(self) -> mqtt.Client:
        if self._client is None:
            raise RuntimeError("MQTT 客户端传输未打开。")
        return self._client

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if self._loop is None:
            return

        def complete_open() -> None:
            if self._open_future is not None and not self._open_future.done():
                code = int(getattr(reason_code, "value", reason_code))
                if code == mqtt.MQTT_ERR_SUCCESS or code == 0:
                    self.emit_state(ConnectionState.CONNECTED)
                    self._open_future.set_result(None)
                else:
                    message = mqtt.connack_string(code)
                    self.emit_error(message)
                    self._open_future.set_exception(RuntimeError(message))

        self._loop.call_soon_threadsafe(complete_open)

    def _on_connect_fail(self, client: mqtt.Client, userdata: Any) -> None:
        if self._loop is None:
            return

        def fail_open() -> None:
            message = "MQTT 连接失败。"
            self.emit_error(message)
            if self._open_future is not None and not self._open_future.done():
                self._open_future.set_exception(RuntimeError(message))

        self._loop.call_soon_threadsafe(fail_open)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if self._loop is None:
            return

        def handle_disconnect() -> None:
            if self._disconnect_future is not None and not self._disconnect_future.done():
                self._disconnect_future.set_result(None)
            if not self._closing and self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
                self.emit_state(ConnectionState.DISCONNECTED)

        self._loop.call_soon_threadsafe(handle_disconnect)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self.emit_message,
            MessageDirection.INBOUND,
            bytes(msg.payload),
            {"topic": msg.topic, "qos": str(msg.qos), "retain": str(int(msg.retain))},
        )

    def _on_subscribe(self, client: mqtt.Client, userdata: Any, mid: int, granted_qos: Any, properties: Any = None) -> None:
        if self._loop is None:
            return

        def complete_subscribe() -> None:
            future = self._subscribe_futures.pop(mid, None)
            if future is not None and not future.done():
                future.set_result(None)

        self._loop.call_soon_threadsafe(complete_subscribe)
