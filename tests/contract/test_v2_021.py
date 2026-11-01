"""Acceptance tests for V2-021 NarrativeDelta Extractor.

Tests extraction of state changes from prose with evidence binding.
"""

import hashlib
from datetime import datetime

import pytest

from anovel.contracts.compiler import ContractCompiler
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.extractor import ExtractionStatus
from anovel.workflow.offline_extractor import OfflineExtractor


@pytest.fixture
def base_vision():
    """Base series vision for tests."""
    return SeriesVision(
        series_id="test-extract-001",
        title="Extraction Test",
        synopsis="Testing extraction",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )


def test_at_v2_021_01_prose_hash_verification(base_vision):
    """AT-V2-021-01: Prose hash mismatch MUST block extraction."""
    extractor = OfflineExtractor()

    prose = "Chapter 1: The beginning of the story."
    wrong_hash = "0" * 64  # Wrong hash

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=wrong_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # MUST fail on hash mismatch
    assert result.status == ExtractionStatus.FAILED
    assert "hash mismatch" in " ".join(result.issues).lower()
    assert result.delta is None


def test_at_v2_021_02_extraction_with_required_transitions(base_vision):
    """AT-V2-021-02: Extract required transitions from prose."""
    extractor = OfflineExtractor()

    # Prose that mentions the fact path
    prose = """
    Chapter 1: The funding was secured.

    After months of negotiations, the startup successfully obtained
    the funding_amount of $10,000,000 from Sequoia Capital.
    The team celebrated this milestone.
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="funding",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=10000000,
                rationale="Funding secured",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should find the transition
    assert result.status == ExtractionStatus.SUCCESS
    assert result.diagnostics.required_transitions_found == 1
    assert result.diagnostics.required_transitions_missing == 0
    assert len(result.operation_evidence) == 1
    assert result.operation_evidence[0].fact_path == "funding_amount"
    assert result.operation_evidence[0].evidence_locations[0].verified is True


def test_at_v2_021_03_missing_required_transitions(base_vision):
    """AT-V2-021-03: Missing required transitions MUST be detected."""
    extractor = OfflineExtractor()

    prose = "Chapter 1: Nothing specific happened."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="missing",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.location",
                target_value="New York",
                rationale="Move to New York",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should be incomplete
    assert result.status in [ExtractionStatus.FAILED, ExtractionStatus.INCOMPLETE]
    assert result.diagnostics.required_transitions_found == 0
    assert result.diagnostics.required_transitions_missing == 1


def test_at_v2_021_04_no_changes_distinction(base_vision):
    """AT-V2-021-04: Distinguish 'no changes' from 'extraction failed'."""
    extractor = OfflineExtractor()

    prose = "Chapter 1: The day passed without incident."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    # Contract with NO required transitions
    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],  # No required transitions
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should be NO_CHANGES (not FAILED)
    assert result.status == ExtractionStatus.NO_CHANGES
    assert result.delta is not None
    assert len(result.delta.operations) == 0


def test_at_v2_021_05_evidence_location_verification(base_vision):
    """AT-V2-021-05: Evidence locations must be verified."""
    extractor = OfflineExtractor()

    prose = "The protagonist moved to protagonist.location New York City."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="move",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.location",
                target_value="New York",
                rationale="Move to NYC",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should find evidence
    assert len(result.operation_evidence) > 0
    evidence = result.operation_evidence[0]

    # Evidence location should be valid
    assert evidence.evidence_locations[0].start_char >= 0
    assert evidence.evidence_locations[0].end_char <= len(prose)
    assert evidence.evidence_locations[0].verified is True
    assert "protagonist.location" in evidence.evidence_locations[0].text_snippet


def test_at_v2_021_06_project_id_from_series_vision(base_vision):
    """AT-V2-021-06: Project ID must come from series_vision."""
    extractor = OfflineExtractor()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Project ID must match series_vision
    assert result.delta is not None
    assert str(result.delta.project_id) == base_vision.series_id
    assert str(result.delta.project_id) == "test-extract-001"


def test_at_v2_021_07_prose_hash_in_provenance(base_vision):
    """AT-V2-021-07: Prose hash must be in delta provenance."""
    extractor = OfflineExtractor()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Prose hash must be in provenance
    assert result.delta is not None
    provenance_dict = dict(result.delta.provenance)
    assert "prose_hash" in provenance_dict
    assert provenance_dict["prose_hash"] == prose_hash


def test_at_v2_021_08_mock_prose_marker_detection(base_vision):
    """AT-V2-021-08: Mock prose markers must be detected."""
    extractor = OfflineExtractor()

    prose = "[OFFLINE TEST PROSE] This is not real content."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should detect mock marker
    assert "mock" in " ".join(result.issues).lower() or "test" in " ".join(result.issues).lower()
