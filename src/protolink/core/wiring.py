from __future__ import annotations

from collections.abc import Callable

from protolink.core.event_bus import EventBus
from protolink.core.logging import InMemoryLogStore, StructuredLogEntry, create_log_entry_from_transport_event
from protolink.core.packet_inspector import PacketInspectorState
from protolink.core.transport import TransportAdapter, TransportEvent


def wire_transport_logging(event_bus: EventBus, log_store: InMemoryLogStore) -> None:
    def handle_transport_event(event: TransportEvent) -> None:
        entry = create_log_entry_from_transport_event(event)
        log_store.append(entry)
        event_bus.publish(entry)

    event_bus.subscribe(TransportEvent, handle_transport_event)


def wire_packet_inspector(event_bus: EventBus, inspector: PacketInspectorState) -> None:
    event_bus.subscribe(StructuredLogEntry, inspector.append)


def bind_transport_to_event_bus(
    adapter: TransportAdapter,
    event_bus: EventBus,
    dispatch: Callable[[Callable[[], None]], None] | None = None,
) -> None:
    if dispatch is None:
        adapter.set_event_handler(event_bus.publish)
        return

    def publish_transport_event(event: TransportEvent) -> None:
        dispatch(lambda: event_bus.publish(event))

    adapter.set_event_handler(publish_transport_event)
