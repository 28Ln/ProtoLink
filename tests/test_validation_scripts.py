from __future__ import annotations

import json
import importlib
import runpy
import subprocess
from pathlib import Path

import pytest


def _load_script(script_name: str) -> dict[str, object]:
    script_file = Path(__file__).resolve().parents[1] / 'scripts' / script_name
    return runpy.run_path(str(script_file), run_name=f'{script_name}_test_module')


def test_execute_full_test_suite_aggregates_file_results(tmp_path: Path) -> None:
    ns = _load_script('run_full_test_suite.py')

    file_a = tmp_path / 'tests' / 'test_a.py'
    file_b = tmp_path / 'tests' / 'test_b.py'
    file_a.parent.mkdir(parents=True)
    file_a.write_text('pass', encoding='utf-8')
    file_b.write_text('pass', encoding='utf-8')

    outputs = {
        str(file_a): '...                                                                      [100%]\n3 passed in 0.10s\n',
        str(file_b): '..                                                                       [100%]\n2 passed in 0.08s\n',
    }

    def fake_discover_test_files():
        return (file_a, file_b)

    def fake_run(command, cwd=None, text=None, capture_output=None, check=None):
        test_file = command[-1]
        return subprocess.CompletedProcess(command, 0, stdout=outputs[test_file], stderr='')

    execute = ns['execute_full_test_suite']
    execute.__globals__['discover_test_files'] = fake_discover_test_files
    execute.__globals__['subprocess'].run = fake_run

    result = execute()

    assert result['test_file_count'] == 2
    assert result['passed_count'] == 5
    assert [item['passed_count'] for item in result['file_results']] == [3, 2]


def test_execute_full_test_suite_fails_on_nonzero_file_run(tmp_path: Path) -> None:
    ns = _load_script('run_full_test_suite.py')

    file_a = tmp_path / 'tests' / 'test_a.py'
    file_a.parent.mkdir(parents=True)
    file_a.write_text('pass', encoding='utf-8')

    def fake_discover_test_files():
        return (file_a,)

    def fake_run(command, cwd=None, text=None, capture_output=None, check=None):
        return subprocess.CompletedProcess(command, 1, stdout='F                                                                        [100%]\n1 failed in 0.10s\n', stderr='')

    execute = ns['execute_full_test_suite']
    execute.__globals__['discover_test_files'] = fake_discover_test_files
    execute.__globals__['subprocess'].run = fake_run

    with pytest.raises(ns['VerificationError'], match='Full test suite file run failed'):
        execute()


def test_execute_full_test_suite_accepts_nonzero_exit_when_output_is_clean(tmp_path: Path) -> None:
    ns = _load_script('run_full_test_suite.py')

    file_a = tmp_path / 'tests' / 'test_a.py'
    file_a.parent.mkdir(parents=True)
    file_a.write_text('pass', encoding='utf-8')

    def fake_discover_test_files():
        return (file_a,)

    def fake_run(command, cwd=None, text=None, capture_output=None, check=None):
        return subprocess.CompletedProcess(command, 3221225477, stdout='..                                                                       [100%]\n2 passed in 0.08s\n', stderr='')

    execute = ns['execute_full_test_suite']
    execute.__globals__['discover_test_files'] = fake_discover_test_files
    execute.__globals__['subprocess'].run = fake_run

    result = execute()

    assert result['passed_count'] == 2


def test_execute_full_test_suite_retries_retryable_crash(tmp_path: Path) -> None:
    ns = _load_script('run_full_test_suite.py')

    file_a = tmp_path / 'tests' / 'test_a.py'
    file_a.parent.mkdir(parents=True)
    file_a.write_text('pass', encoding='utf-8')
    calls = {'count': 0}

    def fake_discover_test_files():
        return (file_a,)

    def fake_run(command, cwd=None, text=None, capture_output=None, check=None):
        calls['count'] += 1
        if calls['count'] == 1:
            return subprocess.CompletedProcess(
                command,
                3221226356,
                stdout='...\n',
                stderr='Windows fatal exception: code 0xc0000374\n',
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='..                                                                       [100%]\n2 passed in 0.08s\n',
            stderr='',
        )

    execute = ns['execute_full_test_suite']
    execute.__globals__['discover_test_files'] = fake_discover_test_files
    execute.__globals__['subprocess'].run = fake_run

    result = execute()

    assert calls['count'] == 2
    assert result['passed_count'] == 2
    assert result['file_results'][0]['attempt_count'] == 2


def test_execute_full_test_suite_retries_retryable_exit_code_without_stderr_marker(tmp_path: Path) -> None:
    ns = _load_script('run_full_test_suite.py')

    file_a = tmp_path / 'tests' / 'test_a.py'
    file_a.parent.mkdir(parents=True)
    file_a.write_text('pass', encoding='utf-8')
    calls = {'count': 0}

    def fake_discover_test_files():
        return (file_a,)

    def fake_run(command, cwd=None, text=None, capture_output=None, check=None):
        calls['count'] += 1
        if calls['count'] == 1:
            return subprocess.CompletedProcess(command, 3221226356, stdout='....                                                                     [100%]\n', stderr='')
        return subprocess.CompletedProcess(command, 0, stdout='..                                                                       [100%]\n2 passed in 0.08s\n', stderr='')

    execute = ns['execute_full_test_suite']
    execute.__globals__['discover_test_files'] = fake_discover_test_files
    execute.__globals__['subprocess'].run = fake_run

    result = execute()

    assert calls['count'] == 2
    assert result['passed_count'] == 2


def test_execute_native_installer_lane_handles_missing_toolchain_with_structured_result(tmp_path: Path) -> None:
    ns = _load_script('verify_native_installer_lane.py')

    def fake_run_json(command, *, cwd=None):
        if '--verify-native-installer-toolchain' in command:
            return {
                'ready': False,
                'tools': {
                    'wix': {'available': False},
                    'signtool': {'available': False},
                },
            }
        if '--build-native-installer-scaffold' in command:
            return {'native_installer_scaffold_dir': str(tmp_path / 'scaffold')}
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    result = execute(workspace=tmp_path / 'workspace', name='lane')

    assert result['toolchain']['ready'] is False
    assert result['scaffold_build']['native_installer_scaffold_dir'].endswith('scaffold')
    assert result['stage_status']['scaffold_built'] is True
    assert result['stage_status']['scaffold_verified'] is True
    assert result['stage_status']['toolchain_ready'] is False
    assert result['readiness']['ready_for_build'] is False
    assert result['readiness']['ready_for_signing'] is False
    assert result['lane_status'] == 'toolchain_missing'
    assert 'native_installer_wix_missing' in result['blocking_items']
    assert 'native_installer_signtool_missing' in result['blocking_items']
    assert any('Install WiX Toolset v4' in item for item in result['next_actions'])
    assert 'native_installer_manifest' not in result['scaffold_build']
    assert result['ready_for_release'] is False


def test_execute_native_installer_lane_raises_when_toolchain_is_required(tmp_path: Path) -> None:
    ns = _load_script('verify_native_installer_lane.py')

    def fake_run_json(command, *, cwd=None):
        if '--verify-native-installer-toolchain' in command:
            return {
                'ready': False,
                'tools': {
                    'wix': {'available': False},
                    'signtool': {'available': False},
                },
            }
        if '--build-native-installer-scaffold' in command:
            return {'native_installer_scaffold_dir': str(tmp_path / 'scaffold')}
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    with pytest.raises(ns['VerificationError'], match='toolchain'):
        execute(workspace=tmp_path / 'workspace', name='lane', require_toolchain=True)


def test_execute_native_installer_lane_raises_when_signature_is_required(tmp_path: Path) -> None:
    ns = _load_script('verify_native_installer_lane.py')

    def fake_run_json(command, *, cwd=None):
        if '--verify-native-installer-toolchain' in command:
            return {
                'ready': True,
                'tools': {
                    'wix': {'available': True},
                    'signtool': {'available': True},
                },
            }
        if '--build-native-installer-scaffold' in command:
            return {
                'native_installer_scaffold_dir': str(tmp_path / 'scaffold'),
                'native_installer_payload_file': str(tmp_path / 'scaffold' / 'payload' / 'installer.zip'),
            }
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    def fake_run_optional_json(command, *, cwd=None):
        if '--build-native-installer-msi' in command:
            installer_file = tmp_path / 'ProtoLink.msi'
            installer_file.write_text('msi', encoding='utf-8')
            return {
                'ok': True,
                'returncode': 0,
                'stdout': '',
                'stderr': '',
                'payload': {'output_file': str(installer_file)},
            }
        if '--verify-installer-package' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '{}', 'stderr': '', 'payload': {'checksum_matches': True}}
        if '--install-installer-package' in command:
            install_dir = Path(command[-1])
            (install_dir / 'runtime').mkdir(parents=True, exist_ok=True)
            (install_dir / 'sp').mkdir(parents=True, exist_ok=True)
            (install_dir / 'workspace').mkdir(parents=True, exist_ok=True)
            (install_dir / '.protolink').mkdir(parents=True, exist_ok=True)
            (install_dir / 'runtime' / 'python.exe').write_text('runtime', encoding='utf-8')
            (install_dir / '.protolink' / 'app_settings.json').write_text('{}', encoding='utf-8')
            return {
                'ok': True,
                'returncode': 0,
                'stdout': '{}',
                'stderr': '',
                'payload': {'install_dir': str(install_dir)},
            }
        if '--uninstall-portable-package' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '{}', 'stderr': '', 'payload': {'removed_receipt': True}}
        if '--build-native-installer-msi' in command:
            raise AssertionError('duplicate build-native-installer-msi handler')
        if '--verify-native-installer-signature' in command:
            return {'ok': False, 'returncode': 1, 'stdout': '', 'stderr': 'unsigned', 'payload': None}
        raise AssertionError(command)

    def fake_run_optional_command(command, *, cwd=None, env=None):
        if command[0].lower() == 'msiexec' and '/i' in command:
            install_root = next(Path(arg.split('=', 1)[1]) for arg in command if arg.startswith('INSTALLDIR='))
            payload_dir = install_root / 'payload'
            payload_dir.mkdir(parents=True, exist_ok=True)
            (payload_dir / 'installer.zip').write_text('payload', encoding='utf-8')
            return {'ok': True, 'returncode': 0, 'stdout': '', 'stderr': ''}
        if command[0].lower() == 'msiexec' and '/x' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '', 'stderr': ''}
        if command[0].endswith('python.exe'):
            install_dir = Path(command[0]).parents[1]
            return {
                'ok': True,
                'returncode': 0,
                'stdout': (
                    'ProtoLink\n'
                    f'工作区：{install_dir / "workspace"}\n'
                    f'设置：{install_dir / ".protolink" / "app_settings.json"}\n'
                    '已注册传输：6\n'
                    '模块数：15\n'
                ),
                'stderr': '',
            }
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = fake_run_optional_json
    execute.__globals__['_run_optional_command'] = fake_run_optional_command

    with pytest.raises(ns['VerificationError'], match='signed-and-ready'):
        execute(workspace=tmp_path / 'workspace', name='lane', require_signed=True)


def test_execute_native_installer_lane_reports_signature_not_ready_with_structured_result(tmp_path: Path) -> None:
    ns = _load_script('verify_native_installer_lane.py')

    def fake_run_json(command, *, cwd=None):
        if '--verify-native-installer-toolchain' in command:
            return {
                'ready': True,
                'tools': {
                    'wix': {'available': True},
                    'signtool': {'available': True},
                },
            }
        if '--build-native-installer-scaffold' in command:
            return {
                'native_installer_scaffold_dir': str(tmp_path / 'scaffold'),
                'native_installer_payload_file': str(tmp_path / 'scaffold' / 'payload' / 'installer.zip'),
            }
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    def fake_run_optional_json(command, *, cwd=None):
        if '--build-native-installer-msi' in command:
            installer_file = tmp_path / 'ProtoLink.msi'
            installer_file.write_text('msi', encoding='utf-8')
            return {
                'ok': True,
                'returncode': 0,
                'stdout': '',
                'stderr': '',
                'payload': {'output_file': str(installer_file)},
            }
        if '--verify-installer-package' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '{}', 'stderr': '', 'payload': {'checksum_matches': True}}
        if '--install-installer-package' in command:
            install_dir = Path(command[-1])
            (install_dir / 'runtime').mkdir(parents=True, exist_ok=True)
            (install_dir / 'sp').mkdir(parents=True, exist_ok=True)
            (install_dir / 'workspace').mkdir(parents=True, exist_ok=True)
            (install_dir / '.protolink').mkdir(parents=True, exist_ok=True)
            (install_dir / 'runtime' / 'python.exe').write_text('runtime', encoding='utf-8')
            (install_dir / '.protolink' / 'app_settings.json').write_text('{}', encoding='utf-8')
            return {
                'ok': True,
                'returncode': 0,
                'stdout': '{}',
                'stderr': '',
                'payload': {'install_dir': str(install_dir)},
            }
        if '--uninstall-portable-package' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '{}', 'stderr': '', 'payload': {'removed_receipt': True}}
        if '--verify-native-installer-signature' in command:
            return {'ok': False, 'returncode': 1, 'stdout': '', 'stderr': 'unsigned', 'payload': None}
        raise AssertionError(command)

    def fake_run_optional_command(command, *, cwd=None, env=None):
        if command[0].lower() == 'msiexec' and '/i' in command:
            install_root = next(Path(arg.split('=', 1)[1]) for arg in command if arg.startswith('INSTALLDIR='))
            payload_dir = install_root / 'payload'
            payload_dir.mkdir(parents=True, exist_ok=True)
            (payload_dir / 'installer.zip').write_text('payload', encoding='utf-8')
            return {'ok': True, 'returncode': 0, 'stdout': '', 'stderr': ''}
        if command[0].lower() == 'msiexec' and '/x' in command:
            return {'ok': True, 'returncode': 0, 'stdout': '', 'stderr': ''}
        if command[0].endswith('python.exe'):
            install_dir = Path(command[0]).parents[1]
            return {
                'ok': True,
                'returncode': 0,
                'stdout': (
                    'ProtoLink\n'
                    f'工作区：{install_dir / "workspace"}\n'
                    f'设置：{install_dir / ".protolink" / "app_settings.json"}\n'
                    '已注册传输：6\n'
                    '模块数：15\n'
                ),
                'stderr': '',
            }
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = fake_run_optional_json
    execute.__globals__['_run_optional_command'] = fake_run_optional_command

    result = execute(workspace=tmp_path / 'workspace', name='lane')

    assert result['msi_file'].endswith('ProtoLink.msi')
    assert result['readiness']['ready_for_build'] is True
    assert result['readiness']['ready_for_install_verification'] is True
    assert result['readiness']['ready_for_signing'] is True
    assert result['readiness']['ready_for_release'] is False
    assert result['stage_status']['msi_installed'] is True
    assert result['stage_status']['installed_payload_verified'] is True
    assert result['stage_status']['installed_payload_runnable'] is True
    assert result['stage_status']['msi_uninstalled'] is True
    assert result['lane_status'] == 'signature_not_ready'
    assert 'native_installer_signature_not_verified' in result['blocking_items']
    assert any('Fix Authenticode signing' in item for item in result['next_actions'])
    assert result['ready_for_release'] is False


def test_execute_native_installer_lane_reports_temporary_root_when_workspace_is_implicit(tmp_path: Path) -> None:
    ns = _load_script('verify_native_installer_lane.py')

    def fake_run_json(command, *, cwd=None):
        if '--verify-native-installer-toolchain' in command:
            return {
                'ready': False,
                'tools': {
                    'wix': {'available': False},
                    'signtool': {'available': False},
                },
            }
        if '--build-native-installer-scaffold' in command:
            return {'native_installer_scaffold_dir': str(tmp_path / 'scaffold')}
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    result = execute(workspace=None, name='lane')

    assert result['temporary_root'] is not None
    assert Path(result['temporary_root']).exists()
    assert str(Path(result['workspace']).parent) == result['temporary_root']


def test_execute_soak_validation_runs_multiple_cycles(tmp_path: Path) -> None:
    ns = _load_script('run_soak_validation.py')

    def fake_run_json(command, *, cwd=None):
        if '--generate-smoke-artifacts' in command:
            return {'log_file': 'log', 'capture_file': 'capture', 'replay_step_count': 2}
        if '--release-preflight' in command:
            return {'ready': True, 'blocking_items': []}
        raise AssertionError(command)

    def fake_run_text(command, *, cwd=None):
        if '--headless-summary' in command:
            return 'ProtoLink\n工作区：X\n设置：Y\n已注册传输：6\n模块数：15\n'
        if '--smoke-check' in command:
            return 'smoke-check-ok\n'
        raise AssertionError(command)

    execute = ns['execute_soak_validation']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_text'] = fake_run_text

    result = execute(workspace=tmp_path / 'workspace', cycles=2, sleep_ms=0)

    assert result['cycles'] == 2
    assert result['ready_cycles'] == 2
    assert result['all_cycles_ready'] is True
    assert result['failing_cycles'] == []
    assert result['total_duration_ms'] >= 0
    assert len(result['cycle_results']) == 2
    assert result['cycle_results'][0]['cycle_ready'] is True
    assert result['cycle_results'][0]['smoke_ok'] is True
    assert result['cycle_results'][0]['headless_summary_markers']['工作区：'] is True


def test_execute_soak_validation_raises_when_all_ready_is_required(tmp_path: Path) -> None:
    ns = _load_script('run_soak_validation.py')

    def fake_run_json(command, *, cwd=None):
        if '--generate-smoke-artifacts' in command:
            return {'log_file': 'log', 'capture_file': 'capture', 'replay_step_count': 2}
        if '--release-preflight' in command:
            return {'ready': False, 'blocking_items': ['shutdown failure']}
        raise AssertionError(command)

    def fake_run_text(command, *, cwd=None):
        if '--headless-summary' in command:
            return 'ProtoLink\n工作区：X\n设置：Y\n已注册传输：6\n模块数：15\n'
        if '--smoke-check' in command:
            return 'smoke-check-ok\n'
        raise AssertionError(command)

    execute = ns['execute_soak_validation']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_text'] = fake_run_text

    with pytest.raises(ns['VerificationError'], match='failing cycle'):
        execute(workspace=tmp_path / 'workspace', cycles=1, sleep_ms=0, require_all_ready=True)


def test_execute_release_staging_reports_native_installer_lane(tmp_path: Path) -> None:
    ns = _load_script('verify_release_staging.py')
    workspace = tmp_path / 'workspace'
    temp_root = workspace.parent
    install_dir = temp_root / 'installer-install'
    staging_dir = temp_root / 'installer-staging'
    install_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(str(part) for part in command)
        if '--generate-smoke-artifacts' in command_text:
            return {'log_file': 'log', 'capture_file': 'capture', 'replay_step_count': 2}
        if '--build-installer-package' in command_text:
            return {
                'release_archive_file': str(tmp_path / 'release.zip'),
                'portable_archive_file': str(tmp_path / 'portable.zip'),
                'distribution_archive_file': str(tmp_path / 'distribution.zip'),
                'installer_archive_file': str(tmp_path / 'installer.zip'),
            }
        if '--verify-portable-package' in command_text:
            return {'archive_file': 'portable.zip', 'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'archive_file': 'distribution.zip', 'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'archive_file': 'installer.zip', 'checksum_matches': True}
        if '--install-installer-package' in command_text:
            (install_dir / 'runtime').mkdir(parents=True, exist_ok=True)
            (install_dir / 'sp').mkdir(parents=True, exist_ok=True)
            (install_dir / '.protolink').mkdir(parents=True, exist_ok=True)
            (install_dir / 'workspace').mkdir(parents=True, exist_ok=True)
            for file_name in ('INSTALL.ps1', 'Launch-ProtoLink.ps1', 'Launch-ProtoLink.bat', 'ProtoLink.exe'):
                (install_dir / file_name).write_text(file_name, encoding='utf-8')
            (install_dir / 'runtime' / 'python.exe').write_text('runtime', encoding='utf-8')
            (install_dir / '.protolink' / 'app_settings.json').write_text('{}', encoding='utf-8')
            manifest_files = {
                'installer_package_manifest_file': staging_dir / 'installer-package-manifest.json',
                'installer_manifest_file': staging_dir / 'installer-manifest.json',
                'distribution_manifest_file': staging_dir / 'distribution-manifest.json',
                'portable_receipt_file': install_dir / 'install-receipt.json',
            }
            for path in manifest_files.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}', encoding='utf-8')
            return {
                'archive_file': str(tmp_path / 'installer.zip'),
                'install_dir': str(install_dir),
                'portable_receipt_file': str(manifest_files['portable_receipt_file']),
                **{key: str(value) for key, value in manifest_files.items()},
            }
        if '--uninstall-portable-package' in command_text:
            return {'target_dir': str(install_dir), 'removed_receipt': True}
        if 'verify_native_installer_lane.py' in command_text:
            return {
                'lane_status': 'toolchain_missing',
                'blocking_items': ['native_installer_wix_missing'],
                'next_actions': ['Install WiX Toolset v4 or set PROTOLINK_WIX before attempting MSI builds.'],
                'readiness': {
                    'ready_for_build': False,
                    'ready_for_install_verification': False,
                    'ready_for_signing': False,
                    'ready_for_release': False,
                },
            }
        raise AssertionError(command)

    def fake_run_command(command, *, cwd=None, env=None):
        rendered = ' '.join(str(part) for part in command)
        if (
            '--headless-summary' in rendered
            or 'INSTALL.ps1' in rendered
            or 'Launch-ProtoLink.ps1' in rendered
            or 'Launch-ProtoLink.bat' in rendered
        ):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    'ProtoLink\n'
                    f'工作区：{install_dir / "workspace"}\n'
                    f'设置：{install_dir / ".protolink" / "app_settings.json"}\n'
                    '已注册传输：6\n'
                    '模块数：15\n'
                ),
                stderr='',
            )
        raise AssertionError(command)

    execute = ns['execute_release_staging']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_command'] = fake_run_command

    result = execute(workspace=workspace, name='stage', include_native_installer_lane=True)

    assert result['verify_installer_package']['checksum_matches'] is True
    assert result['launcher_exe_headless_summary']['workspace'].endswith('installer-install\\workspace')
    assert result['native_installer_lane']['lane_status'] == 'toolchain_missing'
    assert result['native_installer_lane']['readiness']['ready_for_release'] is False
    assert 'native_installer_wix_missing' in result['native_installer_lane']['blocking_items']


def test_execute_release_deliverables_copies_and_reports_artifacts(tmp_path: Path) -> None:
    ns = _load_script('build_release_deliverables.py')
    workspace = tmp_path / 'workspace'
    target_dir = tmp_path / 'deliverables'
    build_root = tmp_path / 'build-root'
    build_root.mkdir()
    release_archive = build_root / 'release.zip'
    portable_archive = build_root / 'portable.zip'
    distribution_archive = build_root / 'distribution.zip'
    installer_archive = build_root / 'installer.zip'
    for file in (release_archive, portable_archive, distribution_archive, installer_archive):
        file.write_text(file.stem, encoding='utf-8')

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(command)
        if '--build-installer-package' in command_text:
            return {
                'release_archive_file': str(release_archive),
                'portable_archive_file': str(portable_archive),
                'distribution_archive_file': str(distribution_archive),
                'installer_archive_file': str(installer_archive),
            }
        if '--verify-portable-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'checksum_matches': True}
        raise AssertionError(command)

    execute = ns['execute_release_deliverables']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_project_version'] = lambda: '0.2.5'
    execute.__globals__['_run_install_smoke'] = lambda installer_archive, target_dir: {'launch_script': 'Launch-ProtoLink.ps1'}

    result = execute(
        name='release-0.2.5',
        workspace=workspace,
        target_dir=target_dir,
        skip_install_smoke=False,
    )

    assert Path(result['copied_artifacts']['installer_archive']).exists()
    assert Path(result['copied_artifacts']['portable_archive']).exists()
    assert result['verification']['installer']['checksum_matches'] is True
    assert result['install_smoke']['launch_script'] == 'Launch-ProtoLink.ps1'


def test_parse_gui_audit_resolution_rejects_invalid_token() -> None:
    ns = _load_script('audit_gui_layout.py')

    with pytest.raises(ns['VerificationError'], match='WIDTHxHEIGHT'):
        ns['_parse_resolution']('bad-resolution')


def test_execute_gui_layout_audit_writes_json_and_artifacts(tmp_path: Path) -> None:
    pytest.importorskip("PySide6.QtWidgets")
    importlib.reload(subprocess)
    ns = _load_script('audit_gui_layout.py')

    execute = ns['execute_gui_layout_audit']
    result = execute(
        workspace=tmp_path / 'workspace',
        output_dir=tmp_path / 'audit-output',
        resolutions=[(1180, 760)],
        module_keys=['dashboard', 'serial_studio'],
        keep_artifacts=True,
    )

    json_file = Path(result['json_file'])
    assert json_file.exists()
    payload = json.loads(json_file.read_text(encoding='utf-8'))

    assert payload['summary']['resolution_count'] == 1
    assert payload['summary']['module_audit_count'] == 2
    assert payload['summary']['screenshot_count'] >= 5
    assert len(payload['resolution_results']) == 1
    resolution_result = payload['resolution_results'][0]
    assert resolution_result['resolution']['label'] == '1180x760'
    assert 'window_metrics' in resolution_result
    assert 'packet_console' in resolution_result
    assert len(resolution_result['module_results']) == 2
    assert Path(resolution_result['packet_console']['screenshot_file']).exists()

    dashboard_result = next(item for item in resolution_result['module_results'] if item['module_key'] == 'dashboard')
    serial_result = next(item for item in resolution_result['module_results'] if item['module_key'] == 'serial_studio')
    assert Path(dashboard_result['screenshots']['window']).exists()
    assert Path(dashboard_result['screenshots']['panel']).exists()
    assert Path(serial_result['screenshots']['window']).exists()
    assert Path(serial_result['screenshots']['panel']).exists()
    assert 'overflow_summary' in serial_result
    assert 'panel' in serial_result
