"""DailyReportAgent - 일일 통합 리포트 생성."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.github_method import GitHubMethodOutput
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import DailySkimOutput, SkimSummary
from rtc.storage.code_store import CodeStore
from rtc.storage.deep_store import DeepStore
from rtc.storage.report_store import ReportStore
from rtc.storage.skim_store import SkimStore
from rtc.trend import aggregate_trends, render_trend_section


def _is_iso_date(value: str) -> bool:
    """True for a plain YYYY-MM-DD stem, so stray yaml files cannot join a window."""
    if len(value) != 10:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


@dataclass
class PaperReportData:
    """개별 논문 리포트 데이터."""

    slug: str
    arxiv_id: str
    title: str
    skim: Optional[SkimSummary] = None
    extraction: Optional[ExtractionOutput] = None
    delta: Optional[DeltaOutput] = None
    scoring: Optional[ScoringOutput] = None
    github_method: Optional[GitHubMethodOutput] = None


@dataclass
class DailyReportInput:
    """DailyReportAgent 입력."""

    run_date: str  # YYYY-MM-DD
    deep_completed: list[str]  # arxiv_ids
    all_papers: list[SkimSummary]  # 모든 스킴 결과


@dataclass
class DailyReportOutput:
    """DailyReportAgent 출력."""

    run_date: str
    report_path: str
    total_papers: int
    papers_with_github: int


class DailyReportAgent(BaseAgent[DailyReportInput, DailyReportOutput]):
    """일일 통합 리포트 생성 에이전트.

    Deep 분석 결과 + GitHub 분석 결과를 통합하여
    단일 마크다운 파일로 출력합니다.
    """

    name = "daily_report"
    uses_llm = False

    def __init__(self):
        self.settings = get_settings()
        self.deep_store = DeepStore(self.settings.base_dir, reports_dir=self.settings.reports_dir)
        self.code_store = CodeStore(self.settings.base_dir, reports_dir=self.settings.reports_dir)
        self.report_store = ReportStore(self.settings.base_dir, reports_dir=self.settings.reports_dir)

    async def run(self, input: DailyReportInput) -> DailyReportOutput:
        """일일 리포트 생성.

        Args:
            input: 입력 데이터

        Returns:
            출력 데이터
        """
        papers_data: list[PaperReportData] = []

        # 중복 제거
        seen_ids: set[str] = set()
        unique_completed = []
        for aid in input.deep_completed:
            if aid not in seen_ids:
                seen_ids.add(aid)
                unique_completed.append(aid)

        # 각 논문 데이터 수집
        for arxiv_id in unique_completed:
            skim = self._find_skim(arxiv_id, input.all_papers)
            if not skim:
                continue

            slug = self._get_paper_slug(arxiv_id, skim.title)

            paper_data = PaperReportData(
                slug=slug,
                arxiv_id=arxiv_id,
                title=skim.title,
                skim=skim,
                extraction=self.deep_store.load_extraction(slug),
                delta=self.deep_store.load_delta(slug),
                scoring=self.deep_store.load_scoring(slug),
                github_method=self.code_store.load_github_method(slug),
            )
            papers_data.append(paper_data)

        # 점수순 정렬
        papers_data.sort(
            key=lambda p: p.scoring.total if p.scoring else 0,
            reverse=True,
        )

        # 스킴만 통과한 나머지 논문 추출
        deep_ids = set(input.deep_completed)
        skim_only = [
            p for p in input.all_papers
            if p.arxiv_id not in deep_ids
            and p.interest_score >= 4
            and p.category in {"agent", "rag", "reasoning"}
        ]

        # 트렌드 브리핑 (토글 off면 이 경로 자체를 타지 않음)
        trend_md = (
            self._build_trend_section()
            if self.settings.trend_section_enabled
            else None
        )

        # 마크다운 생성
        markdown = self._generate_markdown(
            input.run_date, papers_data, skim_only, trend_md
        )

        # 저장
        report_path = self.report_store.save_daily_report(input.run_date, markdown)

        return DailyReportOutput(
            run_date=input.run_date,
            report_path=str(report_path),
            total_papers=len(papers_data),
            papers_with_github=sum(1 for p in papers_data if p.github_method),
        )

    def _find_skim(
        self, arxiv_id: str, papers: list[SkimSummary]
    ) -> Optional[SkimSummary]:
        """arxiv_id로 스킴 결과 찾기."""
        for paper in papers:
            if paper.arxiv_id == arxiv_id:
                return paper
        return None

    def _get_paper_slug(self, arxiv_id: str, title: str) -> str:
        """논문 슬러그 생성."""
        from rtc.storage.deep_store import create_paper_slug

        return create_paper_slug(arxiv_id, title)

    def _build_trend_section(self) -> Optional[str]:
        """Aggregate the recent skim window and render it, or None.

        The SkimStore is built here rather than in __init__ because its
        constructor creates the papers directory; with the toggle off nothing
        about the trend path should run at all. Any failure degrades to no
        section - a trend bug must never take the daily report down with it.
        """
        try:
            window, previous = self._load_trend_window()
            if not window:
                return None

            summary = aggregate_trends(
                window,
                previous,
                self._resolve_trend_vocab(window),
                top_tags=self.settings.trend_top_tags,
                min_count=self.settings.trend_min_count,
            )
            return render_trend_section(summary) or None
        except Exception as e:  # noqa: BLE001 - report generation must survive
            print(f"  [Warn] Trend section skipped: {e}")
            return None

    def _load_trend_window(self) -> tuple[list[DailySkimOutput], list[DailySkimOutput]]:
        """Load the most recent N stored skim files, plus the N before them.

        The window is defined by files that exist, not by the calendar, so gaps
        in the schedule shrink the window instead of emptying it.
        """
        store = SkimStore(self.settings.base_dir, papers_dir=self.settings.papers_dir)
        dates = [d for d in store.list_dates() if _is_iso_date(d)]

        size = max(self.settings.trend_window_days, 0)
        if not size:
            return [], []

        window = self._load_dates(store, dates[:size])
        previous = self._load_dates(store, dates[size : size * 2])
        return window, previous

    @staticmethod
    def _load_dates(store: SkimStore, dates: list[str]) -> list[DailySkimOutput]:
        """Load each date, skipping anything that no longer parses."""
        loaded = []
        for date in dates:
            try:
                output = store.load(date)
            except Exception:  # noqa: BLE001 - a broken file must not sink the window
                continue
            if output is not None:
                loaded.append(output)
        return loaded

    def _resolve_trend_vocab(self, window: list[DailySkimOutput]) -> list[str]:
        """Resolve the vocabulary that decides what counts as an outside signal.

        Stored snapshots win. Files written before the snapshot field existed
        carry none, so fall back to the currently configured vocabulary.
        """
        snapshot = {kw for out in window for kw in (out.effective_keywords or [])}
        if snapshot:
            return sorted(snapshot)
        return self.settings.get_effective_hf_keywords()

    def _generate_markdown(
        self,
        run_date: str,
        papers: list[PaperReportData],
        skim_only: list[SkimSummary] | None = None,
        trend_md: str | None = None,
    ) -> str:
        """마크다운 리포트 생성.

        목적: 논문을 깊이 리뷰하는 것이 아니라,
        최근 연구 트렌드가 어떤 방향으로 가고 있는지를 감지하기 위한 데일리 리포트입니다.
        """
        lines = [
            f"# {run_date} Daily Paper Report",
            "",
            "> 이 리포트는 논문을 상세히 분석하기 위한 것이 아니라,",
            "> 최근 연구 흐름을 빠르게 파악하기 위한 데일리 요약입니다.",
            "",
        ]

        # 트렌드 브리핑은 헤더 바로 아래, 논문 섹션 위
        if trend_md:
            lines.append(trend_md)

        lines.extend([
            f"## 📚 오늘의 논문 ({len(papers)}편)",
            "",
            "---",
            "",
        ])

        for i, paper in enumerate(papers, 1):
            lines.extend(self._render_paper(i, paper))
            lines.append("")

        # 스킴 요약 섹션
        if skim_only:
            lines.extend(self._render_skim_summary_section(skim_only))

        # 푸터
        lines.extend([
            "---",
            "",
            f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        return "\n".join(lines)

    def _render_skim_summary_section(self, papers: list[SkimSummary]) -> list[str]:
        """스킴만 통과한 논문을 테이블 형식으로 렌더링."""
        lines = [
            "---",
            "",
            f"## 📋 기타 주목할 논문",
            "",
            "| # | 논문 | 키워드 | 카테고리 | 한줄 요약 |",
            "|---|------|--------|----------|-----------|",
        ]

        for i, paper in enumerate(papers, 1):
            keywords = ", ".join(f"`{kw}`" for kw in paper.matched_keywords) if paper.matched_keywords else ""
            title_link = f"[{paper.title}]({paper.link})"
            lines.append(f"| {i} | {title_link} | {keywords} | {paper.category} | {paper.one_liner} |")

        lines.append("")
        return lines

    def _render_paper(self, index: int, paper: PaperReportData) -> list[str]:
        """개별 논문 렌더링 (상세 버전)."""
        lines = []

        # 1. 헤더 + 링크
        stars = self._get_stars(paper.scoring)
        github_badge = "[GitHub ✓]" if paper.github_method else ""
        lines.append(f"### {index}. {paper.title} {stars} {github_badge}".strip())
        lines.append("")

        # 링크
        if paper.skim:
            lines.append(f"**arXiv**: [{paper.arxiv_id}]({paper.skim.link})")
            pdf_url = f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"
            lines.append(f"**PDF**: [다운로드]({pdf_url})")
            if paper.skim.github_url:
                lines.append(f"**GitHub**: [{paper.skim.github_url}]({paper.skim.github_url})")
            if paper.skim.matched_keywords:
                lines.append(f"**매칭 키워드**: {', '.join(paper.skim.matched_keywords)}")
            lines.append("")

        # 2. 왜 이 논문인가? (점수 상세 + 평가 근거 + 주요 강점)
        lines.extend(self._render_scoring_section(paper.scoring))

        # 3. 한 줄 요약
        if paper.delta:
            lines.append("## 한 줄 요약")
            lines.append(paper.delta.one_line_takeaway)
            lines.append("")

        # 4. 문제 정의 (상세)
        if paper.extraction and paper.extraction.problem_definition:
            problem = paper.extraction.problem_definition
            lines.append("## 문제 정의")
            lines.append(problem.statement)
            lines.append("")
            if problem.structural_limitation:
                lines.append(f"**기존 방법의 한계**: {problem.structural_limitation}")
                lines.append("")

        # 5. 핵심 기여
        if paper.extraction:
            lines.extend(self._render_contribution_section(paper.extraction))

        # 6. 방법론 (구성요소별)
        lines.extend(self._render_methodology_section(paper.extraction))

        # 7. 차별점 (Delta) - 상세
        lines.extend(self._render_delta_section(paper.delta, paper.extraction))

        # 8. 트레이드오프
        lines.extend(self._render_tradeoffs_section(paper.delta))

        # 9. 언제 사용해야 하는가?
        if paper.delta:
            lines.append("## 언제 사용해야 하는가?")
            lines.append(f"✅ **사용 권장**: {paper.delta.when_to_use}")
            lines.append(f"❌ **사용 비권장**: {paper.delta.when_not_to_use}")
            lines.append("")

        # 10. 주요 클레임 (유형별 그룹)
        lines.extend(self._render_claims_section(paper.extraction))

        # 11. GitHub 구현 (있으면)
        if paper.github_method:
            lines.extend(self._render_github_section(paper.github_method))

        lines.append("---")
        return lines

    def _render_scoring_section(self, scoring: Optional[ScoringOutput]) -> list[str]:
        """점수 섹션 상세 렌더링."""
        lines = []
        if not scoring:
            return lines

        lines.append("## 왜 이 논문인가?")
        lines.append(f"총점: {scoring.total}/15")
        lines.append("")

        lines.append("🎯 점수 상세:")
        lines.append(f"  - 실용성 (Practicality): {scoring.practicality}/5")
        lines.append(f"  - 구현 가능성 (Codeability): {scoring.codeability}/5")
        lines.append(f"  - 신뢰도 (Signal): {scoring.signal}/5")
        lines.append("")

        lines.append("💡 평가 근거:")
        lines.append(scoring.reasoning)
        lines.append("")

        lines.append(f"**주요 강점**: {scoring.key_strength}")
        if scoring.main_concern:
            lines.append(f"**주요 우려**: {scoring.main_concern}")
        lines.append("")

        return lines

    def _render_contribution_section(self, extraction: Optional[ExtractionOutput]) -> list[str]:
        """핵심 기여 섹션 렌더링."""
        lines = []
        if not extraction:
            return lines

        # 핵심 기여는 method claims에서 추출
        method_claims = [c for c in extraction.claims if c.claim_type == "method"]
        if method_claims:
            lines.append("## 핵심 기여")
            for claim in method_claims[:3]:  # 최대 3개
                lines.append(f"- {claim.text}")
            lines.append("")

        return lines

    def _render_methodology_section(self, extraction: Optional[ExtractionOutput]) -> list[str]:
        """방법론 섹션 렌더링."""
        lines = []
        if not extraction or not extraction.method_components:
            return lines

        lines.append("## 방법론")
        for component in extraction.method_components:
            lines.append(f"### {component.name}")
            lines.append(component.description)

            if component.inputs:
                lines.append(f"- **입력**: {', '.join(component.inputs)}")
            if component.outputs:
                lines.append(f"- **출력**: {', '.join(component.outputs)}")
            if component.implementation_hint:
                lines.append(f"- **구현 힌트**: {component.implementation_hint}")
            lines.append("")

        return lines

    def _render_delta_section(
        self, delta: Optional[DeltaOutput], extraction: Optional[ExtractionOutput]
    ) -> list[str]:
        """Delta 섹션 상세 렌더링."""
        lines = []
        if not delta:
            return lines

        lines.append("## 차별점 (Delta)")
        lines.append("")

        # 기존 방법 (extraction에서 가져옴)
        if extraction and extraction.baselines:
            main_baseline = extraction.baselines[0]
            lines.append(f"### 기존 방법: {main_baseline.name}")
            lines.append(main_baseline.limitation)
            lines.append("")

        # 혁신점
        lines.append("### 혁신점")
        for d in delta.core_deltas:
            lines.append(f"- **{d.axis}**: {d.why_better}")
        lines.append("")

        # 핵심 혁신 (기존→변경 형식)
        lines.append("**핵심 혁신:**")
        for d in delta.core_deltas:
            lines.append(f"- [기존: {d.old_approach}] → [변경: {d.new_approach}]")
        lines.append("")

        return lines

    def _render_tradeoffs_section(self, delta: Optional[DeltaOutput]) -> list[str]:
        """트레이드오프 섹션 렌더링."""
        lines = []
        if not delta or not delta.tradeoffs:
            return lines

        lines.append("## 트레이드오프")
        for tradeoff in delta.tradeoffs:
            lines.append(f"- **{tradeoff.aspect}**: {tradeoff.benefit} vs {tradeoff.cost}")
        lines.append("")

        return lines

    def _render_claims_section(self, extraction: Optional[ExtractionOutput]) -> list[str]:
        """클레임 섹션 렌더링 (유형별 그룹화)."""
        lines = []
        if not extraction or not extraction.claims:
            return lines

        lines.append("## 주요 클레임")

        # 유형별 그룹화
        claim_types = {
            "method": "방법론 클레임",
            "result": "결과 클레임",
            "comparison": "비교 클레임",
            "limitation": "한계 클레임",
        }

        for claim_type, label in claim_types.items():
            type_claims = [c for c in extraction.claims if c.claim_type == claim_type]
            if type_claims:
                lines.append(f"### {label}")
                for claim in type_claims:
                    lines.append(f"- {claim.text}")
                lines.append("")

        return lines

    def _render_github_section(self, github: GitHubMethodOutput) -> list[str]:
        """GitHub 섹션 렌더링 - 논문 방법론과 코드 매핑 강조."""
        lines = [
            "## 💻 GitHub 구현 분석",
            "",
        ]

        # 프로젝트 개요
        if github.structure_summary:
            lines.append("### 프로젝트 구조")
            lines.append(github.structure_summary)
            lines.append("")

        # 핵심 구현 (core 타입만 먼저, 최대 5개)
        core_methods = [
            m for m in github.methods
            if getattr(m, "implementation_type", "core") == "core"
            and getattr(m, "has_actual_logic", True)
        ]
        other_methods = [m for m in github.methods if m not in core_methods]

        if core_methods:
            lines.append("### 핵심 알고리즘 구현")
            lines.append("")

            for method in core_methods[:5]:
                lines.extend(self._render_method_implementation(method))

        # 보조 구현 (있으면)
        if other_methods and len(core_methods) < 3:
            lines.append("### 보조 구현")
            lines.append("")
            for method in other_methods[:2]:
                lines.extend(self._render_method_implementation(method, compact=True))

        # 매핑 못 한 방법론
        if github.unmapped_methods:
            lines.append("### ⚠️ 구현을 찾지 못한 방법론")
            for unmapped in github.unmapped_methods:
                lines.append(f"- {unmapped}")
            lines.append("")

        # 사용법
        if github.installation or github.usage_example:
            lines.append("### 사용 방법")
            if github.installation:
                lines.append("**설치**:")
                lines.append("```bash")
                lines.append(github.installation)
                lines.append("```")
                lines.append("")

            if github.usage_example:
                lines.append("**실행 예시**:")
                lines.append("```python")
                lines.append(github.usage_example)
                lines.append("```")
                lines.append("")

        return lines

    def _render_method_implementation(
        self, method, compact: bool = False
    ) -> list[str]:
        """개별 방법론 구현 렌더링."""
        lines = []

        # 헤더: 방법론 이름 + 논문 섹션
        paper_ref = ""
        if hasattr(method, "paper_section") and method.paper_section:
            paper_ref = f" (📄 {method.paper_section})"
        if hasattr(method, "paper_formula") and method.paper_formula:
            paper_ref += f" - {method.paper_formula}"

        lines.append(f"#### {method.method_name}{paper_ref}")
        lines.append("")

        # 위치 정보
        location = f"`{method.file_path}`"
        if method.class_or_function:
            location += f" → `{method.class_or_function}`"
        if method.line_start:
            location += f" (L{method.line_start}"
            if method.line_end:
                location += f"-{method.line_end}"
            location += ")"
        lines.append(f"**위치**: {location}")
        lines.append("")

        # 코드 설명 (한국어)
        if method.code_explanation:
            lines.append(f"**동작 원리**: {method.code_explanation}")
            lines.append("")

        # 핵심 코드
        if not compact:
            max_lines = 30
        else:
            max_lines = 15

        lines.append("**핵심 코드**:")
        lines.append("```python")
        code_lines = method.key_code.split("\n")
        lines.extend(code_lines[:max_lines])
        if len(code_lines) > max_lines:
            lines.append(f"# ... ({len(code_lines) - max_lines}줄 더)")
        lines.append("```")
        lines.append("")

        # 의존성 (있으면)
        if method.dependencies:
            lines.append(f"**사용 라이브러리**: {', '.join(method.dependencies)}")
            lines.append("")

        return lines

    def _get_stars(self, scoring: Optional[ScoringOutput]) -> str:
        """점수에 따른 별표 생성."""
        if not scoring:
            return ""

        total = scoring.total
        if total >= 13:
            return "⭐⭐⭐⭐⭐"
        elif total >= 11:
            return "⭐⭐⭐⭐"
        elif total >= 9:
            return "⭐⭐⭐"
        elif total >= 7:
            return "⭐⭐"
        else:
            return "⭐"


async def generate_daily_report(
    run_date: str,
    deep_completed: list[str],
    all_papers: list[SkimSummary],
) -> DailyReportOutput:
    """일일 리포트 생성 헬퍼.

    Args:
        run_date: 실행 날짜 (YYYY-MM-DD)
        deep_completed: Deep 분석 완료된 arxiv_ids
        all_papers: 모든 스킴 결과

    Returns:
        리포트 출력
    """
    agent = DailyReportAgent()
    return await agent.run(
        DailyReportInput(
            run_date=run_date,
            deep_completed=deep_completed,
            all_papers=all_papers,
        )
    )
