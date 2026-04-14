from protolink.core.errors import CliExitCode, ProtoLinkUserError, format_cli_error, format_unexpected_cli_error


def test_format_cli_error_includes_action_and_recovery() -> None:
    error = ProtoLinkUserError(
        message="串口枚举不可用。",
        action="列出串口",
        recovery="请安装所需驱动后重试。",
    )

    assert (
        format_cli_error(error)
        == "列出串口失败： 串口枚举不可用。 恢复建议：请安装所需驱动后重试。"
    )


def test_format_unexpected_cli_error_is_stable() -> None:
    assert format_unexpected_cli_error("命令行命令", RuntimeError("boom")) == "命令行命令失败：boom"
    assert int(CliExitCode.USER_ERROR) == 2
