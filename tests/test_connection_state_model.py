import pytest

from protolink.core.connection_state_model import can_transition_connection_state, validate_connection_state_transition
from protolink.core.transport import ConnectionState, TransportKind, TransportSession


def test_connection_state_model_allows_expected_transitions() -> None:
    assert can_transition_connection_state(ConnectionState.DISCONNECTED, ConnectionState.CONNECTING) is True
    assert can_transition_connection_state(ConnectionState.CONNECTING, ConnectionState.CONNECTED) is True
    assert can_transition_connection_state(ConnectionState.CONNECTED, ConnectionState.STOPPING) is True
    assert can_transition_connection_state(ConnectionState.ERROR, ConnectionState.DISCONNECTED) is True


def test_connection_state_model_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError):
        validate_connection_state_transition(ConnectionState.DISCONNECTED, ConnectionState.STOPPING)


def test_transport_session_with_state_uses_validated_model() -> None:
    session = TransportSession.new(TransportKind.TCP_CLIENT, "Bench", "127.0.0.1:502")
    connecting = session.with_state(ConnectionState.CONNECTING)
    connected = connecting.with_state(ConnectionState.CONNECTED)

    assert connected.state == ConnectionState.CONNECTED

    with pytest.raises(ValueError):
        session.with_state(ConnectionState.STOPPING)
