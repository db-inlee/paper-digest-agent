"""A same-date rerun must not drop papers the earlier run already reported."""

import json
import re

import pytest
from rtc.agents.daily_report_agent import DailyReportAgent, DailyReportInput
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput
from rtc.schemas.extraction_v2 import (
    Evidence,
    ExtractionOutput,
    MethodComponent,
    ProblemDefinition,
)
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import DailySkimOutput, SkimSummary
from rtc.storage.deep_store import DeepStore, create_paper_slug
from rtc.storage.report_store import ReportStore
from rtc.storage.skim_store import SkimStore

DATE = "2026-08-21"
RUN1 = ["2608.00001", "2608.00002", "2608.00003"]
RUN2 = ["2608.00004", "2608.00005", "2608.00006"]

PAPER_HEADING = re.compile(r"^### (\d+)\. ", re.MULTILINE)


def summary(arxiv_id: str) -> SkimSummary:
    return SkimSummary(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        one_liner=f"한줄 {arxiv_id}",
        tags=["agent"],
        interest_score=4,
        interest_reason="reason",
        category="agent",
        link=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=["agent"],
    )


def extraction(arxiv_id: str) -> ExtractionOutput:
    return ExtractionOutput(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        problem_definition=ProblemDefinition(statement="문제", structural_limitation="한계"),
        method_components=[
            MethodComponent(name="C1", description="설명1"),
            MethodComponent(name="C2", description="설명2"),
        ],
        claims=[],
    )


def delta(arxiv_id: str) -> DeltaOutput:
    return DeltaOutput(
        arxiv_id=arxiv_id,
        one_line_takeaway="핵심",
        core_deltas=[
            CoreDelta(
                axis="설계",
                old_approach="기존",
                new_approach="신규",
                why_better="이유",
                evidence=Evidence(quote="근거 인용", type="quote"),
            )
        ],
        tradeoffs=[],
        when_to_use="쓸 때",
        when_not_to_use="안 쓸 때",
    )


def scoring(arxiv_id: str) -> ScoringOutput:
    return ScoringOutput(
        arxiv_id=arxiv_id,
        practicality=4,
        codeability=3,
        signal=4,
        recommendation="worth_reading",
        reasoning="근거",
        key_strength="강점",
    )


@pytest.fixture
def agent(tmp_path, monkeypatch):
    instance = DailyReportAgent()
    instance.report_store = ReportStore(tmp_path / "reports")
    monkeypatch.setattr(instance.settings, "papers_base_dir", tmp_path / "papers")
    monkeypatch.setattr(instance.settings, "trend_section_enabled", False)
    monkeypatch.setattr(instance.settings, "ranking_enabled", False)
    instance.deep_store = DeepStore(tmp_path, reports_dir=tmp_path / "reports")
    instance.code_store.reports_dir = tmp_path / "reports"
    return instance


def store_artifacts(agent, ids):
    """Write the deep artifacts a real run would have left behind."""
    for arxiv_id in ids:
        slug = create_paper_slug(arxiv_id, f"Paper {arxiv_id}")
        agent.deep_store.save_extraction(slug, extraction(arxiv_id))
        agent.deep_store.save_delta(slug, delta(arxiv_id))
        agent.deep_store.save_scoring(slug, scoring(arxiv_id))
        agent.deep_store.save_report(slug, "# deep")


def store_skim(agent, ids, deep_candidates):
    """Write papers/{date}.yaml the way SkimStore merges across runs."""
    store = SkimStore(agent.settings.base_dir, papers_dir=agent.settings.papers_dir)
    store.save(
        DailySkimOutput(
            date=DATE,
            total_collected=len(ids),
            total_skimmed=len(ids),
            papers=[summary(i) for i in ids],
            deep_candidates=list(deep_candidates),
        )
    )


def rendered_ids(markdown: str) -> list[str]:
    return re.findall(r"\*\*arXiv\*\*: \[(\d+\.\d+)\]", markdown)


# --- A1. rerun merge -------------------------------------------------------


@pytest.mark.asyncio
async def test_rerun_preserves_previous_papers(agent):
    """1회차 3편 + 2회차 3편 → 리포트에 6편 전부."""
    store_artifacts(agent, RUN1)
    store_skim(agent, RUN1, RUN1)
    await agent.run(DailyReportInput(DATE, RUN1, [summary(i) for i in RUN1]))
    first = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")
    assert len(rendered_ids(first)) == 3

    # 2회차: SkimStore 병합으로 deep_candidates가 합집합이 된다
    store_artifacts(agent, RUN2)
    store_skim(agent, RUN2, RUN2)
    await agent.run(DailyReportInput(DATE, RUN2, [summary(i) for i in RUN2]))
    second = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    assert rendered_ids(second) == RUN1 + RUN2
    assert [int(n) for n in PAPER_HEADING.findall(second)] == [1, 2, 3, 4, 5, 6]


@pytest.mark.asyncio
async def test_rerun_does_not_duplicate(agent):
    """같은 논문이 두 실행에 모두 있어도 한 번만 렌더된다."""
    store_artifacts(agent, RUN1)
    store_skim(agent, RUN1, RUN1)
    await agent.run(DailyReportInput(DATE, RUN1, [summary(i) for i in RUN1]))
    await agent.run(DailyReportInput(DATE, RUN1, [summary(i) for i in RUN1]))

    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")
    assert rendered_ids(markdown) == RUN1


@pytest.mark.asyncio
async def test_missing_artifact_is_skipped_not_fatal(agent):
    """선정됐으나 분석되지 않은 논문이 있어도 나머지는 렌더된다."""
    store_artifacts(agent, RUN1)
    store_skim(agent, RUN1 + ["2608.09999"], RUN1 + ["2608.09999"])

    await agent.run(DailyReportInput(DATE, [], []))
    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    assert rendered_ids(markdown) == RUN1
    assert "2608.09999" not in markdown.split("## 📋")[0]


@pytest.mark.asyncio
async def test_unloadable_artifact_does_not_break_the_report(agent):
    """스키마 제약을 어기는 레거시 산출물이 섞여도 리포트는 생성된다."""
    store_artifacts(agent, RUN1)
    # 레거시 재현: method_components 1개 (현행 스키마는 min_length=2)
    broken = create_paper_slug("2608.00002", "Paper 2608.00002")
    path = agent.deep_store.get_paper_dir(broken) / "extraction.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["method_components"] = data["method_components"][:1]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    store_skim(agent, RUN1, RUN1)

    await agent.run(DailyReportInput(DATE, RUN1, [summary(i) for i in RUN1]))
    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    assert rendered_ids(markdown) == ["2608.00001", "2608.00003"]


@pytest.mark.asyncio
async def test_missing_skim_yaml_falls_back_to_input(agent):
    """저장된 yaml이 없으면 이번 실행이 넘긴 목록으로 동작한다."""
    store_artifacts(agent, RUN1)  # yaml 없음

    await agent.run(DailyReportInput(DATE, RUN1, [summary(i) for i in RUN1]))
    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    assert rendered_ids(markdown) == RUN1


@pytest.mark.asyncio
async def test_slug_falls_back_to_arxiv_prefix_match(agent):
    """저장 당시 제목이 달라도 arxiv_id 접두로 디렉토리를 찾는다."""
    arxiv_id = "2608.00007"
    slug = create_paper_slug(arxiv_id, "A Completely Different Stored Title")
    agent.deep_store.save_extraction(slug, extraction(arxiv_id))
    agent.deep_store.save_delta(slug, delta(arxiv_id))
    agent.deep_store.save_scoring(slug, scoring(arxiv_id))
    agent.deep_store.save_report(slug, "# deep")
    store_skim(agent, [arxiv_id], [arxiv_id])

    await agent.run(DailyReportInput(DATE, [], []))
    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    assert rendered_ids(markdown) == [arxiv_id]


# --- C. parser guard -------------------------------------------------------


def test_merged_report_still_parses(agent, monkeypatch):
    """병합된 6편 리포트가 notifier 파서에서 6편으로 읽힌다."""
    parse_report = pytest.importorskip("toslack.converter").parse_report

    store_artifacts(agent, RUN1 + RUN2)
    store_skim(agent, RUN1 + RUN2, RUN1 + RUN2)

    import asyncio

    asyncio.run(agent.run(DailyReportInput(DATE, [], [])))
    markdown = agent.report_store.get_report_path(DATE).read_text(encoding="utf-8")

    papers, _ = parse_report(markdown)

    assert [p.arxiv_id for p in papers] == RUN1 + RUN2
    assert all(p.stars > 0 for p in papers)
    assert all(p.score == 11 for p in papers)
