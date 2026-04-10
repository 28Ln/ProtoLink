from __future__ import annotations

from protolink.core.transport import ConnectionState


ALLOWED_CONNECTION_STATE_TRANSITIONS: dict[ConnectionState, tuple[ConnectionState, ...]] = {
    ConnectionState.DISCONNECTED: (
        ConnectionState.CONNECTING,
        ConnectionState.CONNECTED,
        ConnectionState.ERROR,
    ),
    ConnectionState.CONNECTING: (
        ConnectionState.CONNECTED,
        ConnectionState.STOPPING,
        ConnectionState.DISCONNECTED,
        ConnectionState.ERROR,
    ),
    ConnectionState.CONNECTED: (
        ConnectionState.STOPPING,
        ConnectionState.DISCONNECTED,
        ConnectionState.ERROR,
    ),
    ConnectionState.STOPPING: (
        ConnectionState.DISCONNECTED,
        ConnectionState.ERROR,
    ),
    ConnectionState.ERROR: (
        ConnectionState.CONNECTING,
        ConnectionState.STOPPING,
        ConnectionState.DISCONNECTED,
    ),
}


def can_transition_connection_state(current: ConnectionState, target: ConnectionState) -> bool:
    if current == target:
        return True
    return target in ALLOWED_CONNECTION_STATE_TRANSITIONS[current]


def validate_connection_state_transition(current: ConnectionState, target: ConnectionState) -> None:
    if can_transition_connection_state(current, target):
        return
    raise ValueError(f"Invalid connection state transition: {current} -> {target}")
