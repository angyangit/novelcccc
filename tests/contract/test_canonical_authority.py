"""Test canonical authority regression check."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plan" / "scripts"))
from check_canonical_authority import check_file


def test_correct_github_canonical_passes(tmp_path):
    """Test that correct GitHub canonical declaration passes."""
    test_file = tmp_path / "AGENTS.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

**Canonical Repository**: `https://github.com/angyangit/novelcccc.git`
**Branch**: `main`

AI agents must use GitHub for current work.
"""
    )

    errors = check_file(test_file)
    assert len(errors) == 0, f"Should pass but got errors: {errors}"


def test_missing_canonical_declaration_fails(tmp_path):
    """Test that missing canonical repository declaration fails."""
    test_file = tmp_path / "AGENTS.md"
    test_file.write_text(
        """# Test File

## Some Other Section

Content here but no canonical repository declaration.
"""
    )

    errors = check_file(test_file)
    assert len(errors) > 0, "Should fail when canonical section is missing"
    assert any(
        "MISSING_CANONICAL_SECTION" in e for e in errors
    ), f"Should report missing canonical section, got: {errors}"


def test_wrong_gitlab_url_fails(tmp_path):
    """Test that GitLab URL in canonical section fails."""
    test_file = tmp_path / "README.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

**Canonical Repository**: `https://gitlab.com/angyang582821422/novelcccc.git`
**Branch**: `main`
"""
    )

    errors = check_file(test_file)
    assert len(errors) > 0, "Should fail with GitLab URL"
    assert any("FORBIDDEN_PATTERN" in e for e in errors)
    assert any("gitlab.com" in e for e in errors)


def test_gitlab_as_sole_canonical_fails(tmp_path):
    """Test that 'GitLab as sole canonical' phrase fails."""
    test_file = tmp_path / "PROJECT_STATUS.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

This project uses GitLab as the sole canonical platform.

**Canonical Repository**: `https://gitlab.com/angyang582821422/novelcccc.git`
"""
    )

    errors = check_file(test_file)
    assert len(errors) >= 2, "Should fail with multiple forbidden patterns"
    assert any("GitLab as the sole canonical" in e for e in errors)


def test_git_fetch_gitlab_instruction_fails(tmp_path):
    """Test that 'git fetch gitlab' instruction fails."""
    test_file = tmp_path / "AGENTS.md"
    test_file.write_text(
        """# Test File

## Canonical Repository

**Repository**: `https://github.com/angyangit/novelcccc.git`

Before any task:
```bash
git fetch gitlab --prune
git rev-parse gitlab/main
```
"""
    )

    errors = check_file(test_file)
    assert len(errors) >= 2, "Should fail with gitlab fetch instructions"
    assert any("git fetch gitlab" in e for e in errors)
    assert any("gitlab/main" in e for e in errors)


def test_historical_gitlab_reference_outside_canonical_passes(tmp_path):
    """Test that GitLab reference outside canonical section passes."""
    test_file = tmp_path / "README.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

**Canonical Repository**: `https://github.com/angyangit/novelcccc.git`
**Branch**: `main`

---

## Historical Note

Earlier work used GitLab (gitlab.com/angyang582821422/novelcccc).
This is preserved for reference only.
"""
    )

    errors = check_file(test_file)
    # Historical note is outside canonical section, so should pass
    assert len(errors) == 0, f"Historical reference should pass but got: {errors}"


def test_canonical_declaration_with_github_but_missing_url_fails(tmp_path):
    """Test that canonical section without GitHub URL fails."""
    test_file = tmp_path / "AGENTS.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

**Repository**: `https://example.com/someother/repo.git`
**Branch**: `main`
"""
    )

    errors = check_file(test_file)
    assert len(errors) > 0, "Should fail without correct GitHub URL"
    assert any("MISSING_GITHUB" in e for e in errors)


def test_canonical_header_exists_but_no_url_at_all_fails(tmp_path):
    """Test that canonical section with no repository URL at all fails."""
    test_file = tmp_path / "PROJECT_STATUS.md"
    test_file.write_text(
        """# Test File

## Canonical Repository

This section exists but has no actual repository URL declared.

**Branch**: `main`
"""
    )

    errors = check_file(test_file)
    assert len(errors) > 0, "Should fail when canonical section lacks any URL"
    assert any("MISSING_GITHUB" in e for e in errors)


def test_github_url_only_in_historical_section_fails(tmp_path):
    """Test that GitHub URL only in historical section fails."""
    test_file = tmp_path / "AGENTS.md"
    test_file.write_text(
        """# Test File

## CANONICAL REPOSITORY

**Repository**: `https://example.com/wrong/repo.git`
**Branch**: `main`

---

## Historical Note

The correct repository is https://github.com/angyangit/novelcccc.git but
it's only mentioned here in the historical section, not in the canonical declaration.
"""
    )

    errors = check_file(test_file)
    assert len(errors) > 0, "Should fail when correct URL only in historical section"
    assert any("MISSING_GITHUB" in e for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
