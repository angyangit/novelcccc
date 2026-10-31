"""Fact path mapper for converting natural language state changes to typed fact paths.

Maps fixture state_changes text to structured NarrativeDelta fact paths with proper
OperationType semantics (SET_FACT, END_FACT, UNDO_FACT).

P0-B requirement: Replace placeholder "state.chapter_x.change_i" with real typed paths.
"""

import re
from typing import Optional
from dataclasses import dataclass

from ..domain.delta import OperationType


@dataclass
class MappedFact:
    """Result of mapping a state change to a typed fact path."""
    operation_type: OperationType
    fact_path: str
    target_value: str
    confidence: str  # "certain", "probable", "uncertain"
    diagnostic: Optional[str] = None


class FactPathMapper:
    """Maps natural language state changes to typed fact paths."""

    # Urban business patterns
    EQUITY_PATTERNS = [
        (r'股权.*?从.*?(\d+)%.*?至.*?(\d+)%', 'equity.{character}.percentage'),  # Range: from X% to Y%
        (r'股权.*?降至.*?(\d+)%', 'equity.{character}.percentage'),  # Drop to X%
        (r'股权.*?(\d+)%', 'equity.{character}.percentage'),  # Simple: equity is X%
        (r'持股.*?从.*?(\d+)%.*?至.*?(\d+)%', 'equity.{character}.percentage'),  # Range
        (r'持股.*?(\d+)%', 'equity.{character}.percentage'),
        (r'股权稀释', 'equity.{character}.percentage'),
    ]

    RESOURCE_PATTERNS = [
        (r'账户余额.*?从.*?(\d+)万.*?至.*?(\d+)万', 'resources.company.cash'),  # Range: from X to Y
        (r'账户余额.*?降至.*?(\d+)万', 'resources.company.cash'),  # Drop to X
        (r'账户余额.*?(\d+)万', 'resources.company.cash'),  # Simple: balance is X
        (r'资金.*?(\d+)万', 'resources.company.cash'),
        (r'获得.*?(\d+)万', 'resources.company.cash'),
        (r'融资.*?(\d+)万', 'resources.company.funding_received'),
    ]

    RELATIONSHIP_PATTERNS = [
        (r'(.*?)与(.*?)信任度', 'relationships.{char_a}.{char_b}.trust_level'),
        (r'(.*?)从(.*?)变为(.*)', 'relationships.{char_a}.{char_b}.status'),
    ]

    # Fantasy cultivation patterns
    CULTIVATION_PATTERNS = [
        (r'(.*?)修为.*?至(.*?)[层期]', 'cultivation.{character}.realm'),
        (r'道韵.*?(\d+)', 'cultivation.{character}.dao_comprehension'),
        (r'突破.*?期', 'cultivation.{character}.realm'),
        (r'筑基', 'cultivation.{character}.realm'),
    ]

    SPIRIT_RESOURCE_PATTERNS = [
        (r'灵石.*?(\d+)块', 'resources.{character}.spirit_stones'),
        (r'获得.*?丹', 'resources.{character}.pills'),
        (r'消耗.*?(\d+)块', 'resources.{character}.spirit_stones'),
    ]

    CONDITION_PATTERNS = [
        (r'(.*?)伤势', 'condition.{character}.injury_state'),
        (r'走火入魔', 'condition.{character}.cultivation_deviation'),
        (r'经脉受损', 'condition.{character}.meridian_damage'),
    ]

    def map_state_change(
        self,
        state_change: str,
        chapter_id: str,
        genre_pack_id: str,
    ) -> MappedFact:
        """
        Map natural language state change to typed fact path.

        Args:
            state_change: Natural language description
            chapter_id: Chapter identifier for fallback paths
            genre_pack_id: Genre pack to determine mapping rules

        Returns:
            MappedFact with typed path or diagnostic if uncertain
        """
        # Try urban business patterns
        if 'urban' in genre_pack_id or 'business' in genre_pack_id:
            result = self._try_urban_patterns(state_change, chapter_id)
            if result:
                return result

        # Try fantasy cultivation patterns
        if 'fantasy' in genre_pack_id or 'cultivation' in genre_pack_id:
            result = self._try_fantasy_patterns(state_change, chapter_id)
            if result:
                return result

        # Generic patterns (relationships, knowledge)
        result = self._try_generic_patterns(state_change, chapter_id)
        if result:
            return result

        # Fallback: uncertain mapping
        return MappedFact(
            operation_type=OperationType.SET_FACT,
            fact_path=f"state.{chapter_id}.untyped_change",
            target_value=state_change,
            confidence="uncertain",
            diagnostic=f"Could not map state change to typed fact path: '{state_change}'"
        )

    def _try_urban_patterns(self, state_change: str, chapter_id: str) -> Optional[MappedFact]:
        """Try urban business-specific patterns."""

        # Equity patterns
        for pattern, path_template in self.EQUITY_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                # Extract character name
                character = self._extract_character_name(state_change)
                fact_path = path_template.format(character=character or 'protagonist')

                operation_type = OperationType.SET_FACT
                if '失去' in state_change or '放弃' in state_change:
                    operation_type = OperationType.END_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="certain" if character else "probable"
                )

        # Resource patterns
        for pattern, path_template in self.RESOURCE_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                fact_path = path_template
                operation_type = OperationType.SET_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="certain"
                )

        # Relationship patterns
        for pattern, path_template in self.RELATIONSHIP_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                groups = match.groups()
                char_a = self._normalize_name(groups[0]) if len(groups) > 0 else 'char_a'
                char_b = self._normalize_name(groups[1]) if len(groups) > 1 else 'char_b'

                fact_path = path_template.format(char_a=char_a, char_b=char_b)
                operation_type = OperationType.SET_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="probable"
                )

        return None

    def _try_fantasy_patterns(self, state_change: str, chapter_id: str) -> Optional[MappedFact]:
        """Try fantasy cultivation-specific patterns."""

        # Cultivation patterns
        for pattern, path_template in self.CULTIVATION_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                character = self._extract_character_name(state_change)
                fact_path = path_template.format(character=character or 'protagonist')

                operation_type = OperationType.SET_FACT
                if '跌落' in state_change or '废除' in state_change:
                    operation_type = OperationType.END_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="certain" if character else "probable"
                )

        # Spirit resource patterns
        for pattern, path_template in self.SPIRIT_RESOURCE_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                character = self._extract_character_name(state_change)
                fact_path = path_template.format(character=character or 'protagonist')

                operation_type = OperationType.SET_FACT
                if '消耗' in state_change or '失去' in state_change:
                    operation_type = OperationType.END_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="certain" if character else "probable"
                )

        # Condition patterns
        for pattern, path_template in self.CONDITION_PATTERNS:
            match = re.search(pattern, state_change)
            if match:
                character = self._normalize_name(match.group(1)) if match.groups() else 'unknown'
                fact_path = path_template.format(character=character)

                operation_type = OperationType.SET_FACT
                if '恢复' in state_change or '治愈' in state_change:
                    operation_type = OperationType.END_FACT

                return MappedFact(
                    operation_type=operation_type,
                    fact_path=fact_path,
                    target_value=state_change,
                    confidence="probable"
                )

        return None

    def _try_generic_patterns(self, state_change: str, chapter_id: str) -> Optional[MappedFact]:
        """Try genre-agnostic patterns (knowledge, world state)."""

        # Knowledge acquisition
        if '了解' in state_change or '知道' in state_change or '发现' in state_change:
            character = self._extract_character_name(state_change) or 'protagonist'
            return MappedFact(
                operation_type=OperationType.SET_FACT,
                fact_path=f"knowledge.{character}.acquired",
                target_value=state_change,
                confidence="probable"
            )

        # World state changes (market, environment)
        if '市场' in state_change or '窗口期' in state_change:
            return MappedFact(
                operation_type=OperationType.SET_FACT,
                fact_path="world.market.state",
                target_value=state_change,
                confidence="probable"
            )

        # Generic resource acquisition (documents, agreements, items)
        if '获得' in state_change and ('协议' in state_change or '文件' in state_change or '资源' in state_change):
            return MappedFact(
                operation_type=OperationType.SET_FACT,
                fact_path="resources.acquired.documents",
                target_value=state_change,
                confidence="probable"
            )

        return None

    def _extract_character_name(self, text: str) -> Optional[str]:
        """Extract character name from state change text."""
        # Common Chinese names pattern (surname + 1-2 characters)
        names = re.findall(r'(张明|李华|王总|王林|柳梦|赵长老)', text)
        if names:
            return self._normalize_name(names[0])

        # Generic pattern for names
        names = re.findall(r'[张王李刘陈杨黄赵吴周][一-鿿]{1,2}', text)
        if names:
            return self._normalize_name(names[0])

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize character name for fact path."""
        # Convert to pinyin-like identifier
        name_map = {
            '张明': 'zhang_ming',
            '李华': 'li_hua',
            '王总': 'wang_zong',
            '王林': 'wang_lin',
            '柳梦': 'liu_meng',
            '赵长老': 'elder_zhao',
        }
        return name_map.get(name, name.lower().replace(' ', '_'))
