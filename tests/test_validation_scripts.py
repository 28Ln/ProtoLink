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
            return {'checksum_matches': True, 'lifecycle_contract_ready': True}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    result = execute(workspace=tmp_path / 'workspace', name='lane')

    assert result['toolchain']['ready'] is False
    assert result['scaffold_build']['native_installer_scaffold_dir'].endswith('scaffold')
    assert result['stage_status']['scaffold_built'] is True
    assert result['stage_status']['scaffold_verified'] is True
    assert result['stage_status']['lifecycle_contract_ready'] is True
    assert result['stage_status']['toolchain_ready'] is False
    assert 'native_installer_manifest' not in result['scaffold_build']
    assert result['ready_for_release'] is False
    assert result['cutover_policy']['current_canonical_release_lane'] == 'bundled-runtime-installer-package'
    assert result['cutover_policy']['native_installer_lane_phase'] == 'probe-only'
    assert result['cutover_policy']['probe_ready'] is True
    assert result['cutover_policy']['cutover_ready'] is False
    assert result['cutover_policy']['blocking_items'] == ['missing_wix', 'missing_signtool']
    assert result['cutover_policy']['next_action'] == 'install_wix_and_signtool'
    assert 'documented_release_approval' in result['cutover_policy']['manual_cutover_requirements']


def test_main_writes_native_installer_lane_receipt_file(tmp_path: Path, capsys) -> None:
    ns = _load_script('verify_native_installer_lane.py')
    receipt_file = tmp_path / 'native-installer-lane-receipt.json'
    workspace = tmp_path / 'workspace'
    result_payload = {
        'generated_at': '2026-04-16T00:00:00+00:00',
        'workspace': str(workspace),
        'temporary_root': None,
        'duration_ms': 1.0,
        'stage_status': {
            'toolchain_ready': False,
            'scaffold_built': True,
            'scaffold_verified': True,
            'lifecycle_contract_ready': True,
            'msi_built': False,
            'signature_verified': False,
        },
        'cutover_policy': {
            'current_canonical_release_lane': 'bundled-runtime-installer-package',
            'native_installer_lane_phase': 'probe-only',
            'probe_ready': True,
            'cutover_ready': False,
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'next_action': 'install_wix_and_signtool',
            'manual_cutover_requirements': ['approved_code_signing_certificate'],
        },
        'toolchain': {'ready': False},
        'scaffold_build': {'native_installer_scaffold_dir': str(tmp_path / 'scaffold')},
        'scaffold_verify': {'checksum_matches': True, 'lifecycle_contract_ready': True},
        'msi_build': None,
        'signature_verify': None,
        'ready_for_release': False,
    }

    args = type(
        'Args',
        (),
        {
            'workspace': workspace,
            'name': 'lane',
            'receipt_file': receipt_file,
            'require_toolchain': False,
            'require_signed': False,
            'keep_artifacts': True,
        },
    )()

    class _FakeParser:
        def parse_args(self):
            return args

    ns['main'].__globals__['build_parser'] = lambda: _FakeParser()
    ns['main'].__globals__['execute_native_installer_lane'] = lambda **kwargs: result_payload

    exit_code = ns['main']()
    captured = capsys.readouterr()
    stored_payload = json.loads(receipt_file.read_text(encoding='utf-8'))

    assert exit_code == 0
    assert json.loads(captured.out)['cutover_policy']['native_installer_lane_phase'] == 'probe-only'
    assert stored_payload['stage_status']['lifecycle_contract_ready'] is True
    assert stored_payload['cutover_policy']['native_installer_lane_phase'] == 'probe-only'


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
            return {'checksum_matches': True, 'lifecycle_contract_ready': True}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    with pytest.raises(ns['VerificationError'], match='toolchain'):
        execute(workspace=tmp_path / 'workspace', name='lane', require_toolchain=True)


def test_execute_native_installer_lane_reports_contract_blocker_before_toolchain(tmp_path: Path) -> None:
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
            return {'checksum_matches': True, 'lifecycle_contract_ready': False}
        raise AssertionError(command)

    execute = ns['execute_native_installer_lane']
    execute.__globals__['_run_json'] = fake_run_json
    execute.__globals__['_run_optional_json'] = lambda *args, **kwargs: {'ok': False, 'returncode': 2, 'stdout': '', 'stderr': '', 'payload': None}

    result = execute(workspace=tmp_path / 'workspace', name='lane')

    assert result['stage_status']['scaffold_verified'] is True
    assert result['stage_status']['lifecycle_contract_ready'] is False
    assert result['cutover_policy']['native_installer_lane_phase'] == 'contract-incomplete'
    assert result['cutover_policy']['blocking_items'] == ['lifecycle_contract_incomplete', 'missing_wix', 'missing_signtool']
    assert result['cutover_policy']['next_action'] == 'repair_lifecycle_contract'


def test_execute_native_installer_lane_reports_unsigned_msi_cutover_blocker(tmp_path: Path) -> None:
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
            return {'checksum_matches': True, 'lifecycle_contract_ready': True}
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

    result = execute(workspace=tmp_path / 'workspace', name='lane')

    assert result['stage_status']['msi_built'] is True
    assert result['stage_status']['lifecycle_contract_ready'] is True
    assert result['stage_status']['signature_verified'] is False
    assert result['cutover_policy']['native_installer_lane_phase'] == 'unsigned-msi'
    assert result['cutover_policy']['blocking_items'] == ['signature_not_verified']
    assert result['cutover_policy']['next_action'] == 'sign_and_verify_msi'


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
            return {'checksum_matches': True, 'lifecycle_contract_ready': True}
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
    def fake_native_lane_receipt(*, workspace, name, receipt_file):
        payload = {
            'generated_at': '2026-04-16T00:00:00+00:00',
            'stage_status': {
                'toolchain_ready': False,
                'lifecycle_contract_ready': True,
            },
            'cutover_policy': {
                'native_installer_lane_phase': 'probe-only',
                'blocking_items': ['missing_wix', 'missing_signtool'],
            },
            'ready_for_release': False,
        }
        receipt_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return payload
    execute.__globals__['_run_native_installer_lane_receipt'] = fake_native_lane_receipt

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
    assert Path(result['native_installer_lane_receipt_file']).exists()
    assert Path(result['deliverables_manifest_file']).exists()
    assert result['deliverables_manifest']['native_installer_lane_summary']['phase'] == 'probe-only'
    assert result['deliverables_manifest']['checksums']['protolink-0.2.5-installer-package.zip']


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
