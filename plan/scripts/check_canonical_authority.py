#!/usr/bin/env python3
"""
Regression check: Verify canonical repository authority is correctly configured.

This check ensures that active entry points consistently declare GitHub as the
canonical repository, preventing future misconfiguration.

Focus: Active entry points that AI agents read for current operational guidance.
Excludes: Historical archives, execution evidence, and technical documentation.
"""

import sys
from pathlib import Path

# Files that must declare GitHub as canonical
ACTIVE_ENTRY_POINTS = [
    "AGENTS.md",
    "README.md",
    "PROJECT_STATUS.md",
]

# Correct canonical repository
CORRECT_CANONICAL = "https://github.com/angyangit/novelcccc.git"

# Incorrect patterns that should NOT appear in active entry points
FORBIDDEN_PATTERNS = [
    ("GitLab as the sole canonical", "Must not declare GitLab as sole canonical platform"),
    ("git fetch gitlab --prune", "Must not instruct fetching from gitlab remote"),
    ("git rev-parse gitlab/main", "Must not reference gitlab/main as canonical HEAD"),
    ("https://gitlab.com/angyang582821422/novelcccc.git", "GitLab URL must not be declared as canonical repository"),
]

def check_file(file_path: Path) -> list[str]:
    """Check a single file for canonical authority correctness."""
    errors = []

    if not file_path.exists():
        errors.append(f"MISSING: {file_path} does not exist")
        return errors

    content = file_path.read_text()

    # Check for correct canonical declaration
    if file_path.name in ["AGENTS.md", "README.md", "PROJECT_STATUS.md"]:
        if "Canonical Repository" in content or "CANONICAL REPOSITORY" in content:
            if CORRECT_CANONICAL not in content:
                errors.append(
                    f"MISSING_GITHUB: {file_path} has Canonical Repository section "
                    f"but does not declare {CORRECT_CANONICAL}"
                )

    # Check for forbidden patterns (only in canonical declaration sections)
    lines = content.split('\n')
    in_canonical_section = False

    for i, line in enumerate(lines):
        # Track if we're in a canonical repository section
        if "canonical repository" in line.lower() or "## canonical repository" in line.lower():
            in_canonical_section = True
        elif line.startswith("##") and in_canonical_section:
            in_canonical_section = False

        # Only check forbidden patterns in canonical sections
        if in_canonical_section:
            for pattern, reason in FORBIDDEN_PATTERNS:
                if pattern in line:
                    errors.append(
                        f"FORBIDDEN_PATTERN: {file_path}:{i+1} contains '{pattern}' - {reason}"
                    )

    return errors

def main():
    """Run canonical authority regression check."""
    repo_root = Path(__file__).resolve().parents[2]
    all_errors = []

    print("Canonical Repository Authority Check")
    print("=" * 60)
    print()

    for file_name in ACTIVE_ENTRY_POINTS:
        file_path = repo_root / file_name
        print(f"Checking {file_name}...", end=" ")

        errors = check_file(file_path)

        if errors:
            print("FAIL")
            all_errors.extend(errors)
        else:
            print("PASS")

    print()

    if all_errors:
        print("ERRORS FOUND:")
        print("-" * 60)
        for error in all_errors:
            print(f"  {error}")
        print()
        print(f"Total errors: {len(all_errors)}")
        return 1
    else:
        print("All checks passed!")
        print()
        print(f"Verified: {len(ACTIVE_ENTRY_POINTS)} entry points correctly declare")
        print(f"          {CORRECT_CANONICAL}")
        print(f"          as canonical repository")
        return 0

if __name__ == "__main__":
    sys.exit(main())
