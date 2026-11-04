"""Minimal Chapter Workflow for V2-020.

Connects ChapterContract → ContextArtifact → ModelGateway → Draft text.
First implementation focuses on generating readable novel chapters.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..context.compiler import ContextCompiler
from ..contracts.models import ChapterContract
from ..domain.delta import CanonState
from ..domain.identity import ProjectId
from ..gateway import ModelGateway


@dataclass
class ChapterDraft:
    """Draft chapter output before formal validation."""

    chapter_id: str
    chapter_number: int
    title: str
    content: str  # Full Chinese novel text
    word_count: int
    model_used: str
    generation_cost_usd: float
    created_at: datetime
    contract_id: str
    context_artifact_id: str


class ChapterWorkflow:
    """Minimal workflow to generate chapter drafts."""

    def __init__(
        self,
        context_compiler: ContextCompiler,
        model_gateway: ModelGateway,
        output_dir: Path,
    ):
        """Initialize workflow.

        Args:
            context_compiler: Context compiler for building prompts
            model_gateway: Model gateway for text generation
            output_dir: Directory to save draft chapters
        """
        self.context_compiler = context_compiler
        self.model_gateway = model_gateway
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _build_writer_prompt(self, context_artifact) -> tuple[str, str]:
        """Build Writer prompt from ContextArtifact.

        Returns:
            (system_prompt, user_prompt) tuple
        """
        # System prompt defines the Writer's role
        system_prompt = """你是一位专业的中文网络小说作家。

你的任务是根据章节合约（ChapterContract）和上下文信息，创作引人入胜的小说章节。

创作要求：
1. 文字流畅自然，有感染力
2. 人物有明确动机和行动
3. 冲突真实可信，推动情节发展
4. 场景描写生动，细节丰富
5. 对话符合人物性格
6. 章节结尾留下悬念或推进

严格遵守：
- 合约规定的必需事实转移
- 角色知识边界（不能让角色知道他们不该知道的信息）
- 题材规则和世界设定
- 前章接续点

输出格式：
# 章节标题

正文内容...

（不要输出任何元数据、说明或分析，只输出小说正文）"""

        # User prompt provides the specific context
        user_prompt = "# 章节合约与上下文\n\n"

        # Add mandatory context items
        user_prompt += "## 必需约束\n\n"
        for item in context_artifact.mandatory_items:
            user_prompt += f"### {item.source_type}\n"
            user_prompt += (
                f"{json.dumps(item.content, ensure_ascii=False, indent=2)}\n\n"
            )

        # Add optional context items
        if context_artifact.optional_items:
            user_prompt += "## 参考信息\n\n"
            for item in context_artifact.optional_items[:3]:  # Limit optional items
                user_prompt += f"### {item.source_type}\n"
                user_prompt += (
                    f"{json.dumps(item.content, ensure_ascii=False, indent=2)}\n\n"
                )

        user_prompt += "\n请创作本章内容："

        return system_prompt, user_prompt

    def generate_chapter_draft(
        self,
        chapter_contract: ChapterContract,
        canon_state: CanonState,
        project_id: ProjectId,
        model_id: str = "claude-sonnet-4",
        max_tokens: int = 8000,
    ) -> ChapterDraft:
        """Generate a chapter draft.

        Args:
            chapter_contract: Chapter contract with requirements
            canon_state: Canon state at contract.canon_parent
            project_id: Project ID
            model_id: Model to use for generation
            max_tokens: Maximum output tokens

        Returns:
            ChapterDraft with generated content
        """
        # Step 1: Compile context
        print(f"Compiling context for chapter {chapter_contract.chapter_number}...")
        context_result = self.context_compiler.compile_context(
            chapter_contract=chapter_contract,
            canon_state=canon_state,
            project_id=project_id,
            token_budget=32000,
            output_reserve=max_tokens,
        )

        if hasattr(context_result, "error_type"):
            raise RuntimeError(
                f"Context compilation failed: {context_result.error_type}"
            )

        context_artifact = context_result

        # Step 2: Build Writer prompt
        print("Building Writer prompt...")
        system_prompt, user_prompt = self._build_writer_prompt(context_artifact)

        # Step 3: Call model
        print(f"Generating chapter content with {model_id}...")
        response = self.model_gateway.generate(
            model_id=model_id,
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=1.0,
            max_tokens=max_tokens,
            context_metadata={
                "chapter_id": chapter_contract.chapter_id,
                "chapter_number": chapter_contract.chapter_number,
                "contract_id": chapter_contract.contract_id,
            },
        )

        if response.result_status.value != "success":
            raise RuntimeError(
                f"Model generation failed: {response.result_status.value}"
            )

        # Step 4: Extract title and content
        content = response.response_text or ""
        lines = content.strip().split("\n")
        title = "未命名章节"
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip()
            content = "\n".join(lines[1:]).strip()

        # Step 5: Create draft
        draft = ChapterDraft(
            chapter_id=chapter_contract.chapter_id,
            chapter_number=chapter_contract.chapter_number,
            title=title,
            content=content,
            word_count=len(content),
            model_used=model_id,
            generation_cost_usd=response.total_cost_usd,
            created_at=datetime.now(),
            contract_id=chapter_contract.contract_id,
            context_artifact_id=context_artifact.artifact_id,
        )

        # Step 6: Save to file
        self._save_draft(draft)

        return draft

    def _save_draft(self, draft: ChapterDraft) -> None:
        """Save draft to markdown file."""
        filename = f"chapter_{draft.chapter_number:03d}_{draft.chapter_id}.md"
        filepath = self.output_dir / filename

        content = f"""# {draft.title}

**章节**: 第 {draft.chapter_number} 章
**生成时间**: {draft.created_at.isoformat()}
**模型**: {draft.model_used}
**字数**: {draft.word_count}
**成本**: ${draft.generation_cost_usd:.4f}

---

{draft.content}

---

**元数据**:
- Contract ID: {draft.contract_id}
- Context Artifact ID: {draft.context_artifact_id}
- Chapter ID: {draft.chapter_id}
"""

        filepath.write_text(content, encoding="utf-8")
        print(f"Draft saved to: {filepath}")
