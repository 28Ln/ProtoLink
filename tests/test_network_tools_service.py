from __future__ import annotations

import socket

import pytest

from protolink.application.network_tools_service import NetworkToolsService
from tests.support import TcpEchoServer


def test_network_tools_service_refreshes_local_info_and_resolves_host() -> None:
    service = NetworkToolsService()
    service.refresh_local_info()

    assert service.snapshot.local_hostname
    assert service.snapshot.local_addresses_text is not None

    service.set_target_host("localhost")
    resolved = service.resolve_target()
    assert resolved is not None
    assert service.snapshot.resolved_addresses_text


def test_network_tools_service_probes_tcp_read_only() -> None:
    service = NetworkToolsService()
    with TcpEchoServer() as server:
        service.set_target_host(server.host)
        service.set_target_port(server.port)
        result = service.probe_tcp()
        assert result == f"可达：{server.host}:{server.port}"
        assert "可达" in service.snapshot.tcp_probe_summary


def test_network_tools_service_handles_local_info_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("resolver down")))

    service = NetworkToolsService()

    assert service.snapshot.local_hostname
    assert service.snapshot.local_ip_addresses == ()
    assert service.snapshot.execution_count == 0
    assert service.snapshot.last_error == "本机网络信息刷新失败：resolver down"

    service.refresh_local_info()

    assert service.snapshot.execution_count == 1
    assert service.snapshot.last_error == "本机网络信息刷新失败：resolver down"
