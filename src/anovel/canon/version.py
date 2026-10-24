"""Canon version management for reducer and schema compatibility.

Tracks versions for:
- DeltaReducer logic (how operations are interpreted)
- Schema structure (what fields and types are valid)

Version changes trigger explicit compatibility checks to prevent
silent semantic drift in historical state reconstruction.
"""

# Reducer version: incremented when DeltaReducer logic changes
# affect how operations are applied to CanonState
REDUCER_VERSION = "1.0.0"

# Schema version: incremented when domain model structure changes
# (FactPath registry, operation types, field definitions)
SCHEMA_VERSION = "1.0.0"


class VersionCompatibilityError(Exception):
    """Raised when version compatibility check fails."""

    pass


def check_reducer_compatibility(stored_version: str) -> bool:
    """Check if stored reducer version is compatible with current.

    Args:
        stored_version: Reducer version from stored snapshot

    Returns:
        True if compatible, False otherwise

    Note:
        V1 implementation: exact match required.
        Future: semantic versioning with backward compatibility rules.
    """
    return stored_version == REDUCER_VERSION


def check_schema_compatibility(stored_version: str) -> bool:
    """Check if stored schema version is compatible with current.

    Args:
        stored_version: Schema version from stored snapshot

    Returns:
        True if compatible, False otherwise

    Note:
        V1 implementation: exact match required.
        Future: migration paths for schema evolution.
    """
    return stored_version == SCHEMA_VERSION


def validate_versions(stored_reducer_version: str, stored_schema_version: str) -> None:
    """Validate stored versions are compatible with current runtime.

    Args:
        stored_reducer_version: Reducer version from snapshot
        stored_schema_version: Schema version from snapshot

    Raises:
        VersionCompatibilityError: If either version incompatible
    """
    if not check_reducer_compatibility(stored_reducer_version):
        raise VersionCompatibilityError(
            f"Incompatible reducer version: stored={stored_reducer_version}, "
            f"current={REDUCER_VERSION}. Cannot restore snapshot safely."
        )

    if not check_schema_compatibility(stored_schema_version):
        raise VersionCompatibilityError(
            f"Incompatible schema version: stored={stored_schema_version}, "
            f"current={SCHEMA_VERSION}. Cannot restore snapshot safely."
        )
