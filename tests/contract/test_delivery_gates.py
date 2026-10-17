"""Delivery gate contract tests for V2-004.

These tests verify CI gate requirements and anti-weakening properties.
They run locally and do not depend on the CI platform being online.

Current CI platform: GitHub Actions (.github/workflows/ci.yml)
Historical baseline: GitLab CI (archived at docs/archive/platform/gitlab-ci-historical.yml)
"""
import json
from pathlib import Path
import re
import yaml
import pytest

ROOT = Path(__file__).resolve().parents[2]
CURRENT_CI_PATH = ROOT / '.github/workflows/ci.yml'


def load_ci_workflow():
    """Load and parse GitHub Actions workflow."""
    with CURRENT_CI_PATH.open() as f:
        return yaml.safe_load(f)


def get_job_steps(workflow, job_name):
    """Extract steps from a GitHub Actions job."""
    jobs = workflow.get('jobs', {})
    job = jobs.get(job_name.replace('_', '-'), {})  # GitHub uses kebab-case
    if not job:
        job = jobs.get(job_name, {})  # Try original name
    return job.get('steps', [])


def get_job_run_commands(workflow, job_name):
    """Extract all run commands from a job's steps."""
    steps = get_job_steps(workflow, job_name)
    commands = []
    for step in steps:
        if 'run' in step:
            commands.append(step['run'])
    return '\n'.join(commands)


# ============================================================================
# Machine SSOT Gate Structure Tests
# ============================================================================

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


def test_ci_gates_not_reduced_from_baseline():
    """Number of P0 gates must not decrease."""
    gates_path = ROOT / 'plan/machine/ci-gates.yaml'
    with gates_path.open() as f:
        data = yaml.safe_load(f)

    p0_gates = [g for g in data['gates'] if g['activation_phase'] == 'P0']

    assert len(p0_gates) >= 6, \
        f"Must have at least 6 P0 gates, found {len(p0_gates)}"


# ============================================================================
# GitHub Actions CI Existence and Structure Tests
# ============================================================================

def test_github_ci_exists():
    """GitHub Actions CI configuration must exist."""
    assert CURRENT_CI_PATH.exists(), ".github/workflows/ci.yml must exist"


def test_github_ci_yaml_is_valid():
    """GitHub Actions CI YAML must be syntactically valid."""
    assert CURRENT_CI_PATH.exists()

    with CURRENT_CI_PATH.open() as f:
        try:
            yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"GitHub Actions CI YAML is invalid: {e}")


def test_github_ci_has_p0_jobs():
    """GitHub Actions CI must define jobs for P0 gates."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Check for job definitions
    required_jobs = [
        'static', 'unit', 'schema_contract',
        'arch_fitness', 'secret_dependency', 'postgres_env'
    ]

    content_lower = content.lower()
    for job in required_jobs:
        # GitHub Actions uses kebab-case for job IDs
        assert job.replace('_', '-') in content_lower or job in content_lower, \
            f"CI must include job for {job}"


def test_github_ci_uses_locked_dependencies():
    """CI must use locked dependencies (uv sync --frozen)."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    assert 'uv sync --frozen' in content, \
        "CI must use uv sync --frozen for locked dependencies"


def test_github_ci_uses_postgres_service():
    """CI must include PostgreSQL service for POSTGRES_ENV gate."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    assert 'postgres:' in content, \
        "CI must include PostgreSQL service"


# ============================================================================
# Locked Dependencies and Tool Version Tests
# ============================================================================

def test_locked_dependencies_file_exists():
    """uv.lock must exist and not be bypassed."""
    lock_path = ROOT / 'uv.lock'
    assert lock_path.exists(), "uv.lock must exist for locked dependencies"


def test_locked_tools_used_in_ci():
    """CI must use locked tools via 'uv run'."""
    with CURRENT_CI_PATH.open() as f:
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


def test_pip_audit_is_locked_dependency():
    """pip-audit must be in pyproject.toml dev dependencies."""
    pyproject_path = ROOT / 'pyproject.toml'

    with pyproject_path.open() as f:
        content = f.read()

    # pip-audit must be in dependencies
    assert 'pip-audit' in content, \
        "pip-audit must be declared in pyproject.toml dev dependencies"


def test_no_post_lock_dependency_mutation():
    """After uv sync --frozen, CI must not install additional tools dynamically."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Check for patterns that would bypass locked environment
    # Allow pip install uv (bootstrap), but not project tools after sync
    lines = content.split('\n')
    found_sync = False
    for i, line in enumerate(lines):
        if 'uv sync --frozen' in line:
            found_sync = True
        elif found_sync and 'pip install' in line and 'uv==' not in line:
            # After sync, pip install (except bootstrap) is suspicious
            if i + 1 < len(lines):
                context = '\n'.join(lines[max(0,i-2):i+3])
                pytest.fail(
                    f"Found 'pip install' after 'uv sync --frozen': {line.strip()}\n"
                    f"Context:\n{context}\n"
                    f"This may bypass locked environment"
                )


# ============================================================================
# P0 Gate Command Tests
# ============================================================================

def test_static_gate_uses_real_tools():
    """STATIC gate must use real formatter/linter/typechecker."""
    workflow = load_ci_workflow()
    commands = get_job_run_commands(workflow, 'static')

    # Check for real tools
    has_ruff = 'ruff format' in commands or 'ruff check' in commands
    has_mypy = 'mypy' in commands

    assert has_ruff or has_mypy, \
        "STATIC gate must use real formatter/linter (ruff) or typechecker (mypy)"


def test_secret_dependency_has_real_vulnerability_scanner():
    """SECRET_DEPENDENCY must have real vulnerability scanner."""
    workflow = load_ci_workflow()
    commands = get_job_run_commands(workflow, 'secret_dependency')

    # Should have real vulnerability scanning
    has_pip_audit = 'pip-audit' in commands
    has_safety = 'safety check' in commands

    # Must have at least one real scanner
    assert has_pip_audit or has_safety, \
        "SECRET_DEPENDENCY must include real vulnerability scanner (pip-audit or safety)"


# ============================================================================
# Secret Scanning Anti-Weakening Tests
# ============================================================================

def test_ci_would_detect_secret_fixture():
    """SECRET_DEPENDENCY gate includes secret scanning logic."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Verify secret_dependency job has actual scanning logic
    assert 'secret' in content.lower() or 'gitleaks' in content.lower(), \
        "CI must include secret scanning reference"


def test_ci_would_detect_dependency_issues():
    """SECRET_DEPENDENCY gate includes dependency checking logic."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Verify dependency checking
    assert 'uv pip check' in content or 'pip-audit' in content, \
        "CI must include dependency validation"


def test_security_policy_scanner_implementation():
    """Verify CI actually implements the scanner declared in security-policy."""
    policy_path = ROOT / 'security-policy.yaml'
    assert policy_path.exists(), "security-policy.yaml must exist"

    with policy_path.open() as f:
        policy = yaml.safe_load(f)

    with CURRENT_CI_PATH.open() as f:
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
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Check for supplementary secret pattern checks
    assert 'ANOVELOS_.*SECRET' in content or 'api[_-]key' in content, \
        "SECRET_DEPENDENCY must include supplementary grep-based secret checks"


def test_secret_dependency_has_checksum_verification():
    """SECRET_DEPENDENCY must verify gitleaks checksum."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Check for SHA256 checksum verification
    assert 'sha256sum -c' in content.lower() or 'GITLEAKS_SHA256' in content, \
        "SECRET_DEPENDENCY must verify gitleaks binary with checksum"


def test_secret_dependency_no_failure_suppression():
    """SECRET_DEPENDENCY must not suppress failures with || true or similar."""
    workflow = load_ci_workflow()
    commands = get_job_run_commands(workflow, 'secret_dependency')

    # Check for failure-swallowing patterns
    forbidden_patterns = [
        r'\|\|\s*true',
        r'\|\|\s*exit\s+0',
        r'\|\|\s*:',
        r'continue-on-error:\s*true',
    ]

    for pattern in forbidden_patterns:
        if re.search(pattern, commands):
            pytest.fail(
                f"SECRET_DEPENDENCY must not use failure suppression pattern: {pattern}\n"
                f"Found in commands:\n{commands}"
            )


def test_security_policy_exclusions_match_gitleaks_allowlist():
    """Verify security-policy exclusions align with gitleaks allowlist."""
    policy_path = ROOT / 'security-policy.yaml'
    assert policy_path.exists(), "security-policy.yaml must exist"

    with policy_path.open() as f:
        policy = yaml.safe_load(f)

    # Read gitleaks config - parse as TOML
    gitleaks_config_path = ROOT / '.gitleaks.toml'
    assert gitleaks_config_path.exists(), ".gitleaks.toml must exist"

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with gitleaks_config_path.open('rb') as f:
        gitleaks_config = tomllib.load(f)

    # Get policy exclusions
    policy_exclusions = policy.get('secret_scanning', {}).get('exclusions', [])
    assert policy_exclusions, "security-policy should declare exclusions"

    # Normalize policy exclusions
    policy_files = set()
    for exclusion in policy_exclusions:
        if isinstance(exclusion, str):
            policy_files.add(exclusion)
        elif isinstance(exclusion, dict):
            policy_files.add(exclusion.get('path', ''))

    # Get gitleaks allowlist paths
    gitleaks_paths = gitleaks_config.get('allowlist', {}).get('paths', [])
    assert gitleaks_paths, ".gitleaks.toml should have allowlist.paths"

    # Operational exclusions: CI cache/venv (outside policy scope)
    operational_exclusions = {
        r'(^|/)\.cache/',
        r'(^|/)\.venv/',
    }

    # Forward check: policy → gitleaks
    missing_in_gitleaks = []
    for policy_file in policy_files:
        if not policy_file:
            continue

        # Check if this path appears in gitleaks allowlist
        found = False
        for gitleaks_pattern in gitleaks_paths:
            if (policy_file in gitleaks_pattern or
                policy_file.replace('.', r'\.') in gitleaks_pattern):
                found = True
                break

        if not found:
            missing_in_gitleaks.append(policy_file)

    assert not missing_in_gitleaks, \
        f"security-policy exclusions not found in .gitleaks.toml: {missing_in_gitleaks}"

    # Reverse check: gitleaks → policy (minus operational)
    unexpected_in_gitleaks = []
    for gitleaks_pattern in gitleaks_paths:
        if gitleaks_pattern in operational_exclusions:
            continue

        found = False
        for policy_file in policy_files:
            if (policy_file in gitleaks_pattern or
                policy_file.replace('.', r'\.') in gitleaks_pattern):
                found = True
                break

        if not found:
            unexpected_in_gitleaks.append(gitleaks_pattern)

    assert not unexpected_in_gitleaks, \
        f".gitleaks.toml has exclusions not declared in security-policy: {unexpected_in_gitleaks}"


def test_production_scan_isolated_from_fixtures():
    """Production secret scan must exclude test fixtures directory."""
    workflow = load_ci_workflow()
    commands = get_job_run_commands(workflow, 'secret_dependency')

    # Should have test fixture exclusion pattern
    assert 'tests/fixtures' in commands or 'grep -v' in commands, \
        "Production secret scan should exclude test fixtures"


def test_secret_dependency_explicit_failure():
    """SECRET_DEPENDENCY must explicitly exit non-zero on violations."""
    workflow = load_ci_workflow()
    commands = get_job_run_commands(workflow, 'secret_dependency')

    # Should contain 'exit 1' for violations
    assert 'exit 1' in commands, \
        "SECRET_DEPENDENCY must explicitly fail on violations with exit 1"


# ============================================================================
# PostgreSQL Runtime Alignment Tests
# ============================================================================

def test_postgres_runtime_matches_compose():
    """GitHub Actions postgres service must match compose.yaml image."""
    # Read compose.yaml
    compose_path = ROOT / 'compose.yaml'
    assert compose_path.exists(), "compose.yaml must exist"

    with compose_path.open() as f:
        compose_data = yaml.safe_load(f)

    compose_postgres = compose_data.get('services', {}).get('postgres', {}).get('image', '')

    # Read GitHub workflow
    workflow = load_ci_workflow()
    postgres_job = workflow.get('jobs', {}).get('postgres-env', {})
    if not postgres_job:
        postgres_job = workflow.get('jobs', {}).get('postgres_env', {})

    services = postgres_job.get('services', {})
    postgres_service = services.get('postgres', {})
    gh_postgres = postgres_service.get('image', '')

    # Extract version and digest
    assert compose_postgres, "compose.yaml must define postgres image"
    assert gh_postgres, "GitHub Actions must define postgres image in POSTGRES_ENV"

    # They should match exactly (version + digest)
    assert compose_postgres == gh_postgres, \
        f"PostgreSQL images must match:\n" \
        f"  compose.yaml:     {compose_postgres}\n" \
        f"  GitHub Actions:   {gh_postgres}"


# ============================================================================
# CI Reference Integrity Tests
# ============================================================================

def test_ci_references_exist():
    """All files referenced in CI must actually exist."""
    with CURRENT_CI_PATH.open() as f:
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


def test_arch_fitness_references_existing_tests():
    """ARCH_FITNESS job must reference only existing test files."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Extract test paths from arch_fitness job
    test_paths = re.findall(r'tests/architecture/test_\w+\.py', content)
    for test_path in test_paths:
        full_path = ROOT / test_path
        assert full_path.exists(), \
            f"ARCH_FITNESS references non-existent test: {test_path}"


# ============================================================================
# Governance and Validation Tests
# ============================================================================

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


def test_ci_does_not_modify_plan_directory():
    """CI validation output must go to dist/, not modify plan/."""
    with CURRENT_CI_PATH.open() as f:
        content = f.read()

    # Should use --output-dir to dist/
    assert '--output-dir' in content or 'dist/ci/schema' in content, \
        "SCHEMA_CONTRACT must output to dist/, not modify plan/validation/"


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


# ============================================================================
# Infrastructure Tests
# ============================================================================

def test_gitignore_includes_dist():
    """dist/ must be in .gitignore (CI artifacts)."""
    gitignore_path = ROOT / '.gitignore'
    assert gitignore_path.exists()

    with gitignore_path.open() as f:
        content = f.read()

    assert 'dist/' in content, "dist/ must be in .gitignore"
