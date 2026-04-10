from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypeVar

from protolink.core.preset_profile_store import (
    PresetProfileDraft,
    PresetProfileEntry,
    PresetProfileStore,
    ProfileValue,
    load_preset_profile_store,
    save_preset_profile_store,
)

DraftT = TypeVar("DraftT")
PresetT = TypeVar("PresetT")
ProfileT = TypeVar("ProfileT")


def load_transport_profile(
    path: Path,
    *,
    format_version: str,
    default_values: dict[str, ProfileValue],
    build_draft: Callable[[dict[str, ProfileValue], str | None], DraftT],
    build_preset: Callable[[str, dict[str, ProfileValue]], PresetT],
    build_profile: Callable[[str, str | None, DraftT, list[PresetT]], ProfileT],
) -> ProfileT:
    store = load_preset_profile_store(
        path,
        format_version=format_version,
        default_values=default_values,
    )
    draft = build_draft(store.draft.values, store.draft.selected_preset_name)
    presets = [build_preset(entry.name, entry.values) for entry in store.presets]
    return build_profile(store.format_version, store.selected_preset_name, draft, presets)


def save_transport_profile(
    path: Path,
    *,
    profile_format_version: str,
    profile_selected_preset_name: str | None,
    draft_values: Mapping[str, ProfileValue],
    draft_selected_preset_name: str | None,
    presets: list[PresetT],
    preset_name_getter: Callable[[PresetT], str],
    preset_values_getter: Callable[[PresetT], Mapping[str, ProfileValue]],
) -> None:
    save_preset_profile_store(
        path,
        PresetProfileStore(
            format_version=profile_format_version,
            selected_preset_name=profile_selected_preset_name,
            draft=PresetProfileDraft(
                values=dict(draft_values),
                selected_preset_name=draft_selected_preset_name,
            ),
            presets=[
                PresetProfileEntry(
                    name=preset_name_getter(preset),
                    values=dict(preset_values_getter(preset)),
                )
                for preset in presets
            ],
        ),
    )
