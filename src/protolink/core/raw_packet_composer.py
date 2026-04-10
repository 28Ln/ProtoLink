from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from protolink.core.logging import render_payload_ascii, render_payload_hex, render_payload_utf8


class RawPacketInputMode(StrEnum):
    HEX = "hex"
    ASCII = "ascii"
    UTF8 = "utf8"


class RawPacketLineEnding(StrEnum):
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class RawPacketComposerSnapshot:
    input_mode: RawPacketInputMode = RawPacketInputMode.HEX
    line_ending: RawPacketLineEnding = RawPacketLineEnding.NONE
    draft_text: str = ""
    payload: bytes = b""
    payload_hex: str = ""
    payload_ascii: str = ""
    payload_utf8: str = ""
    last_error: str | None = None


class RawPacketComposerState:
    def __init__(self) -> None:
        self._snapshot = RawPacketComposerSnapshot()
        self._listeners: list[Callable[[RawPacketComposerSnapshot], None]] = []
        self._recompute()

    @property
    def snapshot(self) -> RawPacketComposerSnapshot:
        return self._snapshot

    def subscribe(self, listener: Callable[[RawPacketComposerSnapshot], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self._snapshot)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_input_mode(self, mode: RawPacketInputMode) -> None:
        self._snapshot = replace(self._snapshot, input_mode=mode)
        self._recompute()

    def set_line_ending(self, line_ending: RawPacketLineEnding) -> None:
        self._snapshot = replace(self._snapshot, line_ending=line_ending)
        self._recompute()

    def set_draft_text(self, text: str) -> None:
        self._snapshot = replace(self._snapshot, draft_text=text)
        self._recompute()

    def clear(self) -> None:
        self._snapshot = replace(self._snapshot, draft_text="", last_error=None)
        self._recompute()

    def load_payload(self, payload: bytes, *, mode: RawPacketInputMode = RawPacketInputMode.HEX) -> None:
        if mode == RawPacketInputMode.HEX:
            text = payload.hex(" ")
        elif mode == RawPacketInputMode.ASCII:
            text = payload.decode("ascii", errors="replace")
        else:
            text = payload.decode("utf-8", errors="replace")
        self._snapshot = replace(
            self._snapshot,
            input_mode=mode,
            line_ending=RawPacketLineEnding.NONE,
            draft_text=text,
            last_error=None,
        )
        self._recompute()

    def _recompute(self) -> None:
        payload: bytes
        try:
            payload = self._decode_payload(self._snapshot.draft_text, self._snapshot.input_mode)
            payload = payload + self._line_ending_bytes(self._snapshot.line_ending)
            last_error = None
        except ValueError as exc:
            payload = b""
            last_error = str(exc)

        self._snapshot = replace(
            self._snapshot,
            payload=payload,
            payload_hex=render_payload_hex(payload),
            payload_ascii=render_payload_ascii(payload),
            payload_utf8=render_payload_utf8(payload),
            last_error=last_error,
        )
        self._notify()

    def _decode_payload(self, text: str, mode: RawPacketInputMode) -> bytes:
        if mode == RawPacketInputMode.UTF8:
            return text.encode("utf-8")
        if mode == RawPacketInputMode.ASCII:
            try:
                return text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ASCII payload can only contain 7-bit ASCII characters.") from exc
        if not text.strip():
            return b""
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("HEX payload must contain complete hexadecimal bytes.") from exc

    def _line_ending_bytes(self, line_ending: RawPacketLineEnding) -> bytes:
        return {
            RawPacketLineEnding.NONE: b"",
            RawPacketLineEnding.CR: b"\r",
            RawPacketLineEnding.LF: b"\n",
            RawPacketLineEnding.CRLF: b"\r\n",
        }[line_ending]

    def _notify(self) -> None:
        snapshot = self._snapshot
        for listener in list(self._listeners):
            listener(snapshot)
