"""Skim Pipeline - 빠른 논문 스킴 파이프라인."""

from datetime import datetime
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langsmith.run_helpers import traceable

from rtc.agents.fetcher import CandidateFetcher, FetchInput
from rtc.agents.gatekeeper import Gatekeeper
from rtc.agents.skim import UltraSkimAgent
from rtc.config import get_settings
from rtc.schemas import PaperCandidate
from rtc.schemas.skim import BatchSkimResult, DailySkimOutput, SkimSummary
from rtc.storage.skim_store import SkimStore


def merge_errors(left: list[dict], right: list[dict]) -> list[dict]:
    """에러 리스트 병합."""
    return left + right


class SkimState(TypedDict, total=False):
    """Skim Pipeline 상태."""

    # 입력
    run_date: str  # YYYY-MM-DD

    # 중간 상태
    candidates: list[PaperCandidate]
    skim_result: Optional[BatchSkimResult]

    # 출력
    deep_candidates: list[str]
    all_papers: list[SkimSummary]
    daily_output: Optional[DailySkimOutput]

    # 통계
    total_collected: int
    total_after_filter: int
    total_skimmed: int

    # 에러
    errors: Annotated[list[dict], merge_errors]


async def fetch_node(state: SkimState) -> dict:
    """논문 수집 노드."""
    run_date = state.get("run_date", datetime.now().strftime("%Y-%m-%d"))

    fetcher = CandidateFetcher()

    try:
        result = await fetcher.run(FetchInput(run_date=run_date))

        return {
            "candidates": result.candidates,
            "total_collected": result.total_collected,
            "total_after_filter": result.total_after_filter,
        }
    except Exception as e:
        return {
            "candidates": [],
            "total_collected": 0,
            "total_after_filter": 0,
            "errors": [{"node": "fetch", "error": str(e)}],
        }


async def skim_node(state: SkimState) -> dict:
    """스킴 노드."""
    candidates = state.get("candidates", [])

    if not candidates:
        return {
            "skim_result": BatchSkimResult(papers=[], total_processed=0),
            "total_skimmed": 0,
        }

    settings = get_settings()
    skim_agent = UltraSkimAgent(batch_size=settings.skim_batch_size)

    try:
        result = await skim_agent.run(candidates)

        errors = []
        if result.errors:
            errors = [{"node": "skim", "error": err} for err in result.errors]

        return {
            "skim_result": result,
            "total_skimmed": result.total_processed,
            "errors": errors if errors else [],
        }
    except Exception as e:
        return {
            "skim_result": BatchSkimResult(papers=[], total_processed=0),
            "total_skimmed": 0,
            "errors": [{"node": "skim", "error": str(e)}],
        }


async def gate_node(state: SkimState) -> dict:
    """Gatekeeper 노드."""
    skim_result = state.get("skim_result")

    if skim_result is None:
        return {
            "deep_candidates": [],
            "all_papers": [],
        }

    settings = get_settings()
    gatekeeper = Gatekeeper(
        interest_threshold=settings.skim_interest_threshold,
        max_deep_papers=settings.max_deep_papers_per_day,
    )

    try:
        result = await gatekeeper.run(skim_result)

        return {
            "deep_candidates": result.deep_candidates,
            "all_papers": result.all_papers,
        }
    except Exception as e:
        return {
            "deep_candidates": [],
            "all_papers": skim_result.papers if skim_result else [],
            "errors": [{"node": "gate", "error": str(e)}],
        }


async def save_skim_node(state: SkimState) -> dict:
    """스킴 결과 저장 노드."""
    run_date = state.get("run_date", datetime.now().strftime("%Y-%m-%d"))
    all_papers = state.get("all_papers", [])
    deep_candidates = state.get("deep_candidates", [])
    total_collected = state.get("total_collected", 0)
    total_skimmed = state.get("total_skimmed", 0)

    # DailySkimOutput 생성
    daily_output = DailySkimOutput(
        date=run_date,
        total_collected=total_collected,
        total_skimmed=total_skimmed,
        papers=all_papers,
        deep_candidates=deep_candidates,
    )

    # 저장
    settings = get_settings()
    store = SkimStore(settings.base_dir)

    try:
        path = store.save(daily_output)
        return {
            "daily_output": daily_output,
        }
    except Exception as e:
        return {
            "daily_output": daily_output,
            "errors": [{"node": "save_skim", "error": str(e)}],
        }


def should_continue_after_fetch(state: SkimState) -> str:
    """fetch 후 계속 진행 여부."""
    candidates = state.get("candidates", [])
    if not candidates:
        return "end"
    return "skim"


def build_skim_pipeline() -> StateGraph:
    """Skim Pipeline 빌드.

    Returns:
        LangGraph StateGraph
    """
    graph = StateGraph(SkimState)

    # 노드 추가
    graph.add_node("fetch", fetch_node)
    graph.add_node("skim", skim_node)
    graph.add_node("gate", gate_node)
    graph.add_node("save_skim", save_skim_node)

    # 엔트리 포인트
    graph.set_entry_point("fetch")

    # 엣지 추가
    graph.add_conditional_edges(
        "fetch",
        should_continue_after_fetch,
        {
            "skim": "skim",
            "end": END,
        },
    )
    graph.add_edge("skim", "gate")
    graph.add_edge("gate", "save_skim")
    graph.add_edge("save_skim", END)

    return graph


def create_skim_pipeline():
    """Skim Pipeline 컴파일.

    Returns:
        컴파일된 LangGraph runnable
    """
    graph = build_skim_pipeline()
    return graph.compile()


@traceable(name="skim_pipeline", run_type="chain")
async def run_skim_pipeline(run_date: str | None = None) -> SkimState:
    """Skim Pipeline 실행.

    Args:
        run_date: 실행 날짜 (YYYY-MM-DD). None이면 오늘 날짜.

    Returns:
        최종 상태
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    pipeline = create_skim_pipeline()

    initial_state: SkimState = {
        "run_date": run_date,
        "candidates": [],
        "errors": [],
    }

    result = await pipeline.ainvoke(initial_state)
    return result


# CLI 지원
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run Skim Pipeline")
    parser.add_argument("--date", type=str, help="Run date (YYYY-MM-DD)")
    args = parser.parse_args()

    result = asyncio.run(run_skim_pipeline(args.date))

    print(f"\n=== Skim Pipeline Results ===")
    print(f"Date: {result.get('run_date')}")
    print(f"Total collected: {result.get('total_collected', 0)}")
    print(f"Total after filter: {result.get('total_after_filter', 0)}")
    print(f"Total skimmed: {result.get('total_skimmed', 0)}")
    print(f"Deep candidates: {result.get('deep_candidates', [])}")

    if result.get("errors"):
        print(f"\nErrors:")
        for err in result["errors"]:
            print(f"  - {err}")
