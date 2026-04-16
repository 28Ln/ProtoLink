from __future__ import annotations

import json
import importlib
import runpy
import subprocess
from pathlib import Path

import pytest
from protolink.core.native_installer_cutover_policy import load_native_installer_cutover_policy


def _load_script(script_name: str) -> dict[str, object]:
    script_file = Path(__file__).resolve().parents[1] / 'scripts' / script_name
    return runpy.run_path(str(script_file), run_name=f'{script_name}_test_module')


def _write_cutover_policy_file(path: Path) -> dict[str, object]:
    payload = {
        "policy_id": "native-installer-cutover-policy",
        "format_version": "protolink-native-installer-cutover-policy-v1",
        "current_canonical_release_lane": "bundled-runtime-installer-package",
        "manual_cutover_requirements": [
            "approved_code_signing_certificate",
            "approved_rfc3161_timestamp_service",
            "documented_release_approval",
            "bundled_runtime_rollback_artifact_retained",
        ],
        "signing": {
            "required": True,
            "method": "windows-authenticode",
            "approved_certificate_required": True,
        },
        "timestamp": {
            "required": True,
            "service_type": "rfc3161",
            "approved_service_required": True,
        },
        "approvals": {
            "release_owner_approval_required": True,
            "signing_operation_approval_required": True,
        },
        "rollback": {
            "bundled_runtime_artifact_required": True,
            "rollback_validation_required": True,
        },
        "clean_machine_validation": {
            "required": True,
            "required_commands": [
                "msiexec /i ProtoLink.msi /qn /l*v install.log",
                "protolink --headless-summary",
                "msiexec /x ProtoLink.msi /qn /l*v uninstall.log",
            ],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return load_native_installer_cutover_policy(path)


def test_load_native_installer_cutover_policy_reads_valid_file(tmp_path: Path) -> None:
    policy_file = tmp_path / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    policy = _write_cutover_policy_file(policy_file)

    assert policy['policy_id'] == 'native-installer-cutover-policy'
    assert policy['format_version'] == 'protolink-native-installer-cutover-policy-v1'
    assert policy['policy_checksum']
    assert 'documented_release_approval' in policy['manual_cutover_requirements']


def test_load_native_installer_cutover_policy_rejects_missing_section(tmp_path: Path) -> None:
    policy_file = tmp_path / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    payload = {
        "policy_id": "native-installer-cutover-policy",
        "format_version": "protolink-native-installer-cutover-policy-v1",
        "current_canonical_release_lane": "bundled-runtime-installer-package",
        "manual_cutover_requirements": [
            "approved_code_signing_certificate",
            "approved_rfc3161_timestamp_service",
            "documented_release_approval",
            "bundled_runtime_rollback_artifact_retained",
        ],
        "signing": {
            "required": True,
            "method": "windows-authenticode",
            "approved_certificate_required": True,
        },
        "timestamp": {
            "required": True,
            "service_type": "rfc3161",
            "approved_service_required": True,
        },
        "approvals": {
            "release_owner_approval_required": True,
            "signing_operation_approval_required": True,
        },
        "rollback": {
            "bundled_runtime_artifact_required": True,
            "rollback_validation_required": True,
        },
    }
    policy_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    with pytest.raises(ValueError, match='clean_machine_validation'):
        load_native_installer_cutover_policy(policy_file)


def test_load_native_installer_cutover_policy_rejects_invalid_field_type(tmp_path: Path) -> None:
    policy_file = tmp_path / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    payload = json.loads(Path(__file__).resolve().parents[1].joinpath('docs', 'NATIVE_INSTALLER_CUTOVER_POLICY.json').read_text(encoding='utf-8'))
    payload['timestamp']['approved_service_required'] = 'yes'
    policy_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    with pytest.raises(ValueError, match='approved_service_required'):
        load_native_installer_cutover_policy(policy_file)


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
    assert result['policy_ready'] is False
    assert result['policy_status']['ready'] is False
    assert result['policy_status']['next_action'] == 'complete_msi_signing'
    assert result['policy_status']['sections']['approvals']['ready'] is False
    assert result['policy_status']['sections']['clean_machine_validation']['ready'] is False
    assert result['cutover_policy']['current_canonical_release_lane'] == 'bundled-runtime-installer-package'
    assert result['cutover_policy']['native_installer_lane_phase'] == 'probe-only'
    assert result['cutover_policy']['probe_ready'] is True
    assert result['cutover_policy']['cutover_ready'] is False
    assert result['cutover_policy']['policy_ready'] is False
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
        'policy_status': {
            'ready': False,
            'blocking_items': ['approvals.release_owner_approval_missing'],
            'next_action': 'record_release_approvals',
            'sections': {
                'approvals': {
                    'required': True,
                    'ready': False,
                    'blocking_items': ['release_owner_approval_missing'],
                },
            },
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
    assert result['policy_status']['ready'] is False
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
    assert result['policy_status']['ready'] is False
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
    policy_file = tmp_path / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    policy = _write_cutover_policy_file(policy_file)
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
    execute.__globals__['load_native_installer_cutover_policy'] = lambda: policy
    execute.__globals__['default_native_installer_cutover_policy_file'] = lambda: policy_file
    def fake_native_lane_receipt(*, workspace, name, receipt_file):
        payload = {
            'generated_at': '2026-04-16T00:00:00+00:00',
            'stage_status': {
                'toolchain_ready': False,
                'lifecycle_contract_ready': True,
            },
            'policy_status': {
                'ready': False,
                'blocking_items': ['approvals.release_owner_approval_missing'],
                'next_action': 'record_release_approvals',
                'sections': {
                    'approvals': {
                        'required': True,
                        'ready': False,
                        'blocking_items': ['release_owner_approval_missing'],
                    },
                },
            },
            'cutover_policy': {
                'policy_file': policy_file.name,
                'policy_id': policy['policy_id'],
                'policy_format_version': policy['format_version'],
                'policy_checksum': policy['policy_checksum'],
                'current_canonical_release_lane': policy['current_canonical_release_lane'],
                'native_installer_lane_phase': 'probe-only',
                'blocking_items': ['missing_wix', 'missing_signtool'],
                'policy_ready': False,
                'policy_blocking_items': ['approvals.release_owner_approval_missing'],
                'manual_cutover_requirements': list(policy['manual_cutover_requirements']),
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
    assert Path(result['native_installer_cutover_policy_file']).exists()
    assert Path(result['deliverables_manifest_file']).exists()
    assert result['deliverables_manifest']['native_installer_lane_summary']['phase'] == 'probe-only'
    assert result['deliverables_manifest']['native_installer_lane_summary']['policy_ready'] is False
    assert result['deliverables_manifest']['native_installer_policy_status']['ready'] is False
    assert result['deliverables_manifest']['checksums']['protolink-0.2.5-installer-package.zip']
    assert result['deliverables_manifest']['checksums']['native-installer-lane-receipt.json']
    assert result['deliverables_manifest']['checksums'][policy_file.name]


def test_execute_verify_release_deliverables_checks_manifest_and_receipt(tmp_path: Path) -> None:
    ns = _load_script('verify_release_deliverables.py')
    target_dir = tmp_path / 'deliverables'
    target_dir.mkdir()
    policy_file = target_dir / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    policy = _write_cutover_policy_file(policy_file)

    file_payloads = {
        'protolink-0.2.5-release-bundle.zip': b'release',
        'protolink-0.2.5-portable-package.zip': b'portable',
        'protolink-0.2.5-distribution-package.zip': b'distribution',
        'protolink-0.2.5-installer-package.zip': b'installer',
    }
    for name, payload in file_payloads.items():
        (target_dir / name).write_bytes(payload)

    receipt = {
        'generated_at': '2026-04-16T00:00:00+00:00',
        'stage_status': {
            'toolchain_ready': False,
            'scaffold_built': True,
            'scaffold_verified': True,
            'lifecycle_contract_ready': True,
            'msi_built': False,
            'signature_verified': False,
        },
        'policy_status': {
            'ready': False,
            'blocking_items': ['approvals.release_owner_approval_missing'],
            'next_action': 'record_release_approvals',
            'sections': {
                'approvals': {
                    'required': True,
                    'ready': False,
                    'blocking_items': ['release_owner_approval_missing'],
                },
            },
        },
        'cutover_policy': {
            'policy_file': policy_file.name,
            'policy_id': policy['policy_id'],
            'policy_format_version': policy['format_version'],
            'policy_checksum': policy['policy_checksum'],
            'current_canonical_release_lane': 'bundled-runtime-installer-package',
            'native_installer_lane_phase': 'probe-only',
            'probe_ready': True,
            'cutover_ready': False,
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'next_action': 'install_wix_and_signtool',
            'manual_cutover_requirements': list(policy['manual_cutover_requirements']),
            'policy_ready': False,
            'policy_blocking_items': ['approvals.release_owner_approval_missing'],
        },
        'ready_for_release': False,
    }
    receipt_file = target_dir / 'native-installer-lane-receipt.json'
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')

    sha256 = ns['_sha256_file']
    manifest = {
        'format_version': 'protolink-deliverables-v1',
        'version': '0.2.5',
        'build_name': 'release-0.2.5',
        'workspace': str(tmp_path / 'workspace'),
        'copied_artifacts': {
            'release_archive': 'protolink-0.2.5-release-bundle.zip',
            'portable_archive': 'protolink-0.2.5-portable-package.zip',
            'distribution_archive': 'protolink-0.2.5-distribution-package.zip',
            'installer_archive': 'protolink-0.2.5-installer-package.zip',
        },
        'checksums': {
            name: sha256(target_dir / name)
            for name in (*file_payloads.keys(), 'native-installer-lane-receipt.json', policy_file.name)
        },
        'verification': {
            'portable': {'checksum_matches': True},
            'distribution': {'checksum_matches': True},
            'installer': {'checksum_matches': True},
        },
        'install_smoke': None,
        'native_installer_lane_receipt_file': 'native-installer-lane-receipt.json',
        'native_installer_cutover_policy_file': policy_file.name,
        'native_installer_cutover_policy': {
            'policy_id': policy['policy_id'],
            'policy_format_version': policy['format_version'],
            'policy_checksum': policy['policy_checksum'],
        },
        'native_installer_lane_summary': {
            'phase': 'probe-only',
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'lifecycle_contract_ready': True,
            'toolchain_ready': False,
            'ready_for_release': False,
            'policy_ready': False,
        },
        'native_installer_policy_status': receipt['policy_status'],
        'included_entries': [
            'deliverables-manifest.json',
            'native-installer-lane-receipt.json',
            policy_file.name,
            'protolink-0.2.5-distribution-package.zip',
            'protolink-0.2.5-installer-package.zip',
            'protolink-0.2.5-portable-package.zip',
            'protolink-0.2.5-release-bundle.zip',
        ],
        'target_dir': str(target_dir),
    }
    (target_dir / 'deliverables-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(command)
        if '--verify-portable-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'checksum_matches': True}
        raise AssertionError(command)

    ns['execute_verify_release_deliverables'].__globals__['_run_json'] = fake_run_json
    result = ns['execute_verify_release_deliverables'](target_dir=target_dir)

    assert result['ready'] is True
    assert result['blocking_items'] == []
    assert result['native_installer_lane_phase'] == 'probe-only'
    assert result['install_smoke_present'] is False
    assert Path(result['receipt_file']).exists()
    assert result['checks']['native_installer_lane']['policy_ready'] is False


def test_execute_verify_release_deliverables_rejects_receipt_summary_mismatch(tmp_path: Path) -> None:
    ns = _load_script('verify_release_deliverables.py')
    target_dir = tmp_path / 'deliverables'
    target_dir.mkdir()
    policy_file = target_dir / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    policy = _write_cutover_policy_file(policy_file)

    for name, payload in {
        'protolink-0.2.5-release-bundle.zip': b'release',
        'protolink-0.2.5-portable-package.zip': b'portable',
        'protolink-0.2.5-distribution-package.zip': b'distribution',
        'protolink-0.2.5-installer-package.zip': b'installer',
    }.items():
        (target_dir / name).write_bytes(payload)

    receipt = {
        'generated_at': '2026-04-16T00:00:00+00:00',
        'stage_status': {
            'toolchain_ready': False,
            'scaffold_built': True,
            'scaffold_verified': True,
            'lifecycle_contract_ready': True,
            'msi_built': False,
            'signature_verified': False,
        },
        'policy_status': {
            'ready': False,
            'blocking_items': ['approvals.release_owner_approval_missing'],
            'next_action': 'record_release_approvals',
            'sections': {
                'approvals': {
                    'required': True,
                    'ready': False,
                    'blocking_items': ['release_owner_approval_missing'],
                },
            },
        },
        'cutover_policy': {
            'policy_file': policy_file.name,
            'policy_id': policy['policy_id'],
            'policy_format_version': policy['format_version'],
            'policy_checksum': policy['policy_checksum'],
            'current_canonical_release_lane': 'bundled-runtime-installer-package',
            'native_installer_lane_phase': 'probe-only',
            'probe_ready': True,
            'cutover_ready': False,
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'next_action': 'install_wix_and_signtool',
            'manual_cutover_requirements': list(policy['manual_cutover_requirements']),
            'policy_ready': False,
            'policy_blocking_items': ['approvals.release_owner_approval_missing'],
        },
        'ready_for_release': False,
    }
    receipt_file = target_dir / 'native-installer-lane-receipt.json'
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    sha256 = ns['_sha256_file']
    (target_dir / 'deliverables-manifest.json').write_text(
        json.dumps(
            {
                'format_version': 'protolink-deliverables-v1',
                'version': '0.2.5',
                'build_name': 'release-0.2.5',
                'workspace': str(tmp_path / 'workspace'),
                'copied_artifacts': {
                    'release_archive': 'protolink-0.2.5-release-bundle.zip',
                    'portable_archive': 'protolink-0.2.5-portable-package.zip',
                    'distribution_archive': 'protolink-0.2.5-distribution-package.zip',
                    'installer_archive': 'protolink-0.2.5-installer-package.zip',
                },
                'checksums': {
                    'protolink-0.2.5-release-bundle.zip': sha256(target_dir / 'protolink-0.2.5-release-bundle.zip'),
                    'protolink-0.2.5-portable-package.zip': sha256(target_dir / 'protolink-0.2.5-portable-package.zip'),
                    'protolink-0.2.5-distribution-package.zip': sha256(target_dir / 'protolink-0.2.5-distribution-package.zip'),
                    'protolink-0.2.5-installer-package.zip': sha256(target_dir / 'protolink-0.2.5-installer-package.zip'),
                    'native-installer-lane-receipt.json': sha256(receipt_file),
                    policy_file.name: sha256(policy_file),
                },
                'verification': {
                    'portable': {'checksum_matches': True},
                    'distribution': {'checksum_matches': True},
                    'installer': {'checksum_matches': True},
                },
                'install_smoke': None,
                'native_installer_lane_receipt_file': 'native-installer-lane-receipt.json',
                'native_installer_cutover_policy_file': policy_file.name,
                'native_installer_cutover_policy': {
                    'policy_id': policy['policy_id'],
                    'policy_format_version': policy['format_version'],
                    'policy_checksum': policy['policy_checksum'],
                },
                'native_installer_lane_summary': {
                    'phase': 'toolchain-ready',
                    'blocking_items': ['missing_wix', 'missing_signtool'],
                    'lifecycle_contract_ready': True,
                    'toolchain_ready': False,
                    'ready_for_release': False,
                    'policy_ready': False,
                },
                'native_installer_policy_status': receipt['policy_status'],
                'included_entries': [
                    'deliverables-manifest.json',
                    'native-installer-lane-receipt.json',
                    policy_file.name,
                    'protolink-0.2.5-distribution-package.zip',
                    'protolink-0.2.5-installer-package.zip',
                    'protolink-0.2.5-portable-package.zip',
                    'protolink-0.2.5-release-bundle.zip',
                ],
                'target_dir': str(target_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(command)
        if '--verify-portable-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'checksum_matches': True}
        raise AssertionError(command)

    ns['execute_verify_release_deliverables'].__globals__['_run_json'] = fake_run_json

    with pytest.raises(ns['DeliveryVerificationError'], match='phase mismatch'):
        ns['execute_verify_release_deliverables'](target_dir=target_dir)


def test_execute_verify_release_deliverables_can_require_native_ready(tmp_path: Path) -> None:
    ns = _load_script('verify_release_deliverables.py')
    target_dir = tmp_path / 'deliverables'
    target_dir.mkdir()
    policy_file = target_dir / 'NATIVE_INSTALLER_CUTOVER_POLICY.json'
    policy = _write_cutover_policy_file(policy_file)

    for name, payload in {
        'protolink-0.2.5-release-bundle.zip': b'release',
        'protolink-0.2.5-portable-package.zip': b'portable',
        'protolink-0.2.5-distribution-package.zip': b'distribution',
        'protolink-0.2.5-installer-package.zip': b'installer',
    }.items():
        (target_dir / name).write_bytes(payload)

    receipt = {
        'generated_at': '2026-04-16T00:00:00+00:00',
        'stage_status': {
            'toolchain_ready': False,
            'scaffold_built': True,
            'scaffold_verified': True,
            'lifecycle_contract_ready': True,
            'msi_built': False,
            'signature_verified': False,
        },
        'policy_status': {
            'ready': False,
            'blocking_items': ['approvals.release_owner_approval_missing'],
            'next_action': 'record_release_approvals',
            'sections': {
                'approvals': {
                    'required': True,
                    'ready': False,
                    'blocking_items': ['release_owner_approval_missing'],
                },
            },
        },
        'cutover_policy': {
            'policy_file': policy_file.name,
            'policy_id': policy['policy_id'],
            'policy_format_version': policy['format_version'],
            'policy_checksum': policy['policy_checksum'],
            'current_canonical_release_lane': 'bundled-runtime-installer-package',
            'native_installer_lane_phase': 'probe-only',
            'probe_ready': True,
            'cutover_ready': False,
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'next_action': 'install_wix_and_signtool',
            'manual_cutover_requirements': list(policy['manual_cutover_requirements']),
            'policy_ready': False,
            'policy_blocking_items': ['approvals.release_owner_approval_missing'],
        },
        'ready_for_release': False,
    }
    receipt_file = target_dir / 'native-installer-lane-receipt.json'
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    sha256 = ns['_sha256_file']
    (target_dir / 'deliverables-manifest.json').write_text(
        json.dumps(
            {
                'format_version': 'protolink-deliverables-v1',
                'version': '0.2.5',
                'build_name': 'release-0.2.5',
                'workspace': str(tmp_path / 'workspace'),
                'copied_artifacts': {
                    'release_archive': 'protolink-0.2.5-release-bundle.zip',
                    'portable_archive': 'protolink-0.2.5-portable-package.zip',
                    'distribution_archive': 'protolink-0.2.5-distribution-package.zip',
                    'installer_archive': 'protolink-0.2.5-installer-package.zip',
                },
                'checksums': {
                    'protolink-0.2.5-release-bundle.zip': sha256(target_dir / 'protolink-0.2.5-release-bundle.zip'),
                    'protolink-0.2.5-portable-package.zip': sha256(target_dir / 'protolink-0.2.5-portable-package.zip'),
                    'protolink-0.2.5-distribution-package.zip': sha256(target_dir / 'protolink-0.2.5-distribution-package.zip'),
                    'protolink-0.2.5-installer-package.zip': sha256(target_dir / 'protolink-0.2.5-installer-package.zip'),
                    'native-installer-lane-receipt.json': sha256(receipt_file),
                    policy_file.name: sha256(policy_file),
                },
                'verification': {
                    'portable': {'checksum_matches': True},
                    'distribution': {'checksum_matches': True},
                    'installer': {'checksum_matches': True},
                },
                'install_smoke': None,
                'native_installer_lane_receipt_file': 'native-installer-lane-receipt.json',
                'native_installer_cutover_policy_file': policy_file.name,
                'native_installer_cutover_policy': {
                    'policy_id': policy['policy_id'],
                    'policy_format_version': policy['format_version'],
                    'policy_checksum': policy['policy_checksum'],
                },
                'native_installer_lane_summary': {
                    'phase': 'probe-only',
                    'blocking_items': ['missing_wix', 'missing_signtool'],
                    'lifecycle_contract_ready': True,
                    'toolchain_ready': False,
                    'ready_for_release': False,
                    'policy_ready': False,
                },
                'native_installer_policy_status': receipt['policy_status'],
                'included_entries': [
                    'deliverables-manifest.json',
                    'native-installer-lane-receipt.json',
                    policy_file.name,
                    'protolink-0.2.5-distribution-package.zip',
                    'protolink-0.2.5-installer-package.zip',
                    'protolink-0.2.5-portable-package.zip',
                    'protolink-0.2.5-release-bundle.zip',
                ],
                'target_dir': str(target_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(command)
        if '--verify-portable-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'checksum_matches': True}
        raise AssertionError(command)

    ns['execute_verify_release_deliverables'].__globals__['_run_json'] = fake_run_json

    with pytest.raises(ns['DeliveryVerificationError'], match='policy is not ready'):
        ns['execute_verify_release_deliverables'](target_dir=target_dir, require_native_ready=True)


def test_execute_verify_release_deliverables_rejects_missing_archived_policy(tmp_path: Path) -> None:
    ns = _load_script('verify_release_deliverables.py')
    target_dir = tmp_path / 'deliverables'
    target_dir.mkdir()

    for name, payload in {
        'protolink-0.2.5-release-bundle.zip': b'release',
        'protolink-0.2.5-portable-package.zip': b'portable',
        'protolink-0.2.5-distribution-package.zip': b'distribution',
        'protolink-0.2.5-installer-package.zip': b'installer',
    }.items():
        (target_dir / name).write_bytes(payload)

    receipt = {
        'generated_at': '2026-04-16T00:00:00+00:00',
        'stage_status': {
            'toolchain_ready': False,
            'scaffold_built': True,
            'scaffold_verified': True,
            'lifecycle_contract_ready': True,
            'msi_built': False,
            'signature_verified': False,
        },
        'policy_status': {
            'ready': False,
            'blocking_items': ['approvals.release_owner_approval_missing'],
            'next_action': 'record_release_approvals',
            'sections': {
                'approvals': {
                    'required': True,
                    'ready': False,
                    'blocking_items': ['release_owner_approval_missing'],
                },
            },
        },
        'cutover_policy': {
            'policy_file': 'NATIVE_INSTALLER_CUTOVER_POLICY.json',
            'policy_id': 'native-installer-cutover-policy',
            'policy_format_version': 'protolink-native-installer-cutover-policy-v1',
            'policy_checksum': 'deadbeef',
            'current_canonical_release_lane': 'bundled-runtime-installer-package',
            'native_installer_lane_phase': 'probe-only',
            'probe_ready': True,
            'cutover_ready': False,
            'blocking_items': ['missing_wix', 'missing_signtool'],
            'next_action': 'install_wix_and_signtool',
            'policy_ready': False,
            'policy_blocking_items': ['approvals.release_owner_approval_missing'],
            'manual_cutover_requirements': [
                'approved_code_signing_certificate',
                'approved_rfc3161_timestamp_service',
                'documented_release_approval',
                'bundled_runtime_rollback_artifact_retained',
            ],
        },
        'ready_for_release': False,
    }
    receipt_file = target_dir / 'native-installer-lane-receipt.json'
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    sha256 = ns['_sha256_file']
    (target_dir / 'deliverables-manifest.json').write_text(
        json.dumps(
            {
                'format_version': 'protolink-deliverables-v1',
                'version': '0.2.5',
                'build_name': 'release-0.2.5',
                'workspace': str(tmp_path / 'workspace'),
                'copied_artifacts': {
                    'release_archive': 'protolink-0.2.5-release-bundle.zip',
                    'portable_archive': 'protolink-0.2.5-portable-package.zip',
                    'distribution_archive': 'protolink-0.2.5-distribution-package.zip',
                    'installer_archive': 'protolink-0.2.5-installer-package.zip',
                },
                'checksums': {
                    'protolink-0.2.5-release-bundle.zip': sha256(target_dir / 'protolink-0.2.5-release-bundle.zip'),
                    'protolink-0.2.5-portable-package.zip': sha256(target_dir / 'protolink-0.2.5-portable-package.zip'),
                    'protolink-0.2.5-distribution-package.zip': sha256(target_dir / 'protolink-0.2.5-distribution-package.zip'),
                    'protolink-0.2.5-installer-package.zip': sha256(target_dir / 'protolink-0.2.5-installer-package.zip'),
                    'native-installer-lane-receipt.json': sha256(receipt_file),
                    'NATIVE_INSTALLER_CUTOVER_POLICY.json': 'deadbeef',
                },
                'verification': {
                    'portable': {'checksum_matches': True},
                    'distribution': {'checksum_matches': True},
                    'installer': {'checksum_matches': True},
                },
                'install_smoke': None,
                'native_installer_lane_receipt_file': 'native-installer-lane-receipt.json',
                'native_installer_cutover_policy_file': 'NATIVE_INSTALLER_CUTOVER_POLICY.json',
                'native_installer_cutover_policy': {
                    'policy_id': 'native-installer-cutover-policy',
                    'policy_format_version': 'protolink-native-installer-cutover-policy-v1',
                    'policy_checksum': 'deadbeef',
                },
                'native_installer_lane_summary': {
                    'phase': 'probe-only',
                    'blocking_items': ['missing_wix', 'missing_signtool'],
                    'lifecycle_contract_ready': True,
                    'toolchain_ready': False,
                    'ready_for_release': False,
                    'policy_ready': False,
                },
                'native_installer_policy_status': receipt['policy_status'],
                'included_entries': [
                    'deliverables-manifest.json',
                    'native-installer-lane-receipt.json',
                    'NATIVE_INSTALLER_CUTOVER_POLICY.json',
                    'protolink-0.2.5-distribution-package.zip',
                    'protolink-0.2.5-installer-package.zip',
                    'protolink-0.2.5-portable-package.zip',
                    'protolink-0.2.5-release-bundle.zip',
                ],
                'target_dir': str(target_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    def fake_run_json(command, *, cwd=None):
        command_text = ' '.join(command)
        if '--verify-portable-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-distribution-package' in command_text:
            return {'checksum_matches': True}
        if '--verify-installer-package' in command_text:
            return {'checksum_matches': True}
        raise AssertionError(command)

    ns['execute_verify_release_deliverables'].__globals__['_run_json'] = fake_run_json

    with pytest.raises(ns['DeliveryVerificationError'], match='cutover policy file was not found'):
        ns['execute_verify_release_deliverables'](target_dir=target_dir)


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
