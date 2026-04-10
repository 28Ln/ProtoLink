from pathlib import Path

from protolink.core.serial_profiles import (
    SerialStudioDraft,
    SerialStudioPreset,
    SerialStudioProfile,
    default_serial_studio_profile_path,
    load_serial_studio_profile,
    save_serial_studio_profile,
)


def test_serial_studio_profile_roundtrip(tmp_path: Path) -> None:
    path = default_serial_studio_profile_path(tmp_path)
    profile = SerialStudioProfile(
        selected_preset_name="Bench A",
        draft=SerialStudioDraft(
            target="COM7",
            baudrate=19200,
            send_mode="ascii",
            line_ending="crlf",
            send_text="PING",
            selected_preset_name="Bench A",
        ),
        presets=[
            SerialStudioPreset(
                name="Bench A",
                target="COM7",
                baudrate=19200,
                send_mode="ascii",
                line_ending="crlf",
                send_text="PING",
            )
        ],
    )

    save_serial_studio_profile(path, profile)
    loaded = load_serial_studio_profile(path)

    assert loaded.selected_preset_name == "Bench A"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.draft.line_ending == "crlf"
    assert loaded.presets[0].target == "COM7"


def test_serial_studio_profile_backs_up_malformed_store(tmp_path: Path) -> None:
    path = default_serial_studio_profile_path(tmp_path)
    path.write_text("{not-json", encoding="utf-8")

    loaded = load_serial_studio_profile(path)

    assert loaded.format_version == "protolink-serial-studio-v1"
    assert loaded.draft.target == ""
    assert not path.exists()
    assert (path.parent / "serial_studio.json.invalid").read_text(encoding="utf-8") == "{not-json"


def test_serial_studio_profile_backs_up_unsupported_format_version(tmp_path: Path) -> None:
    path = default_serial_studio_profile_path(tmp_path)
    path.write_text('{"format_version": "future-version", "draft": {"target": "COM9"}}', encoding="utf-8")

    loaded = load_serial_studio_profile(path)

    assert loaded.format_version == "protolink-serial-studio-v1"
    assert loaded.draft.target == ""
    assert not path.exists()
    assert (path.parent / "serial_studio.json.invalid").exists()
