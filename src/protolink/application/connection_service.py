from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Generic, TypeVar

from protolink.application.runtime import AsyncTaskRunner
from protolink.core.event_bus import EventBus
from protolink.core.transport import ConnectionState, TransportConfig, TransportEvent, TransportEventType, TransportKind, TransportRegistry
from protolink.core.wiring import bind_transport_to_event_bus

SnapshotT = TypeVar("SnapshotT")
PresetT = TypeVar("PresetT")
DraftT = TypeVar("DraftT")


def _identity(value: Any) -> Any:
    return value


@dataclass(frozen=True, slots=True)
class SnapshotValueMapping:
    snapshot_field: str
    value_field: str
    encode: Callable[[Any], Any] = _identity
    decode: Callable[[Any], Any] = _identity


class ConnectionSessionServiceBase(Generic[SnapshotT]):
    def __init__(
        self,
        transport_registry: TransportRegistry,
        event_bus: EventBus,
        *,
        transport_kind: TransportKind,
        initial_snapshot: SnapshotT,
        unknown_error_message: str,
    ) -> None:
        self._transport_registry = transport_registry
        self._event_bus = event_bus
        self._transport_kind = transport_kind
        self._unknown_error_message = unknown_error_message
        self._listeners: list[Callable[[SnapshotT], None]] = []
        self._dispatch_scheduler: Callable[[Callable[[], None]], None] | None = None
        self._runtime: AsyncTaskRunner | None = None
        self._adapter = None
        self._snapshot = initial_snapshot
        self._event_bus.subscribe(TransportEvent, self._handle_transport_event)

    @property
    def snapshot(self) -> SnapshotT:
        return self._snapshot

    def subscribe(self, listener: Callable[[SnapshotT], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        self._dispatch(lambda: listener(self._snapshot))

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_dispatch_scheduler(self, scheduler: Callable[[Callable[[], None]], None] | None) -> None:
        self._dispatch_scheduler = scheduler

    def shutdown(self) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        adapter = self._adapter
        if adapter is not None and self._snapshot.connection_state != ConnectionState.DISCONNECTED:
            try:
                runtime.submit(adapter.close()).result(timeout=2.0)
            except Exception:
                pass
        runtime.shutdown()
        self._runtime = None

    def is_connected(self) -> bool:
        return self._adapter is not None and self._snapshot.connection_state == ConnectionState.CONNECTED

    def send_replay_payload(self, payload: bytes, metadata: Mapping[str, str] | None = None) -> None:
        replay_metadata = dict(metadata or {})
        replay_metadata.setdefault("source", "packet_replay")
        self._dispatch(
            lambda: self._send_payload(
                payload,
                replay_metadata,
                not_connected_error=f"Open the {self._transport_kind.value.replace('_', ' ')} transport before replay dispatch.",
            )
        )

    def _open_transport(self, config: TransportConfig) -> None:
        if self._snapshot.connection_state in {ConnectionState.CONNECTING, ConnectionState.CONNECTED}:
            return

        adapter = self._transport_registry.create(self._transport_kind)
        bind_transport_to_event_bus(adapter, self._event_bus, dispatch=self._dispatch_scheduler)
        self._adapter = adapter
        self._set_snapshot(last_error=None)

        future = self._ensure_runtime().submit(adapter.open(config))
        future.add_done_callback(lambda completed: self._handle_future_result("open", completed, adapter))

    def _close_transport(self) -> None:
        adapter = self._adapter
        if adapter is None:
            return

        future = self._ensure_runtime().submit(adapter.close())
        future.add_done_callback(lambda completed: self._handle_future_result("close", completed, adapter))

    def _send_payload(
        self,
        payload: bytes,
        metadata: Mapping[str, str] | None = None,
        *,
        not_connected_error: str,
    ) -> None:
        adapter = self._adapter
        if adapter is None or self._snapshot.connection_state != ConnectionState.CONNECTED:
            self._set_snapshot(last_error=not_connected_error)
            return

        future = self._ensure_runtime().submit(adapter.send(payload, metadata))
        future.add_done_callback(lambda completed: self._handle_future_result("send", completed, adapter))
        self._set_snapshot(last_error=None)

    def _handle_transport_event(self, event: TransportEvent) -> None:
        if event.session.kind != self._transport_kind:
            return
        if self._adapter is None or self._adapter.session is None:
            return
        if event.session.session_id != self._adapter.session.session_id:
            return

        if event.event_type == TransportEventType.ERROR:
            error_message = event.error or self._unknown_error_message
            if self._snapshot.connection_state == ConnectionState.CONNECTING:
                error_message = f"Open failed: {error_message}"
            self._set_snapshot(
                connection_state=ConnectionState.ERROR,
                active_session_id=event.session.session_id,
                last_error=error_message,
            )
            return

        if event.event_type == TransportEventType.STATE_CHANGED:
            active_session_id = event.session.session_id
            if event.session.state == ConnectionState.DISCONNECTED:
                active_session_id = None
            self._set_snapshot(
                connection_state=event.session.state,
                active_session_id=active_session_id,
                last_error=None if event.session.state != ConnectionState.ERROR else self._snapshot.last_error,
            )

    def _handle_future_result(self, operation: str, future: Future[Any], adapter: object) -> None:
        try:
            future.result()
        except Exception as exc:
            def publish_error() -> None:
                if operation == "send" and self._snapshot.connection_state in {
                    ConnectionState.STOPPING,
                    ConnectionState.DISCONNECTED,
                }:
                    return
                if operation != "close":
                    self._set_snapshot(
                        connection_state=ConnectionState.ERROR,
                        last_error=f"{operation.title()} failed: {exc}",
                    )
                if self._adapter is adapter:
                    self._adapter = None

            self._dispatch(publish_error)
            return

        if operation == "close":
            self._dispatch(lambda: self._finalize_close(adapter))

    def _clear_adapter_if_current(self, adapter: object) -> None:
        if self._adapter is adapter:
            self._adapter = None

    def _finalize_close(self, adapter: object) -> None:
        if self._snapshot.connection_state != ConnectionState.DISCONNECTED:
            self._set_snapshot(connection_state=ConnectionState.DISCONNECTED, active_session_id=None)
        self._clear_adapter_if_current(adapter)

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._after_snapshot_updated()
        self._notify()

    def _after_snapshot_updated(self) -> None:
        return None

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            self._dispatch(lambda listener=listener, snapshot=snapshot: listener(snapshot))

    def _dispatch(self, callback: Callable[[], None]) -> None:
        if self._dispatch_scheduler is None:
            callback()
            return
        self._dispatch_scheduler(callback)

    def _ensure_runtime(self) -> AsyncTaskRunner:
        if self._runtime is None:
            self._runtime = AsyncTaskRunner()
        return self._runtime


class PresetConnectionSessionServiceBase(ConnectionSessionServiceBase[SnapshotT], Generic[SnapshotT, PresetT]):
    def __init__(
        self,
        transport_registry: TransportRegistry,
        event_bus: EventBus,
        *,
        transport_kind: TransportKind,
        initial_snapshot: SnapshotT,
        unknown_error_message: str,
    ) -> None:
        self._presets_by_name: dict[str, PresetT] = {}
        super().__init__(
            transport_registry,
            event_bus,
            transport_kind=transport_kind,
            initial_snapshot=initial_snapshot,
            unknown_error_message=unknown_error_message,
        )

    def save_preset(self, name: str) -> None:
        normalized = self._normalize_preset_name(name)
        if not normalized:
            self._set_snapshot(last_error="Preset name is required.")
            return

        preset = self._build_preset(normalized)
        self._presets_by_name[normalized] = preset
        self._persist_profile(selected_preset_name=normalized)
        self._set_snapshot(
            preset_names=tuple(sorted(self._presets_by_name)),
            selected_preset_name=normalized,
            last_error=None,
        )

    def load_preset(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(selected_preset_name=None)
            return

        preset = self._presets_by_name.get(name)
        if preset is None:
            self._set_snapshot(last_error=f"Preset '{name}' was not found.")
            return

        self._set_snapshot(
            **self._snapshot_changes_from_preset(preset),
            selected_preset_name=name,
            last_error=None,
        )

    def delete_preset(self, name: str | None) -> None:
        if not name:
            self._set_snapshot(last_error="Select a preset before deleting.")
            return

        removed = self._presets_by_name.pop(name, None)
        if removed is None:
            self._set_snapshot(last_error=f"Preset '{name}' was not found.")
            return

        selected_preset_name = None if self._snapshot.selected_preset_name == name else self._snapshot.selected_preset_name
        self._persist_profile(selected_preset_name=selected_preset_name)
        self._set_snapshot(
            preset_names=tuple(sorted(self._presets_by_name)),
            selected_preset_name=selected_preset_name,
            last_error=None,
        )

    def _restore_profile_state(self, *, presets_by_name: dict[str, PresetT], snapshot_changes: dict[str, object]) -> None:
        self._presets_by_name = dict(presets_by_name)
        self._snapshot = replace(self._snapshot, **snapshot_changes)

    def _after_snapshot_updated(self) -> None:
        self._persist_profile()

    def _normalize_preset_name(self, name: str) -> str:
        return " ".join(name.strip().split())

    def _build_preset(self, name: str) -> PresetT:
        raise NotImplementedError

    def _snapshot_changes_from_preset(self, preset: PresetT) -> dict[str, object]:
        raise NotImplementedError

    def _persist_profile(self, *, selected_preset_name: str | None | object = ...) -> None:
        raise NotImplementedError

    def _mapped_values_from_snapshot(self, mappings: tuple[SnapshotValueMapping, ...]) -> dict[str, Any]:
        return {
            mapping.value_field: mapping.encode(getattr(self._snapshot, mapping.snapshot_field))
            for mapping in mappings
        }

    def _mapped_snapshot_changes_from_source(
        self,
        source: object,
        mappings: tuple[SnapshotValueMapping, ...],
    ) -> dict[str, Any]:
        return {
            mapping.snapshot_field: mapping.decode(getattr(source, mapping.value_field))
            for mapping in mappings
        }

    def _build_mapped_preset(
        self,
        preset_type: type[PresetT],
        name: str,
        mappings: tuple[SnapshotValueMapping, ...],
    ) -> PresetT:
        return preset_type(name=name, **self._mapped_values_from_snapshot(mappings))

    def _build_mapped_draft(
        self,
        draft_type: type[object],
        selected_preset_name: str | None,
        mappings: tuple[SnapshotValueMapping, ...],
    ) -> object:
        return draft_type(
            **self._mapped_values_from_snapshot(mappings),
            selected_preset_name=selected_preset_name,
        )


class MappedProfileSessionServiceBase(
    PresetConnectionSessionServiceBase[SnapshotT, PresetT],
    Generic[SnapshotT, DraftT, PresetT],
):
    def __init__(
        self,
        transport_registry: TransportRegistry,
        event_bus: EventBus,
        *,
        transport_kind: TransportKind,
        initial_snapshot: SnapshotT,
        unknown_error_message: str,
        profile_path: Path,
        profile_loader: Callable[[Path], object],
        profile_saver: Callable[[Path, object], None],
        draft_type: type[DraftT],
        preset_type: type[PresetT],
        profile_mappings: tuple[SnapshotValueMapping, ...],
    ) -> None:
        self._profile_path = profile_path
        self._profile_loader = profile_loader
        self._profile_saver = profile_saver
        self._draft_type = draft_type
        self._preset_type = preset_type
        self._profile_mappings = profile_mappings
        super().__init__(
            transport_registry,
            event_bus,
            transport_kind=transport_kind,
            initial_snapshot=initial_snapshot,
            unknown_error_message=unknown_error_message,
        )
        self._load_profile_state()

    def _load_profile_state(self) -> None:
        profile = self._profile_loader(self._profile_path)
        draft = getattr(profile, "draft")
        presets = tuple(getattr(profile, "presets", ()))
        profile_selected = getattr(profile, "selected_preset_name", None)
        draft_selected = getattr(draft, "selected_preset_name", None)
        presets_by_name = {self._preset_name(preset): preset for preset in presets}
        self._restore_profile_state(
            presets_by_name=presets_by_name,
            snapshot_changes={
                **self._mapped_snapshot_changes_from_source(draft, self._profile_mappings),
                "preset_names": tuple(sorted(presets_by_name)),
                "selected_preset_name": profile_selected or draft_selected,
            },
        )

    def _persist_profile(self, *, selected_preset_name: str | None | object = ...) -> None:
        effective_selected = self._snapshot.selected_preset_name if selected_preset_name is ... else selected_preset_name
        profile = self._profile_loader(self._profile_path)
        profile.selected_preset_name = effective_selected
        profile.draft = self._build_mapped_draft(self._draft_type, effective_selected, self._profile_mappings)
        profile.presets = [self._presets_by_name[name] for name in sorted(self._presets_by_name, key=str.lower)]
        self._profile_saver(self._profile_path, profile)

    def _build_preset(self, name: str) -> PresetT:
        return self._build_mapped_preset(self._preset_type, name, self._profile_mappings)

    def _snapshot_changes_from_preset(self, preset: PresetT) -> dict[str, object]:
        return self._mapped_snapshot_changes_from_source(preset, self._profile_mappings)

    def _preset_name(self, preset: PresetT) -> str:
        return str(getattr(preset, "name", "")).strip()
