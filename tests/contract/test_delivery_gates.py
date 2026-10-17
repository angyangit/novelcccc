"""Delivery gate contract tests for V2-004.

These tests verify CI gate requirements and anti-weakening properties.
They run locally and do not depend on the CI platform being online.

Current CI platform: GitHub Actions (.github/workflows/ci.yml)
"""
import json
from pathlib import Path
import re
import yaml
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_ci_gates_yaml_structure():
    """Verify ci-gates.yaml has required structure."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    assert gates_path.exists(), "ci-gates.yaml must exist"

    with gates_path.open() as f:
        data = yaml.safe_load(f)

    assert 'version' in data
    assert 'status' in data
    assert 'gates' in data
    assert isinstance(data['gates'], list)


def test_p0_gates_exist_with_correct_activation():
    """P0 gates must exist with activation_phase: P0."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    with gates_path.open() as f:
        data = yaml.safe_load(f)

    required_p0_gates = {
        'STATIC', 'UNIT', 'SCHEMA_CONTRACT',
        'ARCH_FITNESS', 'SECRET_DEPENDENCY', 'POSTGRES_ENV'
    }

    found_gates = {gate['id']: gate for gate in data['gates']}

    for gate_id in required_p0_gates:
        assert gate_id in found_gates, f"P0 gate {gate_id} must exist"
        gate = found_gates[gate_id]
        assert gate['activation_phase'] == 'P0', \
            f"{gate_id} must have activation_phase: P0"


def test_p0_gates_cannot_allow_failure():
    """All P0 gates must have allow_failure: false."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    with gates_path.open() as f:
        data = yaml.safe_load(f)

    p0_gates = [g for g in data['gates'] if g['activation_phase'] == 'P0']

    for gate in p0_gates:
        assert gate['allow_failure'] is False, \
            f"P0 gate {gate['id']} must have allow_failure: false, got {gate['allow_failure']}"


def test_future_gates_not_falsely_activated():
    """Future gates (P2+) must remain NOT_IMPLEMENTED."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    with gates_path.open() as f:
        data = yaml.safe_load(f)

    future_gates = {
        'CANON_CAS_IDEMPOTENCY': 'P2',
        'DETERMINISTIC_E2E': 'P7',
        'GENRE_SMOKE': 'P8',
        'LIVE_PROVIDER': 'P5'
    }

    found_gates = {gate['id']: gate for gate in data['gates']}

    for gate_id, expected_phase in future_gates.items():
        if gate_id in found_gates:
            gate = found_gates[gate_id]
            assert gate['activation_phase'] == expected_phase, \
                f"{gate_id} must remain in phase {expected_phase}"
            assert gate['status'] == 'NOT_IMPLEMENTED', \
                f"Future gate {gate_id} must remain NOT_IMPLEMENTED"


def test_github_ci_exists():
    """GitHub Actions CI configuration must exist."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    assert ci_path.exists(), ".github/workflows/ci.yml must exist"


def test_github_ci_has_p0_jobs():
    """GitHub Actions CI must define jobs for P0 gates."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Check for job definitions
    required_jobs = [
        'static', 'unit', 'schema_contract',
        'arch_fitness', 'secret_dependency', 'postgres_env'
    ]

    content_lower = content.lower()
    for job in required_jobs:
        assert job in content_lower, \
            f"CI must include job for {job}"


def test_github_ci_uses_locked_dependencies():
    """CI must use locked dependencies (uv sync --frozen)."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    assert 'uv sync --frozen' in content, \
        "CI must use uv sync --frozen for locked dependencies"


def test_github_ci_uses_postgres_service():
    """CI must include PostgreSQL service for POSTGRES_ENV gate."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    assert 'postgres:' in content, \
        "CI must include PostgreSQL service"


def test_delivery_gates_test_suite_registered():
    """AT-V2-004 test suite must be registered in test-catalog."""
    catalog_path = ROOT / 'plan/machine/test-catalog.yaml'
    with catalog_path.open() as f:
        data = yaml.safe_load(f)

    suites = {suite['id']: suite for suite in data['suites']}

    assert 'AT-V2-004' in suites, "AT-V2-004 must be registered in test-catalog"
    suite = suites['AT-V2-004']
    assert suite['task_id'] == 'V2-004'
    assert suite['phase'] == 'P0'


def test_no_test_deletions_in_catalog():
    """Test catalog must not have tests deleted (reduced scenario count)."""
    catalog_path = ROOT / 'plan/machine/test-catalog.yaml'
    with catalog_path.open() as f:
        data = yaml.safe_load(f)

    # V2-001 should have scenarios (from baseline)
    v2_001_suites = [s for s in data['suites'] if s['id'] == 'AT-V2-001']
    assert len(v2_001_suites) > 0
    assert 'scenarios' in v2_001_suites[0]
    assert len(v2_001_suites[0]['scenarios']) >= 5, \
        "V2-001 scenarios must not be reduced"


def test_execution_packet_exists_for_v2_004():
    """V2-004 must have execution packet."""
    packet_path = ROOT / 'plan/validation/execution/V2-004/execution-packet.yaml'
    assert packet_path.exists(), "V2-004 execution packet must exist"


def test_execution_packet_action_is_implement():
    """V2-004 execution packet must have action: IMPLEMENT."""
    packet_path = ROOT / 'plan/validation/execution/V2-004/execution-packet.yaml'
    with packet_path.open() as f:
        data = yaml.safe_load(f)

    assert data['action'] == 'IMPLEMENT', \
        "V2-004 packet must have action: IMPLEMENT"


def test_no_weakening_in_governance_tests():
    """Governance tests must not be skipped or reduced."""
    gov_test_path = ROOT / 'tests/contract/test_plan_governance.py'
    assert gov_test_path.exists(), "Governance tests must exist"

    with gov_test_path.open() as f:
        content = f.read()

    # Check no mass pytest.skip added
    assert '@pytest.skip' not in content or content.count('@pytest.skip') < 3, \
        "Governance tests must not be mass-skipped"


def test_ci_would_detect_secret_fixture():
    """SECRET_DEPENDENCY gate includes secret scanning logic."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Verify secret_dependency job has actual scanning logic
    assert 'secret' in content.lower() or 'gitleaks' in content.lower(), \
        "CI must include secret scanning reference"


def test_ci_would_detect_dependency_issues():
    """SECRET_DEPENDENCY gate includes dependency checking logic."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Verify dependency checking
    assert 'uv pip check' in content or 'pip-audit' in content, \
        "CI must include dependency validation"


def test_ci_gates_not_reduced_from_baseline():
    """Number of P0 gates must not decrease."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    with gates_path.open() as f:
        data = yaml.safe_load(f)

    p0_gates = [g for g in data['gates'] if g['activation_phase'] == 'P0']

    assert len(p0_gates) >= 6, \
        f"Must have at least 6 P0 gates, found {len(p0_gates)}"


def test_locked_dependencies_file_exists():
    """uv.lock must exist and not be bypassed."""
    lock_path = ROOT / 'uv.lock'
    assert lock_path.exists(), "uv.lock must exist for locked dependencies"


def test_gitignore_includes_dist():
    """dist/ must be in .gitignore (CI artifacts)."""
    gitignore_path = ROOT / '.gitignore'
    assert gitignore_path.exists()

    with gitignore_path.open() as f:
        content = f.read()

    assert 'dist/' in content, "dist/ must be in .gitignore"


def test_github_ci_yaml_is_valid():
    """GitHub Actions CI YAML must be syntactically valid."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    assert ci_path.exists()

    with ci_path.open() as f:
        try:
            yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"GitHub Actions CI YAML is invalid: {e}")


def test_arch_fitness_references_existing_tests():
    """ARCH_FITNESS job must reference only existing test files."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Extract test paths from arch_fitness job
    test_paths = re.findall(r'tests/architecture/test_\w+\.py', content)
    for test_path in test_paths:
        full_path = ROOT / test_path
        assert full_path.exists(), \
            f"ARCH_FITNESS references non-existent test: {test_path}"


def test_security_policy_scanner_implementation():
    """Verify CI actually implements the scanner declared in security-policy."""
    policy_path = ROOT / 'security-policy.yaml'
    assert policy_path.exists(), "security-policy.yaml must exist"

    with policy_path.open() as f:
        policy = yaml.safe_load(f)

    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        ci_content = f.read()

    scanner = policy.get('secret_scanning', {}).get('scanner')
    assert scanner, "security-policy must declare secret_scanning.scanner"

    # Check for actual scanner execution
    scanner_execute_patterns = [
        rf'\/{scanner}\s+detect',
        rf'\/{scanner}\s+protect',
    ]

    found_execution = any(re.search(pat, ci_content) for pat in scanner_execute_patterns)

    assert found_execution, \
        f"CI must execute '{scanner}' scan command (e.g., '/tmp/{scanner} detect')"


def test_secret_dependency_has_supplementary_checks():
    """SECRET_DEPENDENCY must have supplementary grep-based checks."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Check for supplementary secret pattern checks
    assert 'ANOVELOS_.*SECRET' in content or 'api[_-]key' in content, \
        "SECRET_DEPENDENCY must include supplementary grep-based secret checks"


def test_secret_dependency_has_checksum_verification():
    """SECRET_DEPENDENCY must verify gitleaks checksum."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Check for SHA256 checksum verification
    assert 'sha256sum -c' in content.lower() or 'GITLEAKS_SHA256' in content, \
        "SECRET_DEPENDENCY must verify gitleaks binary with checksum"


def test_static_gate_uses_real_tools():
    """STATIC gate must use real formatter/linter/typechecker."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Check for real tools
    has_ruff = 'ruff format' in content or 'ruff check' in content
    has_mypy = 'mypy' in content

    assert has_ruff or has_mypy, \
        "STATIC gate must use real formatter/linter (ruff) or typechecker (mypy)"


def test_secret_dependency_has_real_vulnerability_scanner():
    """SECRET_DEPENDENCY must have real vulnerability scanner."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Should have real vulnerability scanning
    has_pip_audit = 'pip-audit' in content
    has_safety = 'safety check' in content

    # Must have at least one real scanner
    assert has_pip_audit or has_safety, \
        "SECRET_DEPENDENCY must include real vulnerability scanner (pip-audit or safety)"


def test_ci_does_not_modify_plan_directory():
    """CI validation output must go to dist/, not modify plan/."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Should use --output-dir to dist/
    assert '--output-dir' in content or 'dist/ci/schema' in content, \
        "SCHEMA_CONTRACT must output to dist/, not modify plan/validation/"


def test_ci_references_exist():
    """All files referenced in CI must actually exist."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Extract test file references
    test_refs = re.findall(r'tests/[a-z_/]+/test_[a-z_]+\.py', content)

    for test_ref in test_refs:
        test_path = ROOT / test_ref
        assert test_path.exists(), \
            f"CI references non-existent test: {test_ref}"

    # Extract script references
    script_refs = re.findall(r'(plan/scripts/[a-z_]+\.py)', content)

    for script_ref in script_refs:
        script_path = ROOT / script_ref
        assert script_path.exists(), \
            f"CI references non-existent script: {script_ref}"


def test_production_scan_isolated_from_fixtures():
    """Production secret scan must exclude test fixtures directory."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Should have test fixture exclusion pattern
    assert 'tests/fixtures' in content or 'grep -v' in content, \
        "Production secret scan should exclude test fixtures"


def test_security_policy_yaml_is_required_artifact():
    """security-policy.yaml must remain in V2-004 required artifacts."""
    backlog_path = ROOT / 'plan/machine/implementation-backlog.yaml'
    with backlog_path.open() as f:
        data = yaml.safe_load(f)

    tasks = {task['task_id']: task for task in data.get('tasks', [])}
    assert 'V2-004' in tasks, "V2-004 must exist in backlog"

    v2_004 = tasks['V2-004']
    assert 'artifacts' in v2_004, "V2-004 must have artifacts"
    assert 'security-policy.yaml' in v2_004['artifacts'], \
        "security-policy.yaml must be V2-004 required artifact"


def test_pip_audit_is_locked_dependency():
    """pip-audit must be in pyproject.toml dev dependencies."""
    pyproject_path = ROOT / 'pyproject.toml'

    with pyproject_path.open() as f:
        content = f.read()

    # pip-audit must be in dependencies
    assert 'pip-audit' in content, \
        "pip-audit must be declared in pyproject.toml dev dependencies"


def test_locked_tools_used_in_ci():
    """CI must use locked tools via 'uv run'."""
    ci_path = ROOT / '.github/workflows/ci.yml'
    with ci_path.open() as f:
        content = f.read()

    # Tools that should be in uv.lock and used via uv run
    locked_tools = {
        'ruff': 'ruff',
        'mypy': 'mypy',
        'pip-audit': 'pip-audit',
    }

    for tool_name, command in locked_tools.items():
        # If tool is used in CI
        if command in content:
            # Check it's called via uv run
            assert f'uv run {command}' in content or f'uv run python' in content, \
                f"CI should use locked {tool_name} via 'uv run'"
