from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class TransportKind(StrEnum):
    SERIAL = "serial"
    TCP_CLIENT = "tcp_client"
    TCP_SERVER = "tcp_server"
    UDP = "udp"
    MQTT_CLIENT = "mqtt_client"
    MQTT_SERVER = "mqtt_server"


class ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STOPPING = "stopping"
    ERROR = "error"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class TransportEventType(StrEnum):
    STATE_CHANGED = "state_changed"
    MESSAGE = "message"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TransportCapabilities:
    can_listen: bool = False
    can_accept_clients: bool = False
    supports_topics: bool = False
    supports_binary_payloads: bool = True
    supports_text_payloads: bool = True
    supports_tls: bool = False
    supports_reconnect: bool = False


@dataclass(frozen=True, slots=True)
class TransportDescriptor:
    kind: TransportKind
    display_name: str
    capabilities: TransportCapabilities


@dataclass(slots=True)
class TransportConfig:
    kind: TransportKind
    name: str
    target: str
    options: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransportSession:
    session_id: str
    kind: TransportKind
    name: str
    target: str
    state: ConnectionState

    @classmethod
    def new(cls, kind: TransportKind, name: str, target: str) -> "TransportSession":
        return cls(
            session_id=uuid4().hex,
            kind=kind,
            name=name,
            target=target,
            state=ConnectionState.DISCONNECTED,
        )

    def with_state(self, state: ConnectionState) -> "TransportSession":
        from protolink.core.connection_state_model import validate_connection_state_transition

        validate_connection_state_transition(self.state, state)
        return TransportSession(
            session_id=self.session_id,
            kind=self.kind,
            name=self.name,
            target=self.target,
            state=state,
        )


@dataclass(frozen=True, slots=True)
class RawTransportMessage:
    session_id: str
    kind: TransportKind
    direction: MessageDirection
    payload: bytes
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransportEvent:
    event_type: TransportEventType
    session: TransportSession
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    message: RawTransportMessage | None = None
    error: str | None = None


TransportEventHandler = Callable[[TransportEvent], None]


class TransportAdapter(ABC):
    def __init__(self, descriptor: TransportDescriptor) -> None:
        self.descriptor = descriptor
        self._handler: TransportEventHandler | None = None
        self._session: TransportSession | None = None

    @property
    def session(self) -> TransportSession | None:
        return self._session

    def set_event_handler(self, handler: TransportEventHandler | None) -> None:
        self._handler = handler

    def bind_session(self, config: TransportConfig) -> TransportSession:
        self._session = TransportSession.new(
            kind=config.kind,
            name=config.name,
            target=config.target,
        )
        return self._session

    def emit(self, event: TransportEvent) -> None:
        if self._handler is not None:
            self._handler(event)

    def emit_state(self, state: ConnectionState) -> None:
        if self._session is None:
            raise RuntimeError("会话尚未绑定。")
        self._session = self._session.with_state(state)
        self.emit(
            TransportEvent(
                event_type=TransportEventType.STATE_CHANGED,
                session=self._session,
            )
        )

    def emit_message(
        self,
        direction: MessageDirection,
        payload: bytes,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        if self._session is None:
            raise RuntimeError("会话尚未绑定。")
        message = RawTransportMessage(
            session_id=self._session.session_id,
            kind=self._session.kind,
            direction=direction,
            payload=payload,
            metadata=metadata or {},
        )
        self.emit(
            TransportEvent(
                event_type=TransportEventType.MESSAGE,
                session=self._session,
                message=message,
            )
        )

    def emit_error(self, error: str) -> None:
        if self._session is None:
            raise RuntimeError("会话尚未绑定。")
        self._session = self._session.with_state(ConnectionState.ERROR)
        self.emit(
            TransportEvent(
                event_type=TransportEventType.ERROR,
                session=self._session,
                error=error,
            )
        )

    @abstractmethod
    async def open(self, config: TransportConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        raise NotImplementedError


TransportFactory = Callable[[], TransportAdapter]


class TransportRegistry:
    def __init__(self) -> None:
        self._factories: dict[TransportKind, TransportFactory] = {}

    def register(self, kind: TransportKind, factory: TransportFactory) -> None:
        self._factories[kind] = factory

    def create(self, kind: TransportKind) -> TransportAdapter:
        try:
            factory = self._factories[kind]
        except KeyError as exc:
            raise KeyError(f"传输类型“{kind}”未注册。") from exc
        return factory()

    def registered_kinds(self) -> tuple[TransportKind, ...]:
        return tuple(self._factories.keys())
