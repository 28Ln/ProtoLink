from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class NetworkToolsSnapshot:
    local_hostname: str = ""
    local_ip_addresses: tuple[str, ...] = ()
    target_host: str = "127.0.0.1"
    target_port: int = 502
    resolved_ip_addresses: tuple[str, ...] = ()
    tcp_probe_summary: str = ""
    execution_count: int = 0
    last_error: str | None = None

    @property
    def local_addresses_text(self) -> str:
        return "\n".join(self.local_ip_addresses)

    @property
    def resolved_addresses_text(self) -> str:
        return "\n".join(self.resolved_ip_addresses)

    @property
    def last_probe_result(self) -> str:
        return self.tcp_probe_summary


class NetworkToolsService:
    def __init__(self) -> None:
        self._snapshot = NetworkToolsSnapshot()
        self._listeners: list[Callable[[NetworkToolsSnapshot], None]] = []
        self._refresh_local_info(count_execution=False)

    @property
    def snapshot(self) -> NetworkToolsSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[NetworkToolsSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_target_host(self, host: str) -> None:
        self._set_snapshot(target_host=host.strip())

    def set_target_port(self, port: int) -> None:
        self._set_snapshot(target_port=max(int(port), 1))

    def refresh_local_info(self) -> None:
        self._refresh_local_info(count_execution=True)

    def _refresh_local_info(self, *, count_execution: bool) -> None:
        hostname = socket.gethostname()
        try:
            addresses = sorted(
                {
                    info[4][0]
                    for info in socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
                    if info[4]
                }
            )
        except OSError as exc:
            self._set_snapshot(
                local_hostname=hostname,
                local_ip_addresses=(),
                execution_count=self._snapshot.execution_count + 1 if count_execution else self._snapshot.execution_count,
                last_error=f"本机网络信息刷新失败：{exc}",
            )
            return
        self._set_snapshot(
            local_hostname=hostname,
            local_ip_addresses=tuple(addresses),
            execution_count=self._snapshot.execution_count + 1 if count_execution else self._snapshot.execution_count,
            last_error=None,
        )

    def resolve_target(self) -> str | None:
        host = self._snapshot.target_host.strip()
        if not host:
            self._set_snapshot(last_error="解析前请输入目标主机。")
            return None
        try:
            _, _, addresses = socket.gethostbyname_ex(host)
        except OSError as exc:
            self._set_snapshot(last_error=str(exc))
            return None
        normalized = tuple(sorted(dict.fromkeys(addresses)))
        self._set_snapshot(
            resolved_ip_addresses=normalized,
            execution_count=self._snapshot.execution_count + 1,
            last_error=None,
        )
        return "\n".join(normalized)

    def probe_tcp(self, *, timeout_seconds: float = 1.0) -> str | None:
        host = self._snapshot.target_host.strip()
        if not host:
            self._set_snapshot(last_error="探测前请输入目标主机。")
            return None
        try:
            with socket.create_connection((host, self._snapshot.target_port), timeout=timeout_seconds):
                pass
        except OSError as exc:
            self._set_snapshot(last_error=str(exc), tcp_probe_summary=f"TCP 探测失败：{exc}")
            return None
        result = f"可达：{host}:{self._snapshot.target_port}"
        self._set_snapshot(
            tcp_probe_summary=result,
            execution_count=self._snapshot.execution_count + 1,
            last_error=None,
        )
        return result

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)
