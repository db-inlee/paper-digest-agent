"""ReportWriter Agent - 마크다운 리포트 생성 (LLM)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import SkimSummary


@dataclass
class ReportInput:
    """Report 입력."""

    skim: Optional[SkimSummary]
    extraction: ExtractionOutput
    delta: DeltaOutput
    scoring: ScoringOutput
    run_date: str


REPORT_TEMPLATE = """# {title}

**날짜**: {run_date}
**arXiv**: [{arxiv_id}](https://arxiv.org/abs/{arxiv_id})
**PDF**: [다운로드](https://arxiv.org/pdf/{arxiv_id}.pdf)
**점수**: {total_score}/15 ({recommendation})

## 한 줄 요약
{one_line_takeaway}

## 왜 이 논문인가?
총점: {total_score}/15

🎯 점수 상세:
  - Practicality (실용성): {practicality}/5
  - Codeability (구현 가능성): {codeability}/5
  - Signal (신뢰도): {signal}/5

💡 평가 근거:
{reasoning}

**주요 강점**: {key_strength}
{main_concern_section}

## 문제 정의
{problem_statement}

**기존 방법의 한계**: {structural_limitation}

## 핵심 기여 (Delta)
{deltas_section}

## 방법론
{method_section}

## 트레이드오프
{tradeoffs_section}

## 언제 사용해야 하는가?
✅ **사용 권장**: {when_to_use}

❌ **사용 비권장**: {when_not_to_use}

## 주요 클레임
{claims_section}

---
*Generated at {generated_at}*
"""


class ReportWriter(BaseAgent[ReportInput, str]):
    """마크다운 리포트 생성 에이전트."""

    name = "report_writer"
    uses_llm = False  # 템플릿 기반, LLM 사용 안 함

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: ReportInput) -> str:
        """리포트 생성.

        Args:
            input: 리포트 입력

        Returns:
            마크다운 리포트 문자열
        """
        extraction = input.extraction
        delta = input.delta
        scoring = input.scoring

        # 섹션 준비
        deltas_section = self._format_deltas(delta)
        method_section = self._format_methods(extraction)
        tradeoffs_section = self._format_tradeoffs(delta)
        claims_section = self._format_claims(extraction)
        main_concern_section = (
            f"\n**주요 우려**: {scoring.main_concern}"
            if scoring.main_concern
            else ""
        )

        # 템플릿 채우기
        report = REPORT_TEMPLATE.format(
            title=extraction.title,
            run_date=input.run_date,
            arxiv_id=extraction.arxiv_id,
            total_score=scoring.total,
            recommendation=self._translate_recommendation(scoring.recommendation),
            one_line_takeaway=delta.one_line_takeaway,
            practicality=scoring.practicality,
            codeability=scoring.codeability,
            signal=scoring.signal,
            reasoning=scoring.reasoning,
            key_strength=scoring.key_strength,
            main_concern_section=main_concern_section,
            problem_statement=extraction.problem_definition.statement,
            structural_limitation=extraction.problem_definition.structural_limitation,
            deltas_section=deltas_section,
            method_section=method_section,
            tradeoffs_section=tradeoffs_section,
            when_to_use=delta.when_to_use,
            when_not_to_use=delta.when_not_to_use,
            claims_section=claims_section,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        return report

    def _translate_recommendation(self, rec: str) -> str:
        """추천 등급 한글 번역."""
        translations = {
            "must_read": "필독",
            "worth_reading": "읽어볼 만함",
            "skip": "스킵 가능",
        }
        return translations.get(rec, rec)

    def _format_deltas(self, delta: DeltaOutput) -> str:
        """Delta 섹션 포맷팅."""
        lines = []
        for i, d in enumerate(delta.core_deltas, 1):
            evidence = d.evidence.to_pointer() if d.evidence else ""
            lines.append(
                f"### Delta {i}: {d.axis}\n"
                f"- **기존**: {d.old_approach}\n"
                f"- **변경**: {d.new_approach}\n"
                f"- **이유**: {d.why_better} {evidence}"
            )
        return "\n\n".join(lines) if lines else "Delta 정보 없음"

    def _format_methods(self, extraction: ExtractionOutput) -> str:
        """방법론 섹션 포맷팅."""
        if not extraction.method_components:
            return "방법론 구성 요소 정보 없음"

        lines = []
        for m in extraction.method_components:
            evidence = (
                m.evidence[0].to_pointer() if m.evidence else ""
            )
            inputs = ", ".join(m.inputs) if m.inputs else "N/A"
            outputs = ", ".join(m.outputs) if m.outputs else "N/A"

            entry = (
                f"**{m.name}**\n"
                f"{m.description}\n"
                f"- **입력**: {inputs}\n"
                f"- **출력**: {outputs}"
            )
            if m.implementation_hint:
                entry += f"\n- **구현 힌트**: {m.implementation_hint}"
            if m.role:
                entry += f"\n- **역할**: {m.role}"
            if evidence:
                entry += f" {evidence}"
            lines.append(entry)

        return "\n\n".join(lines)

    def _format_tradeoffs(self, delta: DeltaOutput) -> str:
        """트레이드오프 섹션 포맷팅."""
        if not delta.tradeoffs:
            return "명시된 트레이드오프 없음"

        lines = []
        for t in delta.tradeoffs:
            evidence = t.evidence.to_pointer() if t.evidence else ""
            lines.append(
                f"- **{t.aspect}**\n"
                f"  - 이점: {t.benefit}\n"
                f"  - 비용: {t.cost}"
            )
            if t.when_acceptable:
                lines[-1] += f"\n  - 수용 가능 조건: {t.when_acceptable}"
            if evidence:
                lines[-1] += f" {evidence}"

        return "\n".join(lines)

    def _format_claims(self, extraction: ExtractionOutput) -> str:
        """클레임 섹션 포맷팅."""
        if not extraction.claims:
            return "주요 클레임 없음"

        # 유형별 그룹화
        by_type = {}
        for c in extraction.claims:
            if c.claim_type not in by_type:
                by_type[c.claim_type] = []
            by_type[c.claim_type].append(c)

        type_labels = {
            "method": "방법론 클레임",
            "result": "결과 클레임",
            "comparison": "비교 클레임",
            "limitation": "한계 클레임",
        }

        lines = []
        for claim_type, claims in by_type.items():
            label = type_labels.get(claim_type, claim_type)
            lines.append(f"### {label}")
            for c in claims:
                evidence = c.evidence[0].to_pointer() if c.evidence else ""
                confidence = f"(신뢰도: {c.confidence:.0%})" if c.confidence < 1.0 else ""
                lines.append(f"- {c.text} {evidence} {confidence}".strip())

        return "\n".join(lines)
