from pathlib import Path

from protolink.core.transport_profile_codec import load_transport_profile, save_transport_profile


def test_transport_profile_codec_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "transport_profile.json"
    save_transport_profile(
        path,
        profile_format_version="codec-v1",
        profile_selected_preset_name="Bench",
        draft_values={"host": "127.0.0.1", "port": 1883},
        draft_selected_preset_name="Bench",
        presets=[{"name": "Bench", "host": "127.0.0.1", "port": 1883}],
        preset_name_getter=lambda preset: preset["name"],
        preset_values_getter=lambda preset: {"host": preset["host"], "port": preset["port"]},
    )

    loaded = load_transport_profile(
        path,
        format_version="codec-v1",
        default_values={"host": "0.0.0.0", "port": 0},
        build_draft=lambda values, selected: {"values": values, "selected": selected},
        build_preset=lambda name, values: {"name": name, "values": values},
        build_profile=lambda version, selected, draft, presets: {
            "version": version,
            "selected": selected,
            "draft": draft,
            "presets": presets,
        },
    )

    assert loaded["version"] == "codec-v1"
    assert loaded["selected"] == "Bench"
    assert loaded["draft"]["values"]["host"] == "127.0.0.1"
    assert loaded["presets"][0]["name"] == "Bench"


def test_transport_profile_codec_falls_back_for_empty_store_file(tmp_path: Path) -> None:
    path = tmp_path / "transport_profile.json"
    path.write_text("", encoding="utf-8")

    loaded = load_transport_profile(
        path,
        format_version="codec-v1",
        default_values={"host": "0.0.0.0", "port": 0},
        build_draft=lambda values, selected: {"values": values, "selected": selected},
        build_preset=lambda name, values: {"name": name, "values": values},
        build_profile=lambda version, selected, draft, presets: {
            "version": version,
            "selected": selected,
            "draft": draft,
            "presets": presets,
        },
    )

    assert loaded["version"] == "codec-v1"
    assert loaded["selected"] is None
    assert loaded["draft"]["values"] == {"host": "0.0.0.0", "port": 0}
    assert loaded["presets"] == []
