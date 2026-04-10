from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimedTask:
    name: str
    rule_name: str
    interval_seconds: float
    enabled: bool = True
