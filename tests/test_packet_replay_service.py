import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from protolink.application.packet_replay_service import PacketReplayExecutionService
from protolink.core.bootstrap import bootstrap_app_context
from protolink.core.packet_replay import PacketReplayPlan, PacketReplayStep, ReplayDirection, save_packet_replay_plan
from protolink.core.transport import ConnectionState, TransportKind
from tests.support import TcpEchoServer


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for condition.")


class _FakeReplayTarget:
    def __init__(self, *, connected: bool = True, session_id: str | None = None, peer: str | None = None) -> None:
        self.connected = connected
        self.sent: list[tuple[bytes, dict[str, str]]] = []
        self.snapshot = type(
            "Snapshot",
            (),
            {
                "active_session_id": session_id,
                "selected_client_peer": peer,
            },
        )()

    def is_connected(self) -> bool:
        return self.connected

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        self.sent.append((payload, dict(metadata or {})))


def test_packet_replay_service_executes_saved_plan_against_target(tmp_path: Path) -> None:
    target = _FakeReplayTarget(session_id="session-a")
    service = PacketReplayExecutionService({TransportKind.SERIAL: target})
    plan = PacketReplayPlan(
        name="bench",
        created_at=datetime(2026, 4, 8, 8, 0, 0, tzinfo=UTC),
        steps=(
            PacketReplayStep(delay_ms=0, payload=b"\x01\x03", direction=ReplayDirection.OUTBOUND),
            PacketReplayStep(delay_ms=5, payload=b"\x10", direction=ReplayDirection.INTERNAL),
        ),
    )
    replay_file = tmp_path / "bench-replay.json"
    save_packet_replay_plan(replay_file, plan)

    service.execute_saved_plan(replay_file, TransportKind.SERIAL)
    _wait_until(lambda: not service.snapshot.running and service.snapshot.dispatched_steps == 2)

    assert len(target.sent) == 2
    assert target.sent[0][0] == b"\x01\x03"
    assert target.sent[1][0] == b"\x10"
    assert target.sent[0][1]["replay_plan"] == "bench"
    assert target.sent[1][1]["replay_direction"] == ReplayDirection.INTERNAL.value
    assert service.snapshot.target_session_id == "session-a"
    assert target.sent[0][1]["replay_target_session_id"] == "session-a"
    service.shutdown()


def test_packet_replay_service_requires_connected_target() -> None:
    target = _FakeReplayTarget(connected=False)
    service = PacketReplayExecutionService({TransportKind.UDP: target})
    plan = PacketReplayPlan(
        name="bench",
        created_at=datetime.now(UTC),
        steps=(PacketReplayStep(delay_ms=0, payload=b"\x01", direction=ReplayDirection.OUTBOUND),),
    )

    service.execute_plan(plan, TransportKind.UDP)

    assert service.snapshot.running is False
    assert service.snapshot.last_error == "回放目标“udp”未连接。"
    assert target.sent == []
    service.shutdown()


def test_packet_replay_service_dispatches_listener_notifications_through_scheduler() -> None:
    target = _FakeReplayTarget(connected=False)
    service = PacketReplayExecutionService({TransportKind.UDP: target})
    scheduled_callbacks = []
    snapshots = []

    service.set_dispatch_scheduler(scheduled_callbacks.append)
    service.subscribe(snapshots.append)

    assert snapshots == []
    assert len(scheduled_callbacks) == 1
    scheduled_callbacks.pop(0)()
    assert snapshots[-1].running is False

    plan = PacketReplayPlan(
        name="bench",
        created_at=datetime.now(UTC),
        steps=(PacketReplayStep(delay_ms=0, payload=b"\x01", direction=ReplayDirection.OUTBOUND),),
    )
    service.execute_plan(plan, TransportKind.UDP)

    assert service.snapshot.last_error == "回放目标“udp”未连接。"
    assert snapshots[-1].last_error is None
    assert len(scheduled_callbacks) == 1
    scheduled_callbacks.pop(0)()
    assert snapshots[-1].last_error == "回放目标“udp”未连接。"
    service.shutdown()


def test_packet_replay_service_dispatches_steps_through_active_tcp_client(tmp_path: Path) -> None:
    context = bootstrap_app_context(tmp_path, persist_settings=False)
    tcp_client = context.tcp_client_service
    replay_service = context.packet_replay_service
    try:
        with TcpEchoServer() as server:
            tcp_client.set_host(server.host)
            tcp_client.set_port(server.port)
            tcp_client.open_session()
            _wait_until(lambda: tcp_client.snapshot.connection_state == ConnectionState.CONNECTED)

            plan = PacketReplayPlan(
                name="tcp-replay",
                created_at=datetime.now(UTC),
                steps=(
                    PacketReplayStep(delay_ms=0, payload=b"PING", direction=ReplayDirection.OUTBOUND),
                    PacketReplayStep(delay_ms=20, payload=b"PONG", direction=ReplayDirection.OUTBOUND),
                ),
            )
            replay_service.execute_plan(plan, TransportKind.TCP_CLIENT)
            _wait_until(lambda: not replay_service.snapshot.running and replay_service.snapshot.dispatched_steps == 2)
            _wait_until(
                lambda: len(
                    [
                        entry
                        for entry in context.log_store.latest(30)
                        if entry.category == "transport.message" and entry.metadata.get("source") == "packet_replay"
                    ]
                )
                >= 2
            )

            replay_entries = [
                entry
                for entry in context.log_store.latest(30)
                if entry.category == "transport.message" and entry.metadata.get("source") == "packet_replay"
            ]
            payloads = [entry.raw_payload for entry in replay_entries]
            assert b"PING" in payloads
            assert b"PONG" in payloads
            assert replay_service.snapshot.last_error is None
            assert replay_service.snapshot.target_kind == TransportKind.TCP_CLIENT
            tcp_client.close_session()
            _wait_until(lambda: tcp_client.snapshot.connection_state == ConnectionState.DISCONNECTED)
    finally:
        replay_service.shutdown()
        tcp_client.shutdown()
        context.serial_session_service.shutdown()
        context.mqtt_client_service.shutdown()
        context.mqtt_server_service.shutdown()
        context.tcp_server_service.shutdown()
        context.udp_service.shutdown()


def test_packet_replay_service_fails_when_target_session_changes_mid_run() -> None:
    target = _FakeReplayTarget(session_id="session-a")
    service = PacketReplayExecutionService({TransportKind.SERIAL: target})
    plan = PacketReplayPlan(
        name="bench",
        created_at=datetime.now(UTC),
        steps=(
            PacketReplayStep(delay_ms=0, payload=b"\x01", direction=ReplayDirection.OUTBOUND),
            PacketReplayStep(delay_ms=1000, payload=b"\x02", direction=ReplayDirection.OUTBOUND),
        ),
    )

    service.execute_plan(plan, TransportKind.SERIAL)
    _wait_until(lambda: len(target.sent) == 1)
    target.snapshot.active_session_id = "session-b"
    _wait_until(lambda: service.snapshot.running is False)

    assert service.snapshot.last_error == "回放执行失败：回放执行期间目标会话已变更。"
    service.shutdown()
