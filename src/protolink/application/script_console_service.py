from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from protolink.application.script_host_service import ScriptHostService
from protolink.core.event_bus import EventBus
from protolink.core.logging import LogLevel, create_log_entry
from protolink.core.script_host import ScriptExecutionRequest, ScriptExecutionResult, ScriptLanguage
from protolink.core.workspace import WorkspaceLayout


@dataclass(frozen=True, slots=True)
class ScriptConsoleSnapshot:
    available_languages: tuple[ScriptLanguage, ...] = ()
    selected_language: ScriptLanguage | None = None
    timeout_seconds: float = 2.0
    code: str = ""
    context_text: str = ""
    execution_count: int = 0
    last_run_at: datetime | None = None
    last_output: str = ""
    last_result_text: str = ""
    last_error: str | None = None
    last_script_file: str | None = None


class ScriptConsoleService:
    def __init__(
        self,
        script_host_service: ScriptHostService,
        workspace: WorkspaceLayout,
        *,
        event_bus: EventBus | None = None,
    ) -> None:
        self._script_host_service = script_host_service
        self._workspace = workspace
        self._event_bus = event_bus
        available_languages = tuple(script_host_service.snapshot.available_languages)
        selected_language = available_languages[0] if available_languages else None
        self._snapshot = ScriptConsoleSnapshot(
            available_languages=available_languages,
            selected_language=selected_language,
        )
        self._listeners: list[Callable[[ScriptConsoleSnapshot], None]] = []

    @property
    def snapshot(self) -> ScriptConsoleSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[ScriptConsoleSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_language(self, language: ScriptLanguage | str | None) -> None:
        if language is None:
            self._set_snapshot(selected_language=None)
            return
        if not isinstance(language, ScriptLanguage):
            language = ScriptLanguage(str(language))
        self._set_snapshot(selected_language=language)

    def set_timeout_seconds(self, value: float) -> None:
        self._set_snapshot(timeout_seconds=max(float(value), 0.1))

    def set_code(self, code: str) -> None:
        self._set_snapshot(code=code)

    def set_context_text(self, text: str) -> None:
        self._set_snapshot(context_text=text)

    def run_script(self) -> ScriptExecutionResult | None:
        language = self._snapshot.selected_language
        if language is None:
            self._set_snapshot(last_error="No script language is available.")
            return None
        if not self._snapshot.code.strip():
            self._set_snapshot(last_error="Script code is required before running.")
            return None

        try:
            context = self._parse_context_text(self._snapshot.context_text)
        except ValueError as exc:
            self._set_snapshot(last_error=str(exc))
            self._publish_log(
                level=LogLevel.ERROR,
                category="automation.script_console.error",
                message=str(exc),
                metadata={"language": language.value},
            )
            return None

        script_file = self._save_script_file(language, self._snapshot.code)
        result = self._script_host_service.execute(
            ScriptExecutionRequest(
                language=language,
                code=self._snapshot.code,
                context=context,
                timeout_seconds=self._snapshot.timeout_seconds,
            )
        )
        now = datetime.now(UTC)
        self._set_snapshot(
            execution_count=self._snapshot.execution_count + 1,
            last_run_at=now,
            last_output=result.output,
            last_result_text="" if result.result is None else repr(result.result),
            last_error=result.error,
            last_script_file=str(script_file),
        )
        if result.success:
            self._publish_log(
                level=LogLevel.INFO,
                category="automation.script_console.run",
                message="Script Console execution succeeded.",
                metadata={"language": language.value, "script_file": script_file.name},
            )
        else:
            self._publish_log(
                level=LogLevel.ERROR,
                category="automation.script_console.error",
                message=result.error or "Script Console execution failed.",
                metadata={"language": language.value, "script_file": script_file.name},
            )
        return result

    def _parse_context_text(self, text: str) -> Mapping[str, object]:
        if not text.strip():
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Script context must be valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Script context must be a JSON object.")
        return {str(key): value for key, value in payload.items()}

    def _save_script_file(self, language: ScriptLanguage, code: str) -> Path:
        extension = ".py" if language == ScriptLanguage.PYTHON else ".txt"
        path = self._workspace.scripts / f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}-script-console{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        return path

    def _publish_log(
        self,
        *,
        level: LogLevel,
        category: str,
        message: str,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            create_log_entry(level=level, category=category, message=message, metadata=metadata)
        )

    def _set_snapshot(self, **changes: object) -> None:
        self._snapshot = replace(self._snapshot, **changes)
        self._notify()

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)
