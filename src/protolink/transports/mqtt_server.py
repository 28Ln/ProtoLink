from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig
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


def _default_mqtt_server_descriptor() -> TransportDescriptor:
    return TransportDescriptor(
        kind=TransportKind.MQTT_SERVER,
        display_name="MQTT Server",
        capabilities=TransportCapabilities(
            can_listen=True,
            can_accept_clients=True,
            supports_topics=True,
            supports_binary_payloads=True,
            supports_tls=True,
        ),
    )


@dataclass(frozen=True, slots=True)
class MqttServerConnectionSettings:
    host: str
    port: int
    internal_client_id: str
    open_timeout: float = 5.0

    @classmethod
    def from_transport_config(cls, config: TransportConfig) -> "MqttServerConnectionSettings":
        host, port = parse_mqtt_server_target(config.target)
        options = dict(config.options)
        internal_client_id = str(options.get("client_id", "") or "").strip() or f"protolink-broker-monitor-{uuid4().hex[:8]}"
        return cls(
            host=host,
            port=port,
            internal_client_id=internal_client_id,
            open_timeout=float(options.get("open_timeout", 5.0) or 5.0),
        )


def parse_mqtt_server_target(target: str) -> tuple[str, int]:
    host, separator, port_text = target.strip().rpartition(":")
    if separator != ":" or not host or not port_text:
        raise ValueError("MQTT server target must use the format host:port.")

    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("MQTT server port must be between 1 and 65535.")
    return host, port


class MqttServerTransportAdapter(TransportAdapter):
    def __init__(self, descriptor: TransportDescriptor | None = None) -> None:
        super().__init__(descriptor or _default_mqtt_server_descriptor())
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broker: Broker | None = None
        self._client: mqtt.Client | None = None
        self._settings: MqttServerConnectionSettings | None = None
        self._closing = False
        self._open_future: asyncio.Future[None] | None = None
        self._disconnect_future: asyncio.Future[None] | None = None
        self._subscribe_future: asyncio.Future[None] | None = None

    async def open(self, config: TransportConfig) -> None:
        if self._broker is not None or self._client is not None:
            raise RuntimeError("MQTT server transport is already open.")

        settings = MqttServerConnectionSettings.from_transport_config(config)
        self._settings = settings
        self.bind_session(config)
        self._loop = asyncio.get_running_loop()
        self._closing = False
        self.emit_state(ConnectionState.CONNECTING)

        broker_config = {
            "listeners": {"default": {"bind": f"{settings.host}:{settings.port}"}},
        }
        broker_config = BrokerConfig.from_dict(broker_config)
        self._broker = Broker(broker_config, loop=self._loop)
        try:
            await self._broker.start()
            self._open_future = self._loop.create_future()
            self._subscribe_future = self._loop.create_future()

            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=settings.internal_client_id,
                protocol=mqtt.MQTTv311,
            )
            client.enable_logger()
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            client.on_subscribe = self._on_subscribe
            self._client = client

            await asyncio.to_thread(client.connect, settings.host, settings.port, 60)
            client.loop_start()
            await asyncio.wait_for(self._open_future, timeout=settings.open_timeout)
            await asyncio.wait_for(self._subscribe_future, timeout=settings.open_timeout)
            self.emit_state(ConnectionState.CONNECTED)
        except Exception:
            self.emit_error("MQTT broker startup failed.")
            await self.close()
            raise

    async def close(self) -> None:
        if self.session is None:
            return

        if self.session.state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPING}:
            self.emit_state(ConnectionState.STOPPING)

        self._closing = True
        client = self._client
        if client is not None:
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
        self._subscribe_future = None
        self._settings = None

        broker = self._broker
        self._broker = None
        if broker is not None:
            await broker.shutdown()

        if self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
            self.emit_state(ConnectionState.DISCONNECTED)
        self._loop = None

    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        await self._ensure_connected()
        client = self._require_client()
        outbound_metadata = dict(metadata or {})
        topic = outbound_metadata.get("topic")
        if not topic:
            raise RuntimeError("MQTT broker publish requires a topic in metadata.")

        self.emit_message(MessageDirection.OUTBOUND, payload, outbound_metadata)
        info = client.publish(topic, payload=payload, qos=int(outbound_metadata.get("qos", "0") or 0))
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(mqtt.error_string(info.rc))
        await asyncio.to_thread(info.wait_for_publish)
        if not info.is_published():
            raise RuntimeError("MQTT broker publish did not complete.")

    async def _ensure_connected(self) -> None:
        client = self._require_client()
        settings = self._settings
        loop = self._loop
        if settings is None or loop is None:
            raise RuntimeError("MQTT server transport is not ready.")
        if client.is_connected():
            return

        self._open_future = loop.create_future()
        self._subscribe_future = loop.create_future()
        await asyncio.to_thread(client.reconnect)
        await asyncio.wait_for(self._open_future, timeout=settings.open_timeout)
        await asyncio.wait_for(self._subscribe_future, timeout=settings.open_timeout)
        if self.session is not None and self.session.state != ConnectionState.CONNECTED:
            self.emit_state(ConnectionState.CONNECTED)

    def _require_client(self) -> mqtt.Client:
        if self._client is None:
            raise RuntimeError("MQTT server transport is not open.")
        return self._client

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def handle_connect() -> None:
            code = int(getattr(reason_code, "value", reason_code))
            if self._open_future is not None and not self._open_future.done():
                if code == 0:
                    self._open_future.set_result(None)
                    result, _mid = client.subscribe("#")
                    if result != mqtt.MQTT_ERR_SUCCESS and self._subscribe_future is not None and not self._subscribe_future.done():
                        self._subscribe_future.set_exception(RuntimeError(mqtt.error_string(result)))
                else:
                    message = mqtt.connack_string(code)
                    self.emit_error(message)
                    self._open_future.set_exception(RuntimeError(message))

        try:
            loop.call_soon_threadsafe(handle_connect)
        except RuntimeError:
            return

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def handle_disconnect() -> None:
            if self._disconnect_future is not None and not self._disconnect_future.done():
                self._disconnect_future.set_result(None)
            if not self._closing and self.session is not None and self.session.state != ConnectionState.DISCONNECTED:
                self.emit_state(ConnectionState.DISCONNECTED)

        try:
            loop.call_soon_threadsafe(handle_disconnect)
        except RuntimeError:
            return

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(
                self.emit_message,
                MessageDirection.INBOUND,
                bytes(msg.payload),
                {"topic": msg.topic, "qos": str(msg.qos), "retain": str(int(msg.retain))},
            )
        except RuntimeError:
            return

    def _on_subscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: Any,
        properties: Any = None,
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def handle_subscribe() -> None:
            if self._subscribe_future is not None and not self._subscribe_future.done():
                self._subscribe_future.set_result(None)
            self.emit_message(MessageDirection.INTERNAL, b"", {"event": "subscribed", "topic": "#"})

        try:
            loop.call_soon_threadsafe(handle_subscribe)
        except RuntimeError:
            return
