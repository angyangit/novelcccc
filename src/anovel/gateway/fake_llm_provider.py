"""Fake Provider for LLM Extractor offline testing.

Returns pre-defined structured extraction results without real API calls.
"""

from typing import Any


class FakeLLMProvider:
    """Fake LLM provider that returns structured extraction JSON.

    For offline testing of LLM extraction pipeline without paid calls.
    """

    def __init__(self, extraction_scenario: str = "urban_funding"):
        """Initialize fake provider.

        Args:
            extraction_scenario: Predefined scenario to return
                - "urban_funding": Urban business funding extraction
                - "fantasy_breakthrough": Fantasy cultivation breakthrough
                - "contradictory": Contradictory evidence
                - "negation": Negation and conditional statements
                - "empty": No state changes detected
        """
        self.extraction_scenario = extraction_scenario
        self.call_count = 0

    def generate(self, prompt: str, max_tokens: int, **kwargs) -> dict[str, Any]:
        """Generate fake structured extraction response."""
        self.call_count += 1

        # Return pre-defined extraction based on scenario
        if self.extraction_scenario == "urban_funding":
            return self._urban_funding_response()
        elif self.extraction_scenario == "fantasy_breakthrough":
            return self._fantasy_breakthrough_response()
        elif self.extraction_scenario == "contradictory":
            return self._contradictory_response()
        elif self.extraction_scenario == "negation":
            return self._negation_response()
        elif self.extraction_scenario == "empty":
            return self._empty_response()
        else:
            return self._urban_funding_response()

    def _urban_funding_response(self) -> dict[str, Any]:
        """Urban business funding extraction."""
        extraction_json = """
{
  "state_changes": [
    {
      "fact_path": "funding_amount",
      "value": 5000000,
      "evidence_text": "公司账户收到了10,000,000美元",
      "evidence_start": 95,
      "evidence_end": 115,
      "confidence": "confirmed",
      "rationale": "明确描述资金到账金额"
    },
    {
      "fact_path": "funding_round",
      "value": "Series A",
      "evidence_text": "funding_round标记为\\"Series A\\"完成",
      "evidence_start": 120,
      "evidence_end": 145,
      "confidence": "confirmed",
      "rationale": "明确标记融资轮次"
    }
  ],
  "beliefs": [],
  "rumors": [],
  "plans": [],
  "negations": [],
  "diagnostics": {
    "total_sentences": 5,
    "state_changes_found": 2,
    "uncertain_statements": 0,
    "contradictions": 0
  }
}
"""
        return {
            "prose": extraction_json,
            "input_tokens": 500,
            "output_tokens": 250,
            "model": "fake-extractor-v1",
            "finished": True,
        }

    def _fantasy_breakthrough_response(self) -> dict[str, Any]:
        """Fantasy cultivation breakthrough extraction."""
        extraction_json = """
{
  "state_changes": [
    {
      "fact_path": "protagonist.realm",
      "value": "筑基",
      "evidence_text": "protagonist.realm已从\\"凝气\\"变为\\"筑基\\"",
      "evidence_start": 145,
      "evidence_end": 175,
      "confidence": "confirmed",
      "rationale": "明确描述境界突破"
    },
    {
      "fact_path": "protagonist.cultivation_level",
      "value": 9500,
      "evidence_text": "protagonist.cultivation_level飙升至9500",
      "evidence_start": 180,
      "evidence_end": 210,
      "confidence": "confirmed",
      "rationale": "明确数值变化"
    }
  ],
  "beliefs": [],
  "rumors": [],
  "plans": [],
  "negations": [],
  "diagnostics": {
    "total_sentences": 6,
    "state_changes_found": 2,
    "uncertain_statements": 0,
    "contradictions": 0
  }
}
"""
        return {
            "prose": extraction_json,
            "input_tokens": 600,
            "output_tokens": 280,
            "model": "fake-extractor-v1",
            "finished": True,
        }

    def _contradictory_response(self) -> dict[str, Any]:
        """Contradictory evidence extraction."""
        extraction_json = """
{
  "state_changes": [],
  "beliefs": [
    {
      "subject": "protagonist",
      "belief": "age is 25",
      "evidence_text": "Sarah认为自己25岁",
      "evidence_start": 10,
      "evidence_end": 25,
      "confidence": "stated_belief"
    }
  ],
  "rumors": [
    {
      "rumor": "protagonist age is 28",
      "source": "colleague",
      "evidence_text": "同事说Sarah其实28岁",
      "evidence_start": 30,
      "evidence_end": 45,
      "confidence": "unverified_claim"
    }
  ],
  "plans": [],
  "negations": [],
  "diagnostics": {
    "total_sentences": 3,
    "state_changes_found": 0,
    "uncertain_statements": 2,
    "contradictions": 1
  }
}
"""
        return {
            "prose": extraction_json,
            "input_tokens": 400,
            "output_tokens": 200,
            "model": "fake-extractor-v1",
            "finished": True,
        }

    def _negation_response(self) -> dict[str, Any]:
        """Negation and conditional statements."""
        extraction_json = """
{
  "state_changes": [],
  "beliefs": [],
  "rumors": [],
  "plans": [
    {
      "subject": "protagonist",
      "planned_action": "pay supplier",
      "planned_value": 100000,
      "evidence_text": "计划支付供应商10万",
      "evidence_start": 15,
      "evidence_end": 30,
      "confidence": "stated_plan"
    }
  ],
  "negations": [
    {
      "negated_fact": "payment completed",
      "evidence_text": "但还没有实际支付",
      "evidence_start": 35,
      "evidence_end": 45,
      "rationale": "明确否定"
    }
  ],
  "diagnostics": {
    "total_sentences": 2,
    "state_changes_found": 0,
    "uncertain_statements": 1,
    "contradictions": 0
  }
}
"""
        return {
            "prose": extraction_json,
            "input_tokens": 350,
            "output_tokens": 180,
            "model": "fake-extractor-v1",
            "finished": True,
        }

    def _empty_response(self) -> dict[str, Any]:
        """No state changes detected."""
        extraction_json = """
{
  "state_changes": [],
  "beliefs": [],
  "rumors": [],
  "plans": [],
  "negations": [],
  "diagnostics": {
    "total_sentences": 3,
    "state_changes_found": 0,
    "uncertain_statements": 0,
    "contradictions": 0
  }
}
"""
        return {
            "prose": extraction_json,
            "input_tokens": 300,
            "output_tokens": 100,
            "model": "fake-extractor-v1",
            "finished": True,
        }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate fake cost (zero for fake provider)."""
        return 0.0
