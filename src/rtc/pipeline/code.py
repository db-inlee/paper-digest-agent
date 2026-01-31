"""Code Pipeline - GitHub 기반 방법론 구현 추출 파이프라인."""

from datetime import datetime
from typing import Optional

from langsmith.run_helpers import traceable

from rtc.agents.github_method_agent import GitHubMethodAgent, GitHubMethodInput
from rtc.config import get_settings
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.github_method import GitHubMethodOutput
from rtc.storage.code_store import CodeStore


@traceable(name="code_pipeline", run_type="chain")
async def run_code_pipeline(
    arxiv_id: str,
    paper_slug: str,
    extraction: ExtractionOutput,
    github_url: str,
) -> dict:
    """GitHub 기반 코드 분석 파이프라인 실행.

    Args:
        arxiv_id: arXiv ID
        paper_slug: 논문 슬러그
        extraction: 추출 결과 (방법론 정보 포함)
        github_url: GitHub 레포 URL

    Returns:
        결과 딕셔너리
    """
    settings = get_settings()
    errors: list[dict] = []

    # GitHubMethodAgent 실행
    agent = GitHubMethodAgent()

    try:
        result = await agent.run(
            GitHubMethodInput(
                extraction=extraction,
                github_url=github_url,
            )
        )

        # 결과 저장
        store = CodeStore(settings.base_dir)
        store.save_github_method(paper_slug, result)

        return {
            "arxiv_id": arxiv_id,
            "paper_slug": paper_slug,
            "github_url": github_url,
            "methods_found": result.total_methods_found,
            "result": result,
            "errors": errors,
        }

    except Exception as e:
        errors.append({"node": "github_method", "error": str(e)})
        return {
            "arxiv_id": arxiv_id,
            "paper_slug": paper_slug,
            "github_url": github_url,
            "methods_found": 0,
            "result": None,
            "errors": errors,
        }

    finally:
        await agent.close()


def select_best_github_paper(
    papers: list[dict],
    max_papers: int = 1,
) -> list[dict]:
    """GitHub가 있는 논문 중 최고 점수 논문 선택.

    Args:
        papers: 논문 목록 (skim 결과 + deep 결과 조합)
        max_papers: 최대 선택 수

    Returns:
        선택된 논문 목록
    """
    # GitHub URL이 있는 논문만 필터
    github_papers = [p for p in papers if p.get("github_url")]

    if not github_papers:
        return []

    # 점수순 정렬 (interest_score 또는 total_score)
    def get_score(p):
        return p.get("total_score", p.get("interest_score", 0))

    github_papers.sort(key=get_score, reverse=True)

    return github_papers[:max_papers]


# CLI 지원
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run GitHub Method Pipeline")
    parser.add_argument("--slug", type=str, required=True, help="Paper slug")
    parser.add_argument("--github", type=str, required=True, help="GitHub URL")
    args = parser.parse_args()

    # Deep 결과에서 extraction 로드
    from rtc.storage.deep_store import DeepStore

    settings = get_settings()
    deep_store = DeepStore(settings.base_dir)

    extraction = deep_store.load_extraction(args.slug)

    if not extraction:
        print(f"Error: Cannot load extraction for {args.slug}")
        exit(1)

    result = asyncio.run(
        run_code_pipeline(
            arxiv_id=extraction.arxiv_id,
            paper_slug=args.slug,
            extraction=extraction,
            github_url=args.github,
        )
    )

    print(f"\n=== GitHub Method Pipeline Results ===")
    print(f"Paper Slug: {result.get('paper_slug')}")
    print(f"GitHub URL: {result.get('github_url')}")
    print(f"Methods Found: {result.get('methods_found', 0)}")

    if result.get("result"):
        method_result = result["result"]
        print(f"\nStructure: {method_result.structure_summary}")
        print(f"\nMethods:")
        for m in method_result.methods:
            print(f"  - {m.method_name}: {m.file_path}")

    if result.get("errors"):
        print(f"\nErrors:")
        for err in result["errors"]:
            print(f"  - {err}")
