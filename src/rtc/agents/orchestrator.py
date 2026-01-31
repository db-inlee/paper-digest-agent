"""Orchestrator - 전체 파이프라인 조율 (비-LLM)."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from langsmith.run_helpers import traceable

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.schemas.skim import SkimSummary
from rtc.storage.deep_store import DeepStore
from rtc.storage.index_store import IndexStore
from rtc.storage.skim_store import SkimStore


@dataclass
class OrchestratorInput:
    """Orchestrator 입력."""

    run_date: Optional[str] = None  # YYYY-MM-DD, None이면 오늘
    run_deep: bool = True  # Deep 분석 실행 여부
    generate_code: bool = False  # 코드 생성 여부
    force_rerun: bool = False  # 이미 처리된 논문도 다시 실행


@dataclass
class OrchestratorOutput:
    """Orchestrator 출력."""

    run_date: str
    total_collected: int
    total_skimmed: int
    deep_candidates: list[str]
    deep_completed: list[str]
    code_generated: list[str]
    daily_report_path: Optional[str] = None
    errors: list[dict] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class Orchestrator(BaseAgent[OrchestratorInput, OrchestratorOutput]):
    """전체 파이프라인 조율 에이전트 (비-LLM).

    Skim → Deep (병렬) → Code → Daily Report 파이프라인을 실행합니다.
    """

    name = "orchestrator"
    uses_llm = False

    def __init__(self):
        self.settings = get_settings()
        self.skim_store = SkimStore(self.settings.base_dir)
        self.deep_store = DeepStore(self.settings.base_dir)
        self.index_store = IndexStore(self.settings.base_dir)

    async def run(self, input: OrchestratorInput) -> OrchestratorOutput:
        """전체 파이프라인 실행.

        Args:
            input: 실행 옵션

        Returns:
            실행 결과
        """
        run_date = input.run_date or datetime.now().strftime("%Y-%m-%d")
        errors: list[dict] = []
        deep_completed: list[str] = []
        code_generated: list[str] = []

        # 1. Skim Pipeline 실행
        from rtc.pipeline.skim import run_skim_pipeline

        print(f"[Orchestrator] Running Skim Pipeline for {run_date}...")
        skim_result = await run_skim_pipeline(run_date)

        total_collected = skim_result.get("total_collected", 0)
        total_skimmed = skim_result.get("total_skimmed", 0)
        deep_candidates = skim_result.get("deep_candidates", [])
        all_papers = skim_result.get("all_papers", [])

        if skim_result.get("errors"):
            errors.extend(skim_result["errors"])

        print(f"[Orchestrator] Skim complete: {total_skimmed} papers, {len(deep_candidates)} deep candidates")

        # 2. Deep Pipeline 실행 (선택적, 병렬 처리)
        if input.run_deep and deep_candidates:
            from rtc.pipeline.deep import run_deep_pipeline

            print(f"[Orchestrator] Running Deep Pipeline for {len(deep_candidates)} papers (parallel)...")

            # 처리할 논문과 스킵할 논문 분류
            papers_to_process: list[tuple[str, SkimSummary]] = []
            for arxiv_id in deep_candidates:
                paper = self._find_paper(arxiv_id, all_papers)
                if not paper:
                    errors.append({
                        "node": "orchestrator",
                        "error": f"Paper not found: {arxiv_id}",
                    })
                    continue

                slug = self._get_paper_slug(arxiv_id, paper.title)
                if not input.force_rerun and self.deep_store.paper_exists(slug):
                    print(f"  [Skip] {arxiv_id} already processed")
                    deep_completed.append(arxiv_id)
                else:
                    papers_to_process.append((arxiv_id, paper))

            # 병렬 처리
            if papers_to_process:
                print(f"  [Parallel] Processing {len(papers_to_process)} papers...")

                async def process_paper(arxiv_id: str, paper: SkimSummary) -> dict:
                    """개별 논문 처리."""
                    try:
                        result = await run_deep_pipeline(
                            arxiv_id=arxiv_id,
                            title=paper.title,
                            abstract="",
                            run_date=run_date,
                            skim_summary=paper,
                        )
                        return {
                            "arxiv_id": arxiv_id,
                            "success": bool(result.get("report_md")),
                            "errors": result.get("errors", []),
                        }
                    except Exception as e:
                        return {
                            "arxiv_id": arxiv_id,
                            "success": False,
                            "errors": [{"node": "orchestrator", "error": f"Deep failed for {arxiv_id}: {str(e)}"}],
                        }

                # 모든 논문 병렬 실행
                tasks = [process_paper(arxiv_id, paper) for arxiv_id, paper in papers_to_process]
                results = await asyncio.gather(*tasks)

                # 결과 집계
                for result in results:
                    if result["errors"]:
                        errors.extend(result["errors"])
                    if result["success"]:
                        deep_completed.append(result["arxiv_id"])
                        print(f"  [Done] {result['arxiv_id']}")
                    else:
                        print(f"  [Fail] {result['arxiv_id']}")

        # 3. GitHub Method Pipeline 실행 (선택적)
        # GitHub 있는 논문 중 하루 1개만 처리
        if input.generate_code and deep_completed:
            from rtc.pipeline.code import run_code_pipeline
            from rtc.storage.code_store import CodeStore

            code_store = CodeStore(self.settings.base_dir)

            # GitHub 있는 논문 중 점수 높은 1개 선택
            github_paper = None
            for arxiv_id in deep_completed:
                paper = self._find_paper(arxiv_id, all_papers)
                if paper and paper.github_url:
                    slug = self._get_paper_slug(arxiv_id, paper.title)
                    # 이미 처리된 건 스킵
                    if not input.force_rerun and code_store.github_method_exists(slug):
                        print(f"  [Skip] {arxiv_id} GitHub method already exists")
                        code_generated.append(arxiv_id)
                        continue
                    github_paper = paper
                    break  # 하루 1개만

            if github_paper:
                arxiv_id = github_paper.arxiv_id
                slug = self._get_paper_slug(arxiv_id, github_paper.title)

                print(f"[Orchestrator] Running GitHub Method Pipeline for {arxiv_id}...")
                print(f"  GitHub: {github_paper.github_url}")

                # Deep 결과 로드
                extraction = self.deep_store.load_extraction(slug)

                if not extraction:
                    errors.append({
                        "node": "orchestrator",
                        "error": f"Cannot load extraction for {arxiv_id}",
                    })
                else:
                    try:
                        code_result = await run_code_pipeline(
                            arxiv_id=arxiv_id,
                            paper_slug=slug,
                            extraction=extraction,
                            github_url=github_paper.github_url,
                        )

                        if code_result.get("errors"):
                            errors.extend(code_result["errors"])

                        if code_result.get("methods_found", 0) > 0:
                            code_generated.append(arxiv_id)
                            print(f"  [Done] {arxiv_id} - {code_result.get('methods_found')} methods found")

                    except Exception as e:
                        errors.append({
                            "node": "orchestrator",
                            "error": f"GitHub Method failed for {arxiv_id}: {str(e)}",
                        })
            else:
                print("[Orchestrator] No papers with GitHub repos to analyze")

        # 4. Daily Report 생성
        daily_report_path: Optional[str] = None
        if deep_completed:
            from rtc.agents.daily_report_agent import generate_daily_report

            print("[Orchestrator] Generating Daily Report...")

            try:
                report_result = await generate_daily_report(
                    run_date=run_date,
                    deep_completed=deep_completed,
                    all_papers=all_papers,
                )
                daily_report_path = report_result.report_path
                print(f"  [Done] Daily report saved to: {daily_report_path}")

            except Exception as e:
                errors.append({
                    "node": "orchestrator",
                    "error": f"Daily report failed: {str(e)}",
                })

        # 5. Index 업데이트
        print("[Orchestrator] Updating index...")
        try:
            self.index_store.update_by_date(run_date, deep_completed)

            # 태그별 인덱스 (스킴 결과 사용)
            if all_papers:
                self.index_store.update_by_tag(all_papers)

            # 점수별 인덱스 (딥 결과 사용)
            score_data = []
            for arxiv_id in deep_completed:
                paper = self._find_paper(arxiv_id, all_papers)
                if paper:
                    slug = self._get_paper_slug(arxiv_id, paper.title)
                    scoring = self.deep_store.load_scoring(slug)
                    if scoring:
                        score_data.append((arxiv_id, scoring.total))
            if score_data:
                self.index_store.update_by_score(score_data)

        except Exception as e:
            errors.append({
                "node": "orchestrator",
                "error": f"Index update failed: {str(e)}",
            })

        print(f"[Orchestrator] Complete!")

        return OrchestratorOutput(
            run_date=run_date,
            total_collected=total_collected,
            total_skimmed=total_skimmed,
            deep_candidates=deep_candidates,
            deep_completed=deep_completed,
            code_generated=code_generated,
            daily_report_path=daily_report_path,
            errors=errors,
        )

    def _find_paper(
        self, arxiv_id: str, papers: list[SkimSummary]
    ) -> Optional[SkimSummary]:
        """arxiv_id로 논문 찾기."""
        for paper in papers:
            if paper.arxiv_id == arxiv_id:
                return paper
        return None

    def _get_paper_slug(self, arxiv_id: str, title: str) -> str:
        """논문 슬러그 생성."""
        from rtc.storage.deep_store import create_paper_slug
        return create_paper_slug(arxiv_id, title)


@traceable(name="orchestrator", run_type="chain")
async def run_orchestrator(
    run_date: Optional[str] = None,
    run_deep: bool = True,
    generate_code: bool = False,
    force_rerun: bool = False,
) -> OrchestratorOutput:
    """Orchestrator 실행 헬퍼.

    Args:
        run_date: 실행 날짜 (YYYY-MM-DD)
        run_deep: Deep 분석 실행 여부
        generate_code: 코드 생성 여부
        force_rerun: 강제 재실행 여부

    Returns:
        실행 결과
    """
    orchestrator = Orchestrator()
    return await orchestrator.run(
        OrchestratorInput(
            run_date=run_date,
            run_deep=run_deep,
            generate_code=generate_code,
            force_rerun=force_rerun,
        )
    )


# CLI 지원
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run Orchestrator")
    parser.add_argument("--date", type=str, help="Run date (YYYY-MM-DD)")
    parser.add_argument("--deep", action="store_true", default=True, help="Run deep analysis")
    parser.add_argument("--no-deep", action="store_false", dest="deep", help="Skip deep analysis")
    parser.add_argument("--code", action="store_true", help="Generate code")
    parser.add_argument("--force", action="store_true", help="Force rerun")
    args = parser.parse_args()

    result = asyncio.run(
        run_orchestrator(
            run_date=args.date,
            run_deep=args.deep,
            generate_code=args.code,
            force_rerun=args.force,
        )
    )

    print(f"\n=== Orchestrator Results ===")
    print(f"Date: {result.run_date}")
    print(f"Collected: {result.total_collected}")
    print(f"Skimmed: {result.total_skimmed}")
    print(f"Deep Candidates: {result.deep_candidates}")
    print(f"Deep Completed: {result.deep_completed}")
    print(f"Code Generated: {result.code_generated}")
    if result.daily_report_path:
        print(f"Daily Report: {result.daily_report_path}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors[:5]:  # 처음 5개만
            print(f"  - {err}")
