from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleStatus(StrEnum):
    BOOTSTRAPPED = "Bootstrapped"
    NEXT = "Next"
    PLANNED = "Planned"


@dataclass(frozen=True, slots=True)
class FeatureModule:
    key: str
    name: str
    area: str
    milestone: str
    status: ModuleStatus
    summary: str
    acceptance: tuple[str, ...]

