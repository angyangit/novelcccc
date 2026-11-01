"""Real Structured Extractor - Phase 3

Parses real LLM JSON output and constructs SetFactOperations.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from ..contracts.models import ChapterContract
from ..domain.delta import (
    DeltaId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    get_fact_path,
)
from ..domain.identity import EntityId, ProjectId
from ..planning.models import SeriesVision
from .extractor import (
    ExtractionDiagnostic,
    ExtractionStatus,
    NarrativeDeltaExtractionResult,
    OperationEvidence,
)


class StructuredExtractor:
    """Extracts state changes from LLM-generated structured JSON.

    Real extraction pipeline:
    1. LLM generates structured JSON with state_changes
    2. Parse and validate JSON schema
    3. Verify evidence positions against prose
    4. Construct SetFactOperations
    5. Build NarrativeDelta
    """

    def __init__(self, llm_gateway):
        """Initialize structured extractor.

        Args:
            llm_gateway: Gateway for LLM calls (must support real calls)
        """
        self.llm_gateway = llm_gateway

    def extract(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_parent: str,
    ) -> NarrativeDeltaExtractionResult:
        """Extract narrative delta using real LLM.

        Args:
            prose: Chapter prose
            prose_hash: SHA256 hash of prose
            contract: Chapter contract
            series_vision: Series vision
            canon_parent: Parent canon ID

        Returns:
            Extraction result with real Operations
        """
        issues = []

        # Verify prose hash
        actual_hash = hashlib.sha256(prose.encode()).hexdigest()
        if actual_hash != prose_hash:
            issues.append(f"Prose hash mismatch: expected {prose_hash[:16]}...")
            return self._create_failed_result(prose_hash, issues)

        # Build extraction prompt
        extraction_prompt = self._build_extraction_prompt(
            prose, contract, series_vision
        )

        # Call real LLM
        try:
            result, cost = self.llm_gateway.generate(
                prompt=extraction_prompt,
                max_tokens=2000,
                temperature=0.3,  # Lower temp for structured output
            )
            extraction_json = result["prose"]

            # Strip markdown code fences if present
            extraction_json = extraction_json.strip()
            if extraction_json.startswith("```"):
                lines = extraction_json.split("\n")
                # Remove first line (```json or ```) and last line (```)
                if len(lines) >= 3:
                    # Find first non-fence line
                    start_idx = 1
                    # Find last fence line
                    end_idx = len(lines) - 1
                    while end_idx > start_idx and not lines[end_idx].strip().startswith("```"):
                        end_idx -= 1
                    if lines[end_idx].strip().startswith("```"):
                        extraction_json = "\n".join(lines[start_idx:end_idx])
                    else:
                        # No closing fence found, take everything after opening fence
                        extraction_json = "\n".join(lines[start_idx:])

        except Exception as e:
            issues.append(f"LLM extraction failed: {e}")
            return self._create_failed_result(prose_hash, issues)

        # Parse JSON
        try:
            extraction_data = json.loads(extraction_json)
        except json.JSONDecodeError as e:
            # Common issue: Chinese quotation marks in evidence_text break JSON
            # Try one correction attempt with explicit budget allowance
            issues.append(f"Initial JSON parse failed: {e}")

            # Only attempt fix if within budget
            if len(extraction_json) < 50000:  # Safety limit
                try:
                    # Replace problematic Chinese punctuation that breaks JSON
                    # These appear in quoted book/category names within strings
                    corrected_json = extraction_json
                    # U+201C LEFT DOUBLE QUOTATION MARK "
                    # U+201D RIGHT DOUBLE QUOTATION MARK "
                    corrected_json = corrected_json.replace('“', '《').replace('”', '》')
                    # Also handle 「」
                    corrected_json = corrected_json.replace('「', '《').replace('」', '》')

                    extraction_data = json.loads(corrected_json)
                    issues.append("Warning: Auto-corrected Chinese quotation marks in JSON")
                except json.JSONDecodeError as e2:
                    issues.append(f"Correction attempt also failed: {e2}")
                    # Save for inspection
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir='.') as f:
                        f.write(extraction_json)
                        issues.append(f"Failed JSON saved to: {f.name}")
                    return self._create_failed_result(prose_hash, issues)
            else:
                return self._create_failed_result(prose_hash, issues)

        # Validate schema
        if not self._validate_extraction_schema(extraction_data):
            issues.append("Extraction schema validation failed")
            return self._create_failed_result(prose_hash, issues)

        # Build Operations
        operations, operation_evidence, extraction_issues = self._build_operations(
            extraction_data, prose, prose_hash, series_vision.series_id
        )
        issues.extend(extraction_issues)

        # Determine status
        required_count = len(contract.required_transitions)
        found_count = len(operations)

        if required_count > 0 and found_count == 0:
            status = ExtractionStatus.FAILED
        elif found_count < required_count:
            status = ExtractionStatus.INCOMPLETE
            issues.append(
                f"Required transitions: {found_count}/{required_count} extracted"
            )
        elif required_count == 0:
            status = ExtractionStatus.NO_CHANGES
        else:
            status = ExtractionStatus.SUCCESS

        # Build Delta
        delta = NarrativeDelta(
            delta_id=DeltaId(str(uuid.uuid4())),
            project_id=ProjectId(series_vision.series_id),
            operations=tuple(operations),
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="structured_extractor_real",
            provenance=(
                ("extraction_method", "llm_structured"),
                ("prose_hash", prose_hash),
                ("canon_parent", canon_parent),
            ),
        )

        diagnostics = ExtractionDiagnostic(
            coverage_percentage=(found_count / required_count * 100.0)
            if required_count > 0
            else 0.0,
            required_transitions_found=found_count,
            required_transitions_missing=required_count - found_count,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=issues.copy(),
        )

        return NarrativeDeltaExtractionResult(
            status=status,
            delta=delta,
            prose_hash=prose_hash,
            operation_evidence=operation_evidence,
            diagnostics=diagnostics,
            extraction_method="llm_structured",
            extracted_at=datetime.now(),
            issues=issues,
        )

    def _build_extraction_prompt(
        self, prose: str, contract: ChapterContract, series_vision: SeriesVision
    ) -> str:
        """Build LLM extraction prompt with strict JSON requirements."""
        required_facts = [t.fact_path for t in contract.required_transitions]

        prompt = f"""你是一个小说语义分析专家。请从以下小说正文中提取状态变化。

**小说正文**:
{prose}

**需要提取的状态变化** (fact_path):
{', '.join(required_facts) if required_facts else '无特定要求'}

**输出格式** (JSON):
{{
  "state_changes": [
    {{
      "fact_path": "状态路径",
      "value": "变化后的值",
      "evidence_text": "支持证据原文（至少15个字，提供上下文）",
      "evidence_start": 证据起始位置（大约即可）,
      "evidence_end": 证据结束位置（大约即可）,
      "confidence": "confirmed",
      "rationale": "提取理由"
    }}
  ]
}}

**重要规则**:
1. 只提取**已经发生**的事实变化，不提取计划、传闻、假设
2. evidence_text必须是正文的精确引用，至少15个字提供上下文
3. evidence_start和evidence_end是大致位置，用于定位，不必精确到字符
4. 如果没有确凿证据，不要猜测
5. 确保value的类型和值与正文一致
6. **严格禁止**：不要在JSON字符串中使用任何引号（包括：" " 「」《》' ' ‹›）
7. 书名、人名等用文字表述，不加标点：例如"时间简史"而非"《时间简史》"
8. 分类名称直接写：例如"物理学书架"而非"物理学"书架

请输出纯JSON（不要用markdown代码块包裹）:"""

        return prompt

    def _validate_extraction_schema(self, data: dict) -> bool:
        """Validate extraction JSON schema."""
        if "state_changes" not in data:
            return False
        if not isinstance(data["state_changes"], list):
            return False
        return True

    def _build_operations(
        self,
        extraction_data: dict,
        prose: str,
        prose_hash: str,
        project_id: str,
    ) -> tuple[list[SetFactOperation], list[OperationEvidence], list[str]]:
        """Build SetFactOperations from extraction data."""
        operations = []
        operation_evidence = []
        issues = []

        for i, change in enumerate(extraction_data.get("state_changes", [])):
            try:
                # Get fact path
                fact_path = get_fact_path(change["fact_path"])

                # Verify evidence (FUZZY MATCHING for LLM position approximations)
                evidence_start = change["evidence_start"]
                evidence_end = change["evidence_end"]
                evidence_text = change["evidence_text"]

                # Fuzzy position matching: LLM positions are approximate
                # Search for evidence_text near suggested position
                search_window = 50  # chars tolerance
                search_start = max(0, evidence_start - search_window)
                search_end = min(len(prose), evidence_end + search_window)
                search_region = prose[search_start:search_end]

                actual_start = evidence_start
                actual_end = evidence_end
                actual_snippet = ""

                # Try to find evidence_text in search region
                if evidence_text in search_region:
                    # Found - calculate actual position
                    relative_pos = search_region.index(evidence_text)
                    actual_start = search_start + relative_pos
                    actual_end = actual_start + len(evidence_text)
                    actual_snippet = prose[actual_start:actual_end]
                elif evidence_text in prose:
                    # Found elsewhere in prose - use first occurrence
                    actual_start = prose.index(evidence_text)
                    actual_end = actual_start + len(evidence_text)
                    actual_snippet = prose[actual_start:actual_end]
                    issues.append(
                        f"Change {i}: Evidence found at position {actual_start}, "
                        f"not near suggested {evidence_start} (fuzzy match used)"
                    )
                else:
                    # Not found - reject this change
                    issues.append(
                        f"Change {i}: Evidence text not found in prose: '{evidence_text[:50]}...'"
                    )
                    continue

                # Build operation
                # For now, use simplified subject (protagonist)
                # Full implementation would resolve entity from prose
                subject = EntityId("protagonist")

                operation = SetFactOperation(
                    operation_type=OperationType.SET_FACT,
                    operation_version="1.0.0",
                    subject=subject,
                    scope=ProjectId(project_id),
                    path=fact_path,
                    value=change["value"],
                    precondition=ExpectAbsent(),  # Simplified
                    evidence=EvidenceRef(
                        source_type="TEXT",
                        source_ref=f"chapter:{actual_start}-{actual_end}",
                        content_hash=prose_hash,
                    ),
                )

                # Validate operation
                operation.validate_schema()
                operations.append(operation)

                # Build evidence
                from .extractor import EvidenceLocation

                op_evidence = OperationEvidence(
                    operation_index=len(operations) - 1,
                    fact_path=change["fact_path"],
                    extracted_value=change["value"],
                    evidence_locations=[
                        EvidenceLocation(
                            start_char=actual_start,
                            end_char=actual_end,
                            text_snippet=actual_snippet[:200],
                            verified=True,
                        )
                    ],
                    confidence=change.get("confidence", "confirmed"),
                    extraction_rationale=change.get("rationale", ""),
                )
                operation_evidence.append(op_evidence)

            except ValueError as e:
                issues.append(f"Change {i}: Cannot construct operation: {e}")
            except Exception as e:
                issues.append(f"Change {i}: Unexpected error: {e}")

        return operations, operation_evidence, issues

    def _create_failed_result(
        self, prose_hash: str, issues: list[str]
    ) -> NarrativeDeltaExtractionResult:
        """Create failed extraction result."""
        return NarrativeDeltaExtractionResult(
            status=ExtractionStatus.FAILED,
            delta=None,
            prose_hash=prose_hash,
            operation_evidence=[],
            diagnostics=ExtractionDiagnostic(
                coverage_percentage=0.0,
                required_transitions_found=0,
                required_transitions_missing=0,
                unexpected_changes_found=0,
                conflicting_evidence_count=0,
                uncertain_extractions=[],
                issues=issues,
            ),
            extraction_method="llm_structured",
            extracted_at=datetime.now(),
            issues=issues,
        )
