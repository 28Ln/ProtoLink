from protolink.core.errors import CliExitCode, ProtoLinkUserError, format_cli_error, format_unexpected_cli_error


def test_format_cli_error_includes_action_and_recovery() -> None:
    error = ProtoLinkUserError(
        message="Port enumeration is unavailable.",
        action="list serial ports",
        recovery="Install the required driver and retry.",
    )

    assert (
        format_cli_error(error)
        == "list serial ports failed: Port enumeration is unavailable. Recovery: Install the required driver and retry."
    )


def test_format_unexpected_cli_error_is_stable() -> None:
    assert format_unexpected_cli_error("CLI command", RuntimeError("boom")) == "CLI command failed: boom"
    assert int(CliExitCode.USER_ERROR) == 2
