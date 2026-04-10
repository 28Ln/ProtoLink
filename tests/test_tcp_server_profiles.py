from pathlib import Path

from protolink.core.tcp_server_profiles import (
    TcpServerDraft,
    TcpServerPreset,
    TcpServerProfile,
    default_tcp_server_profile_path,
    load_tcp_server_profile,
    save_tcp_server_profile,
)


def test_tcp_server_profile_roundtrip(tmp_path: Path) -> None:
    path = default_tcp_server_profile_path(tmp_path)
    profile = TcpServerProfile(
        selected_preset_name="Bench Server",
        draft=TcpServerDraft(
            host="127.0.0.1",
            port=9010,
            send_mode="ascii",
            line_ending="crlf",
            send_text="READY",
            selected_preset_name="Bench Server",
        ),
        presets=[
            TcpServerPreset(
                name="Bench Server",
                host="127.0.0.1",
                port=9010,
                send_mode="ascii",
                line_ending="crlf",
                send_text="READY",
            )
        ],
    )

    save_tcp_server_profile(path, profile)
    loaded = load_tcp_server_profile(path)

    assert loaded.selected_preset_name == "Bench Server"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.draft.line_ending == "crlf"
    assert loaded.presets[0].port == 9010
