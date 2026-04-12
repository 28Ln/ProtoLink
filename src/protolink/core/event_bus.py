from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


EventHandler = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class EventHandlerError:
    event_type: type[Any]
    handler: EventHandler
    error: str


class EventBus:
    def __init__(self, *, failure_recorder: Callable[[EventHandlerError], None] | None = None) -> None:
        self._handlers: dict[type[Any], list[EventHandler]] = defaultdict(list)
        self._handler_errors: list[EventHandlerError] = []
        self._failure_recorder = failure_recorder

    @property
    def handler_errors(self) -> tuple[EventHandlerError, ...]:
        return tuple(self._handler_errors)

    def subscribe(self, event_type: type[Any], handler: EventHandler) -> Callable[[], None]:
        self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Any) -> None:
        for handler in list(self._handlers.get(type(event), [])):
            try:
                handler(event)
            except Exception as exc:
                handler_error = EventHandlerError(
                    event_type=type(event),
                    handler=handler,
                    error=str(exc),
                )
                self._handler_errors.append(handler_error)
                if self._failure_recorder is not None:
                    try:
                        self._failure_recorder(handler_error)
                    except Exception:
                        pass
