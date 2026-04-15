from __future__ import annotations

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
            return {'native_installer_scaffold_dir': str(tmp_path / 'scaffold')}
        if '--verify-native-installer-scaffold' in command:
            return {'checksum_matches': True}
        raise AssertionError(command)

    def fake_run_optional_json(command, *, cwd=None):
        if '--build-native-installer-msi' in command:
            return {
                'ok': True,
                'returncode': 0,
                'stdout': '',
                'stderr': '',
                'payload': {'output_file': str(tmp_path / 'ProtoLink.msi')},
            }
        if '--verify-native-installer-signature' in command:
            return {'ok': False, 'returncode': 1, 'stdout': '', 'stderr': 'unsigned', 'payload': None}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = fake_run_optional_json

    with pytest.raises(ns['VerificationError'], match='signed-and-ready'):
        execute(workspace=tmp_path / 'workspace', name='lane', require_signed=True)


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
