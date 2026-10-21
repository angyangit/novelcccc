"""Test CommitReceipt JSON Schema validation."""

import json
import re
from datetime import datetime
from pathlib import Path

import jsonschema
import pytest


# Enforce RFC 3339 without relying on jsonschema's optional format extras.
# Restrict dates to ISO calendar syntax and require an explicit UTC offset.
_RFC3339_TIMESTAMP = re.compile(
    r"^\\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\\d|3[01])"
    r"T(?:[01]\\d|2[0-3]):[0-5]\\d:[0-5]\\d"
    r"(?:\\.\\d+)?(?:Z|[+-](?:[01]\\d|2[0-3]):[0-5]\\d)$"
)


def strict_format_checker():
    """Return a FormatChecker that always validates RFC 3339 date-time."""
    checker = jsonschema.FormatChecker()

    @checker.checks("date-time")
    def is_rfc3339(value):
        if not isinstance(value, str):
            return True  # The JSON Schema 'type' keyword handles non-strings.
        if _RFC3339_TIMESTAMP.fullmatch(value) is None:
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    return checker


def load_schema():
    """Load CommitReceipt JSON Schema."""
    schema_path = Path(__file__).parent.parent.parent / "specs" / "schemas" / "commit-receipt.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def test_commit_receipt_schema_valid_new():
    """Test valid new commit receipt passes schema validation."""
    schema = load_schema()

    receipt = {
        "commit_id": "commit-abc123def456",
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "a" * 64,
        "recovered": False
    }

    # Should not raise
    jsonschema.validate(receipt, schema, format_checker=strict_format_checker())


def test_commit_receipt_schema_valid_recovered():
    """Test valid recovered commit receipt passes schema validation."""
    schema = load_schema()

    receipt = {
        "commit_id": "commit-123abc456def",
        "project_id": "another-project",
        "branch_name": "feature",
        "idempotency_key": "idem-retry-789",
        "committed_at": "2026-10-21T15:45:30+00:00",
        "payload_hash": "f" * 64,
        "recovered": True
    }

    # Should not raise
    jsonschema.validate(receipt, schema, format_checker=strict_format_checker())


def test_commit_receipt_schema_missing_required():
    """Test receipt missing required field fails validation."""
    schema = load_schema()

    # Missing commit_id
    receipt = {
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "a" * 64,
        "recovered": False
    }

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(receipt, schema, format_checker=strict_format_checker())
    assert "'commit_id' is a required property" in str(exc_info.value)


def test_commit_receipt_schema_invalid_commit_id():
    """Test invalid commit_id pattern fails validation."""
    schema = load_schema()

    receipt = {
        "commit_id": "invalid-format",  # Should be commit-<12 hex>
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "a" * 64,
        "recovered": False
    }

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(receipt, schema, format_checker=strict_format_checker())
    assert "does not match" in str(exc_info.value)


def test_commit_receipt_schema_invalid_payload_hash():
    """Test invalid payload_hash pattern fails validation."""
    schema = load_schema()

    receipt = {
        "commit_id": "commit-abc123def456",
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "tooshort",  # Should be 64 hex chars
        "recovered": False
    }

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(receipt, schema, format_checker=strict_format_checker())
    assert "does not match" in str(exc_info.value)


def test_commit_receipt_schema_invalid_datetime():
    """Invalid RFC 3339 timestamps must be rejected, never silently accepted."""
    schema = load_schema()

    receipt = {
        "commit_id": "commit-abc123def456",
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "a" * 64,
        "recovered": False,
    }

    checker = strict_format_checker()
    for bad_timestamp in (
        "not-a-datetime",
        "2026-02-30T12:00:00Z",
        "2026-10-21T10:30:00",  # No time-zone offset
        "2026-10-21 10:30:00Z",  # A space is not RFC 3339 'T'
    ):
        receipt["committed_at"] = bad_timestamp
        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(receipt, schema, format_checker=checker)
        assert exc_info.value.validator == "format"


def test_commit_receipt_schema_no_additional_properties():
    """Test additional properties are rejected."""
    schema = load_schema()

    receipt = {
        "commit_id": "commit-abc123def456",
        "project_id": "novel-project",
        "branch_name": "main",
        "idempotency_key": "idem-key-123",
        "committed_at": "2026-10-21T10:30:00Z",
        "payload_hash": "a" * 64,
        "recovered": False,
        "extra_field": "not allowed"  # Should be rejected
    }

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(receipt, schema, format_checker=strict_format_checker())
    assert "Additional properties are not allowed" in str(exc_info.value)
