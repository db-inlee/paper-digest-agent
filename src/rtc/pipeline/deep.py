"""Deep Pipeline - 논문 심층 분석 파이프라인."""

import logging
from datetime import datetime
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langsmith.run_helpers import traceable

from rtc.agents.correction_agent import CorrectionAgent, CorrectionInput
from rtc.agents.delta_agent import DeltaAgent, DeltaInput
from rtc.agents.extraction import ExtractionAgent, ExtractionInput
from rtc.agents.report_writer import ReportInput, ReportWriter
from rtc.agents.scoring_agent import ScoringAgent, ScoringInput
from rtc.agents.verification_agent import VerificationAgent, VerificationInput
from rtc.config import get_settings
from rtc.mcp.servers.grobid_server import GrobidServer
from rtc.mcp.servers.pymupdf_parser import PyMuPDFParser
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.parsed import ParsedPDF
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import SkimSummary
from rtc.schemas.verification_v1 import VerificationOutput
from rtc.storage.deep_store import DeepStore, create_paper_slug

logger = logging.getLogger(__name__)


def _build_corpus(settings):
    """LanceDB store + embedder를 구성. 실패 시 (None, None)을 반환(fail-soft)."""
    from rtc.corpus.embedder import get_embedder
    from rtc.corpus.vector_store import LanceDBVectorStore

    store = LanceDBVectorStore(settings.corpus_db_dir)
    embedder = get_embedder(settings.embedding_model)
    return store, embedder


def merge_errors(left: list[dict], right: list[dict]) -> list[dict]:
    """에러 리스트 병합."""
    return left + right


class DeepState(TypedDict, total=False):
    """Deep Pipeline 상태."""

    # 입력
    arxiv_id: str
    title: str
    abstract: str
    pdf_url: str
    run_date: str
    skim_summary: Optional[SkimSummary]

    # 중간 상태
    parsed_pdf: Optional[ParsedPDF]
    parse_mode: str  # "full", "pymupdf", "lite"
    extraction: Optional[ExtractionOutput]
    related_papers: list  # list[SearchHit] - 코퍼스 grounding용 검색 결과
    delta: Optional[DeltaOutput]
    scoring: Optional[ScoringOutput]
    verification: Optional[VerificationOutput]

    # 재시도 관련
    retry_count: int  # 재시도 횟수 (기본값: 0)
    max_retries: int  # 최대 재시도 횟수 (기본값: 2)

    # 출력
    report_md: Optional[str]
    paper_slug: str

    # 에러
    errors: Annotated[list[dict], merge_errors]


async def parse_node(state: DeepState) -> dict:
    """PDF 파싱 노드."""
    arxiv_id = state.get("arxiv_id", "")
    pdf_url = state.get("pdf_url", "")

    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    settings = get_settings()
    errors = []

    # 1. GROBID 시도
    try:
        grobid = GrobidServer(settings.grobid_url)
        parsed_pdf = await grobid.parse_pdf_full(pdf_url, arxiv_id)

        if parsed_pdf and parsed_pdf.parse_success:
            return {
                "parsed_pdf": parsed_pdf,
                "parse_mode": "full",
            }
    except Exception as e:
        errors.append({"node": "parse", "error": f"GROBID: {str(e)}"})

    # 2. PyMuPDF 폴백
    try:
        parser = PyMuPDFParser()
        parsed_pdf = await parser.parse_pdf(pdf_url, arxiv_id)

        if parsed_pdf and parsed_pdf.parse_success:
            return {
                "parsed_pdf": parsed_pdf,
                "parse_mode": "pymupdf",
                "errors": errors,
            }
    except Exception as e:
        errors.append({"node": "parse", "error": f"PyMuPDF: {str(e)}"})

    # 3. Lite 모드 (초록만)
    return {
        "parsed_pdf": None,
        "parse_mode": "lite",
        "errors": errors,
    }


async def extraction_node(state: DeepState) -> dict:
    """Extraction 노드."""
    arxiv_id = state.get("arxiv_id", "")
    title = state.get("title", "")
    abstract = state.get("abstract", "")
    parsed_pdf = state.get("parsed_pdf")
    skim_summary = state.get("skim_summary")

    # 풀텍스트 준비
    full_text = None
    if parsed_pdf and parsed_pdf.parse_success:
        full_text = parsed_pdf.get_full_text()

    agent = ExtractionAgent()

    try:
        extraction = await agent.run(
            ExtractionInput(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                full_text=full_text,
                skim_summary=skim_summary,
            )
        )

        return {"extraction": extraction}

    except Exception as e:
        return {
            "extraction": None,
            "errors": [{"node": "extraction", "error": str(e)}],
        }


async def corpus_search_node(state: DeepState) -> dict:
    """코퍼스 검색 노드 (delta grounding용).

    fail-soft: corpus_enabled=False이거나 검색 실패 시 related_papers=[]를 반환해
    이후 delta가 기존(grounding 이전)과 동일하게 동작하게 한다.
    """
    settings = get_settings()
    if not settings.corpus_enabled:
        return {"related_papers": []}

    extraction = state.get("extraction")
    if extraction is None:
        return {"related_papers": []}

    arxiv_id = state.get("arxiv_id", "") or extraction.arxiv_id
    title = state.get("title", "") or extraction.title
    abstract = state.get("abstract", "")

    # 질의 텍스트: 제목 + 초록 + 주요 claim 요약
    claim_texts = [c.text for c in extraction.claims[:5] if c.text]
    query_text = "\n".join([title, abstract, *claim_texts]).strip()

    try:
        from rtc.corpus.search import CorpusSearch

        store, embedder = _build_corpus(settings)
        search = CorpusSearch(store, embedder)
        related = search.search_related_papers(
            query_text=query_text,
            top_k=settings.delta_grounding_top_k,
            min_score=settings.delta_grounding_min_score,
            exclude_arxiv_id=arxiv_id,
        )
        return {"related_papers": related}
    except Exception as e:
        logger.warning("corpus_search skipped (fail-soft): %s", e)
        return {"related_papers": []}


async def delta_node(state: DeepState) -> dict:
    """Delta 노드."""
    extraction = state.get("extraction")

    if extraction is None:
        return {
            "delta": None,
            "errors": [{"node": "delta", "error": "No extraction result"}],
        }

    agent = DeltaAgent()

    try:
        delta = await agent.run(
            DeltaInput(
                extraction=extraction,
                related_papers=state.get("related_papers", []) or [],
            )
        )
        return {"delta": delta}

    except Exception as e:
        return {
            "delta": None,
            "errors": [{"node": "delta", "error": str(e)}],
        }


async def scoring_node(state: DeepState) -> dict:
    """Scoring 노드."""
    extraction = state.get("extraction")
    delta = state.get("delta")

    if extraction is None or delta is None:
        return {
            "scoring": None,
            "errors": [{"node": "scoring", "error": "Missing extraction or delta"}],
        }

    agent = ScoringAgent()

    try:
        scoring = await agent.run(ScoringInput(extraction=extraction, delta=delta))
        return {"scoring": scoring}

    except Exception as e:
        return {
            "scoring": None,
            "errors": [{"node": "scoring", "error": str(e)}],
        }


async def verification_node(state: DeepState) -> dict:
    """검증 노드."""
    extraction = state.get("extraction")
    delta = state.get("delta")
    parsed_pdf = state.get("parsed_pdf")
    arxiv_id = state.get("arxiv_id", "")
    title = state.get("title", "")
    abstract = state.get("abstract", "")

    if extraction is None or delta is None:
        return {
            "verification": None,
            "errors": [{"node": "verification", "error": "Missing extraction or delta"}],
        }

    # Full text 추출
    full_text = None
    if parsed_pdf and parsed_pdf.parse_success:
        full_text = parsed_pdf.get_full_text()

    agent = VerificationAgent()

    try:
        verification = await agent.run(
            VerificationInput(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                full_text=full_text,
                extraction=extraction,
                delta=delta,
            )
        )

        return {"verification": verification}

    except Exception as e:
        return {
            "verification": None,
            "errors": [{"node": "verification", "error": str(e)}],
        }


async def correction_node(state: DeepState) -> dict:
    """교정 노드 - 검증 실패 항목 수정."""
    verification = state.get("verification")
    extraction = state.get("extraction")
    delta = state.get("delta")
    parsed_pdf = state.get("parsed_pdf")
    arxiv_id = state.get("arxiv_id", "")
    title = state.get("title", "")
    abstract = state.get("abstract", "")
    retry_count = state.get("retry_count", 0)

    if verification is None or extraction is None or delta is None:
        return {
            "errors": [{"node": "correction", "error": "Missing required data"}],
            "retry_count": retry_count + 1,
        }

    # Full text 추출
    full_text = None
    if parsed_pdf and parsed_pdf.parse_success:
        full_text = parsed_pdf.get_full_text()

    agent = CorrectionAgent()

    try:
        corrected = await agent.run(
            CorrectionInput(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                full_text=full_text,
                extraction=extraction,
                delta=delta,
                verification=verification,
            )
        )

        return {
            "extraction": corrected.extraction,
            "delta": corrected.delta,
            "retry_count": retry_count + 1,
        }

    except Exception as e:
        return {
            "errors": [{"node": "correction", "error": str(e)}],
            "retry_count": retry_count + 1,
        }


def should_retry_or_proceed(state: DeepState) -> str:
    """검증 결과에 따라 분기."""
    verification = state.get("verification")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if verification is None:
        return "report"

    # 신뢰도 높음 → 통과
    if verification.overall_reliability == "high":
        return "report"

    # 재시도 가능 → 교정
    if retry_count < max_retries:
        return "correction"

    # 최대 재시도 초과 → 현재 결과로 진행
    return "report"


async def report_node(state: DeepState) -> dict:
    """Report 생성 노드."""
    extraction = state.get("extraction")
    delta = state.get("delta")
    scoring = state.get("scoring")
    skim_summary = state.get("skim_summary")
    run_date = state.get("run_date", datetime.now().strftime("%Y-%m-%d"))

    if extraction is None or delta is None or scoring is None:
        return {
            "report_md": None,
            "errors": [{"node": "report", "error": "Missing required data"}],
        }

    agent = ReportWriter()

    try:
        report_md = await agent.run(
            ReportInput(
                skim=skim_summary,
                extraction=extraction,
                delta=delta,
                scoring=scoring,
                run_date=run_date,
            )
        )

        # 슬러그 생성
        paper_slug = create_paper_slug(extraction.arxiv_id, extraction.title)

        return {
            "report_md": report_md,
            "paper_slug": paper_slug,
        }

    except Exception as e:
        return {
            "report_md": None,
            "errors": [{"node": "report", "error": str(e)}],
        }


async def save_deep_node(state: DeepState) -> dict:
    """Deep 결과 저장 노드."""
    extraction = state.get("extraction")
    delta = state.get("delta")
    scoring = state.get("scoring")
    verification = state.get("verification")
    report_md = state.get("report_md")
    paper_slug = state.get("paper_slug", "")

    if not paper_slug or not extraction:
        return {"errors": [{"node": "save_deep", "error": "Missing paper_slug or extraction"}]}

    settings = get_settings()
    store = DeepStore(settings.base_dir, reports_dir=settings.reports_dir)

    try:
        # 각 아티팩트 저장
        if extraction:
            store.save_extraction(paper_slug, extraction)

        if delta:
            store.save_delta(paper_slug, delta)

        if scoring:
            store.save_scoring(paper_slug, scoring)

        if verification:
            store.save_verification(paper_slug, verification)

        if report_md:
            store.save_report(paper_slug, report_md)

        return {}

    except Exception as e:
        return {"errors": [{"node": "save_deep", "error": str(e)}]}


async def corpus_index_node(state: DeepState) -> dict:
    """현재 논문을 코퍼스에 인덱싱 (delta 이후라 자기 자신이 grounding에 안 잡힘).

    fail-soft: corpus_enabled=False이거나 인덱싱 실패 시 조용히 스킵.
    """
    settings = get_settings()
    if not settings.corpus_enabled:
        return {}

    extraction = state.get("extraction")
    delta = state.get("delta")
    if extraction is None or delta is None:
        return {}

    try:
        from rtc.corpus.indexer import CorpusIndexer

        store, embedder = _build_corpus(settings)
        indexer = CorpusIndexer(store, embedder)
        n = indexer.index_paper(
            arxiv_id=extraction.arxiv_id,
            extraction=extraction,
            delta=delta,
            extra_metadata={
                "title": extraction.title,
                "slug": state.get("paper_slug", ""),
            },
        )
        logger.info("Indexed %s into corpus: %d chunks", extraction.arxiv_id, n)
    except Exception as e:
        logger.warning("corpus_index skipped (fail-soft): %s", e)

    return {}


def should_continue_after_parse(state: DeepState) -> str:
    """parse 후 계속 진행 여부."""
    # 항상 extraction으로 진행 (lite mode도 가능)
    return "extraction"


def build_deep_pipeline() -> StateGraph:
    """Deep Pipeline 빌드.

    파이프라인 구조:
    parse → extraction → corpus_search → delta → scoring → verification → [조건 분기]
    (통과/최대재시도 경로의 끝: report → save_deep → corpus_index → END)
                                                              │
                                        ┌─────────────────────┼─────────────────────┐
                                        │                     │                     │
                                  [통과: high]          [재시도 필요]         [최대 재시도 초과]
                                        │              (medium/low)                 │
                                        ▼                     │                     │
                                     report                   ▼                     │
                                        │              correction                   │
                                        │                     │                     │
                                        │                     ▼                     │
                                        │            extraction (재실행)            │
                                        │                     ↓                     │
                                        │               (delta → scoring →         │
                                        │                verification 반복)         │
                                        │                                           │
                                        ▼                                           │
                                   save_deep ←──────────────────────────────────────┘
                                        │
                                       END

    Returns:
        LangGraph StateGraph
    """
    graph = StateGraph(DeepState)

    # 노드 추가
    graph.add_node("parse", parse_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("corpus_search", corpus_search_node)
    graph.add_node("delta", delta_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("verification", verification_node)
    graph.add_node("correction", correction_node)
    graph.add_node("report", report_node)
    graph.add_node("save_deep", save_deep_node)
    graph.add_node("corpus_index", corpus_index_node)

    # 엔트리 포인트
    graph.set_entry_point("parse")

    # 기본 엣지
    graph.add_edge("parse", "extraction")
    graph.add_edge("extraction", "corpus_search")
    graph.add_edge("corpus_search", "delta")
    graph.add_edge("delta", "scoring")
    graph.add_edge("scoring", "verification")

    # 조건 분기: verification 후
    graph.add_conditional_edges(
        "verification",
        should_retry_or_proceed,
        {
            "report": "report",
            "correction": "correction",
        }
    )

    # 교정 후 → 다시 extraction부터 (수정된 컨텍스트로)
    graph.add_edge("correction", "extraction")

    # 마무리: 저장 후 코퍼스 인덱싱 (delta 이후라 자기 자신은 grounding에 안 잡힘)
    graph.add_edge("report", "save_deep")
    graph.add_edge("save_deep", "corpus_index")
    graph.add_edge("corpus_index", END)

    return graph


def create_deep_pipeline():
    """Deep Pipeline 컴파일.

    Returns:
        컴파일된 LangGraph runnable
    """
    graph = build_deep_pipeline()
    return graph.compile()


@traceable(name="deep_pipeline", run_type="chain")
async def run_deep_pipeline(
    arxiv_id: str,
    title: str,
    abstract: str,
    pdf_url: str | None = None,
    run_date: str | None = None,
    skim_summary: SkimSummary | None = None,
    max_retries: int = 2,
) -> DeepState:
    """Deep Pipeline 실행.

    Args:
        arxiv_id: arXiv ID
        title: 논문 제목
        abstract: 초록
        pdf_url: PDF URL (없으면 자동 생성)
        run_date: 실행 날짜 (YYYY-MM-DD)
        skim_summary: 스킴 결과 (있으면)
        max_retries: 최대 재시도 횟수 (기본값: 2)

    Returns:
        최종 상태
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    if pdf_url is None:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    pipeline = create_deep_pipeline()

    initial_state: DeepState = {
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "pdf_url": pdf_url,
        "run_date": run_date,
        "skim_summary": skim_summary,
        "retry_count": 0,
        "max_retries": max_retries,
        "errors": [],
    }

    result = await pipeline.ainvoke(initial_state)
    return result


# CLI 지원
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run Deep Pipeline")
    parser.add_argument("--arxiv-id", type=str, required=True, help="arXiv ID")
    parser.add_argument("--title", type=str, required=True, help="Paper title")
    parser.add_argument("--abstract", type=str, default="", help="Abstract")
    parser.add_argument("--date", type=str, help="Run date (YYYY-MM-DD)")
    args = parser.parse_args()

    result = asyncio.run(
        run_deep_pipeline(
            arxiv_id=args.arxiv_id,
            title=args.title,
            abstract=args.abstract,
            run_date=args.date,
        )
    )

    print(f"\n=== Deep Pipeline Results ===")
    print(f"ArXiv ID: {result.get('arxiv_id')}")
    print(f"Paper Slug: {result.get('paper_slug')}")
    print(f"Parse Mode: {result.get('parse_mode')}")

    scoring = result.get("scoring")
    if scoring:
        print(f"Score: {scoring.total}/15 ({scoring.recommendation})")

    if result.get("errors"):
        print(f"\nErrors:")
        for err in result["errors"]:
            print(f"  - {err}")
