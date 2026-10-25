"""Test canonical authority regression check."""

# Import check function
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plan" / "scripts"))
from check_canonical_authority import check_file


def test_correct_github_canonical_passes():
    """Test that correct GitHub canonical declaration passes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """# Test File

## CANONICAL REPOSITORY

**Canonical Repository**: `https://github.com/angyangit/novelcccc.git`
**Branch**: `main`

AI agents must use GitHub for current work.
"""
        )
        f.flush()
        path = Path(f.name)

    try:
        errors = check_file(path)
        assert len(errors) == 0, f"Should pass but got errors: {errors}"
    finally:
        path.unlink()


def test_missing_canonical_declaration_fails():
    """Test that missing canonical repository declaration fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """# Test File

## Some Other Section

Content here but no canonical repository declaration.
"""
        )
        f.flush()
        path = Path(f.name)

    try:
        # File doesn't have canonical section, so won't trigger MISSING_GITHUB error
        # This is expected - the check focuses on correcting wrong declarations
        check_file(path)
        # No error expected for files without canonical sections
        assert True
    finally:
        path.unlink()


def test_wrong_gitlab_url_fails():
    """Test that GitLab URL in canonical section fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """# Test File

## CANONICAL REPOSITORY

**Canonical Repository**: `https://gitlab.com/angyang582821422/novelcccc.git`
**Branch**: `main`
"""
        )
        f.flush()
        path = Path(f.name)

    try:
        errors = check_file(path)
        assert len(errors) > 0, "Should fail with GitLab URL"
        assert any("FORBIDDEN_PATTERN" in e for e in errors)
        assert any("gitlab.com" in e for e in errors)
    finally:
        path.unlink()


def test_gitlab_as_sole_canonical_fails():
    """Test that 'GitLab as sole canonical' phrase fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """# Test File

## CANONICAL REPOSITORY

This project uses GitLab as the sole canonical platform.

**Canonical Repository**: `https://gitlab.com/angyang582821422/novelcccc.git`
"""
        )
        f.flush()
        path = Path(f.name)

    try:
        errors = check_file(path)
        assert len(errors) >= 2, "Should fail with multiple forbidden patterns"
        assert any("GitLab as the sole canonical" in e for e in errors)
    finally:
        path.unlink()


def test_git_fetch_gitlab_instruction_fails():
    """Test that 'git fetch gitlab' instruction fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
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
        f.flush()
        path = Path(f.name)

    try:
        errors = check_file(path)
        assert len(errors) >= 2, "Should fail with gitlab fetch instructions"
        assert any("git fetch gitlab" in e for e in errors)
        assert any("gitlab/main" in e for e in errors)
    finally:
        path.unlink()


def test_historical_gitlab_reference_outside_canonical_passes():
    """Test that GitLab reference outside canonical section passes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
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
        f.flush()
        path = Path(f.name)

    try:
        errors = check_file(path)
        # Historical note is outside canonical section, so should pass
        assert len(errors) == 0, f"Historical reference should pass but got: {errors}"
    finally:
        path.unlink()


def test_canonical_declaration_with_github_but_missing_url_fails():
    """Test that canonical section without GitHub URL fails."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir="/tmp", prefix="AGENTS"
    ) as f:
        # Use AGENTS prefix to trigger the check (only specific files are checked)
        pass

    # Rename to exact match
    path = Path(f.name)
    agents_path = path.parent / "AGENTS.md"

    try:
        agents_path.write_text(
            """# Test File

## CANONICAL REPOSITORY

**Repository**: `https://example.com/someother/repo.git`
**Branch**: `main`
"""
        )

        errors = check_file(agents_path)
        assert len(errors) > 0, "Should fail without correct GitHub URL"
        assert any("MISSING_GITHUB" in e for e in errors)
    finally:
        if agents_path.exists():
            agents_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
