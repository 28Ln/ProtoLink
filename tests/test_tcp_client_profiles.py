from pathlib import Path

from protolink.core.tcp_client_profiles import (
    TcpClientDraft,
    TcpClientPreset,
    TcpClientProfile,
    default_tcp_client_profile_path,
    load_tcp_client_profile,
    save_tcp_client_profile,
)


def test_tcp_client_profile_roundtrip(tmp_path: Path) -> None:
    path = default_tcp_client_profile_path(tmp_path)
    profile = TcpClientProfile(
        selected_preset_name="Bench Echo",
        draft=TcpClientDraft(
            host="127.0.0.1",
            port=9000,
            send_mode="ascii",
            line_ending="crlf",
            send_text="PING",
            selected_preset_name="Bench Echo",
        ),
        presets=[
            TcpClientPreset(
                name="Bench Echo",
                host="127.0.0.1",
                port=9000,
                send_mode="ascii",
                line_ending="crlf",
                send_text="PING",
            )
        ],
    )

    save_tcp_client_profile(path, profile)
    loaded = load_tcp_client_profile(path)

    assert loaded.selected_preset_name == "Bench Echo"
    assert loaded.draft.send_mode == "ascii"
    assert loaded.draft.line_ending == "crlf"
    assert loaded.presets[0].port == 9000
