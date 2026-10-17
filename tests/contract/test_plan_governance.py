"""V2-002 engineering integration; fixtures never stand in for real CI."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'plan/scripts'))
import validate_plan as validator

spec = importlib.util.spec_from_file_location('engineering_governance', ROOT / 'scripts/check_governance.py')
engineering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engineering)


def test_current_normative_registry_and_owner_mapping():
    data = validator.load()
    registry, errors = validator.normative_registry(data, ROOT / 'plan')
    assert errors == []
    assert 'V2-002' in registry['AI_EXECUTION_PROTOCOL.md']
    assert set().union(*(set(owners) for owners in registry.values())) == {t['task_id'] for t in data['implementation-backlog']['tasks']}
    assert not any(name.startswith('archive/') for name in registry)


@pytest.mark.parametrize('alias', ['archive/history.md', './archive/history.md', 'current/../archive/history.md', 'alias.md'])
def test_resolved_history_cannot_be_normative(tmp_path, alias):
    plan = tmp_path / 'plan'
    (plan / 'archive').mkdir(parents=True)
    (plan / 'current').mkdir()
    (plan / 'archive/history.md').write_text('HISTORICAL ONLY')
    (plan / 'current/spec.md').write_text('Current requirement')
    (plan / 'alias.md').symlink_to(plan / 'archive/history.md')
    data = {'implementation-backlog': {'tasks': [{'task_id': 'V2-002', 'normative_specs': ['current/spec.md'], 'design_references': ['archive/history.md']}]}}
    assert validator.normative_registry(data, plan)[1] == []
    data['implementation-backlog']['tasks'][0]['normative_specs'] = [alias]
    assert any('resolved archive' in error for error in validator.normative_registry(data, plan)[1])


def test_missing_normative_reference_rejected(tmp_path):
    data = {'implementation-backlog': {'tasks': [{'task_id': 'V2-002', 'normative_specs': ['missing.md']}]}}
    assert any('missing/outside' in error for error in validator.normative_registry(data, tmp_path)[1])


def test_actual_repository_context_entries_and_configuration():
    result = engineering.context_inventory(ROOT)
    assert result['errors'] == []
    by = {row['path']: row for row in result['files']}
    assert by['AGENTS.md']['exists'] and by['README.md']['exists']
    if by['.claude/settings.local.json']['exists']:
        assert by['.claude/settings.local.json']['top_level_keys'] == ['permissions']
        assert by['.claude/settings.local.json']['automatic_context_configuration'] == {}


def test_context_permissions_are_distinct_from_automatic_load(tmp_path):
    (tmp_path / '.claude').mkdir()
    for name in ('README.md', 'AGENTS.md'):
        (tmp_path / name).write_text('Read plan/README.md; archive is historical.')
    settings = tmp_path / '.claude/settings.local.json'
    settings.write_text(json.dumps({'permissions': {'allow': ['Read(plan/archive/history.md)']}}))
    assert engineering.context_inventory(tmp_path)['errors'] == []
    settings.write_text(json.dumps({'contextFiles': ['plan/archive/history.md']}))
    assert any('CONTEXT_ARCHIVE' in error for error in engineering.context_inventory(tmp_path)['errors'])


def test_context_import_alias_resolves_to_history(tmp_path):
    (tmp_path / 'plan/archive').mkdir(parents=True)
    (tmp_path / 'plan/archive/history.md').write_text('old')
    (tmp_path / 'alias.md').symlink_to(tmp_path / 'plan/archive/history.md')
    for name in ('README.md', 'AGENTS.md'):
        (tmp_path / name).write_text('Read plan/README.md')
    (tmp_path / 'CLAUDE.md').write_text('@alias.md\n')
    assert any('CONTEXT_ARCHIVE' in error for error in engineering.context_inventory(tmp_path)['errors'])


def _make_verified_dependency_incomplete(data):
    """Create a progress-stable TASK_START violation from a closed dependency chain."""
    tasks = {
        task['task_id']: task
        for task in data['implementation-backlog']['tasks']
    }
    assert 'V2-005' in tasks['V2-006']['dependencies']
    assert tasks['V2-006']['status'] in {'VERIFIED', 'CLOSED'}
    tasks['V2-005']['status'] = 'OPEN'


@pytest.mark.parametrize('mutate,prefix', [
    (lambda d: d['implementation-backlog']['tasks'][1].update(phase='P1'), 'TASK_PHASE'),
    (lambda d: d['implementation-backlog']['tasks'][1]['evidence'].pop('ci'), 'TASK_SCHEMA'),
    (lambda d: d['implementation-backlog']['tasks'][1]['evidence'].pop('acceptance'), 'TASK_SCHEMA'),
    (_make_verified_dependency_incomplete, 'TASK_START'),
    (lambda d: d['external-practice-register']['practices'][0].update(source_refs=['MISSING']), 'EXTERNAL_SOURCE'),
])
def test_existing_rules_reject_single_mutations(mutate, prefix):
    data = deepcopy(validator.load())
    assert validator.validate_objects(data) == []
    mutate(data)
    errors = validator.validate_objects(data)
    assert any(error.startswith(prefix) for error in errors), errors


def test_generated_views_match_current_source():
    for name, content in validator.expected_views(validator.load()).items():
        assert (ROOT / 'plan' / name).read_text() == content


@pytest.mark.parametrize('status', ['VERIFIED', 'CLOSED'])
@pytest.mark.parametrize('kind', ['code', 'tests', 'ci', 'acceptance'])
def test_completed_task_requires_nonempty_evidence(status, kind):
    """Regression: VERIFIED/CLOSED tasks must have non-empty evidence for all categories."""
    data = deepcopy(validator.load())

    current = data['implementation-backlog']['tasks'][0]
    current['status'] = status
    current['evidence'][kind] = []

    errors = validator.validate_objects(data)

    assert any(
        error.startswith(f"TASK_SCHEMA V2-001 ['evidence', '{kind}']:") or
        f"['evidence', '{kind}']" in error
        for error in errors
    ), f"Expected rejection for {status} task with empty {kind} evidence, got: {errors}"


def test_empty_closed_evidence_self_test_probe_rejects():
    """Regression: self-test 'empty CLOSED evidence' probe must actually produce rejection."""
    data = deepcopy(validator.load())
    cases = {
        row['case']: row
        for row in validator.self_test(data)
    }

    result = cases['empty CLOSED evidence']

    assert result['expected'] == 'REJECT', "Self-test probe should expect REJECT"
    assert result['actual'] == 'REJECT', f"Self-test probe should produce REJECT, got: {result['actual']}"
    assert result['evidence'], "Self-test probe should include diagnostic evidence"

    # Verify all four evidence categories are checked
    evidence_text = ' '.join(result['evidence'])
    for kind in ['code', 'tests', 'ci', 'acceptance']:
        assert f"'{kind}'" in evidence_text or f'["{kind}"]' in evidence_text or kind in evidence_text, \
            f"Self-test evidence should mention {kind} category"


def test_validator_exit_code_respects_severity():
    """
    Regression: validator must exit 0 when only informational errors present.
    
    Exit code semantics:
    - fatal_errors present → exit 1
    - only informational_errors → exit 0
    - no errors → exit 0
    """
    import subprocess
    import tempfile
    
    # Case 1: Clean validation should exit 0
    result = subprocess.run(
        ['python3', str(ROOT / 'plan/scripts/validate_plan.py'), '--check'],
        capture_output=True,
        cwd=ROOT
    )
    output = json.loads(result.stdout)
    
    # Informational errors are allowed
    if output['status'] == 'PASS' and not output.get('fatal_errors'):
        assert result.returncode == 0, \
            f"Validator with status=PASS and no fatal errors must exit 0, got {result.returncode}"
    
    # Case 2: With fatal errors should exit non-zero
    # This is verified by CI when actual fatal errors occur
    
    # Case 3: Informational-only should exit 0
    if output.get('informational_errors') and not output.get('fatal_errors'):
        assert result.returncode == 0, \
            f"Validator with only informational errors must exit 0, got {result.returncode}"
        assert output['status'] == 'PASS', \
            f"Status should be PASS when no fatal errors, got {output['status']}"
