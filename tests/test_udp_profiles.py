from pathlib import Path

from protolink.core.udp_profiles import (
    UdpDraft,
    UdpPreset,
    UdpProfile,
    default_udp_profile_path,
    load_udp_profile,
    save_udp_profile,
)


def test_udp_profile_roundtrip(tmp_path: Path) -> None:
    path = default_udp_profile_path(tmp_path)
    profile = UdpProfile(
        selected_preset_name="Bench UDP",
        draft=UdpDraft(
            local_host="127.0.0.1",
            local_port=2000,
            remote_host="127.0.0.1",
            remote_port=3000,
            send_mode="ascii",
            line_ending="crlf",
            send_text="PING",
            selected_preset_name="Bench UDP",
        ),
        presets=[
            UdpPreset(
                name="Bench UDP",
                local_host="127.0.0.1",
                local_port=2000,
                remote_host="127.0.0.1",
                remote_port=3000,
                send_mode="ascii",
                line_ending="crlf",
                send_text="PING",
            )
        ],
    )

    save_udp_profile(path, profile)
    loaded = load_udp_profile(path)

    assert loaded.selected_preset_name == "Bench UDP"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.draft.line_ending == "crlf"
    assert loaded.presets[0].remote_port == 3000
