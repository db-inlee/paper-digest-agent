"""DeepStore - reports/<slug>/ 저장 관리."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.verification_v1 import VerificationOutput


def create_paper_slug(arxiv_id: str, title: str) -> str:
    """논문 슬러그 생성.

    Args:
        arxiv_id: arXiv ID (예: 2601.18491)
        title: 논문 제목

    Returns:
        슬러그 (예: 2601.18491-agentdog)
    """
    # 제목에서 알파벳/숫자만 추출, 소문자로
    title_clean = re.sub(r"[^a-zA-Z0-9\s]", "", title.lower())
    # 공백을 하이픈으로, 30자 제한
    title_slug = "-".join(title_clean.split())[:30].rstrip("-")
    return f"{arxiv_id}-{title_slug}"


class DeepStore:
    """reports/ 디렉토리 저장 관리.

    reports/<paper_slug>/ 구조:
    - extraction.json
    - delta.json
    - scoring.json
    - deep.md
    - verification.json (선택)
    """

    def __init__(self, base_dir: Path):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리
        """
        self.reports_dir = base_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def get_paper_dir(self, slug: str) -> Path:
        """논문 디렉토리 경로."""
        paper_dir = self.reports_dir / slug
        paper_dir.mkdir(parents=True, exist_ok=True)
        return paper_dir

    def save_extraction(self, slug: str, data: ExtractionOutput) -> Path:
        """extraction.json 저장.

        Args:
            slug: 논문 슬러그
            data: 추출 결과

        Returns:
            저장된 파일 경로
        """
        paper_dir = self.get_paper_dir(slug)
        path = paper_dir / "extraction.json"

        content = data.model_dump()
        path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def save_delta(self, slug: str, data: DeltaOutput) -> Path:
        """delta.json 저장.

        Args:
            slug: 논문 슬러그
            data: Delta 결과

        Returns:
            저장된 파일 경로
        """
        paper_dir = self.get_paper_dir(slug)
        path = paper_dir / "delta.json"

        content = data.model_dump()
        path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def save_scoring(self, slug: str, data: ScoringOutput) -> Path:
        """scoring.json 저장.

        Args:
            slug: 논문 슬러그
            data: 스코어링 결과

        Returns:
            저장된 파일 경로
        """
        paper_dir = self.get_paper_dir(slug)
        path = paper_dir / "scoring.json"

        content = data.model_dump()
        path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def save_report(self, slug: str, markdown: str) -> Path:
        """deep.md 저장.

        Args:
            slug: 논문 슬러그
            markdown: 마크다운 리포트

        Returns:
            저장된 파일 경로
        """
        paper_dir = self.get_paper_dir(slug)
        path = paper_dir / "deep.md"

        path.write_text(markdown, encoding="utf-8")
        return path

    def load_extraction(self, slug: str) -> Optional[ExtractionOutput]:
        """extraction.json 로드."""
        path = self.reports_dir / slug / "extraction.json"
        if not path.exists():
            return None

        content = json.loads(path.read_text(encoding="utf-8"))
        return ExtractionOutput(**content)

    def load_delta(self, slug: str) -> Optional[DeltaOutput]:
        """delta.json 로드."""
        path = self.reports_dir / slug / "delta.json"
        if not path.exists():
            return None

        content = json.loads(path.read_text(encoding="utf-8"))
        return DeltaOutput(**content)

    def load_scoring(self, slug: str) -> Optional[ScoringOutput]:
        """scoring.json 로드."""
        path = self.reports_dir / slug / "scoring.json"
        if not path.exists():
            return None

        content = json.loads(path.read_text(encoding="utf-8"))
        return ScoringOutput(**content)

    def load_report(self, slug: str) -> Optional[str]:
        """deep.md 로드."""
        path = self.reports_dir / slug / "deep.md"
        if not path.exists():
            return None

        return path.read_text(encoding="utf-8")

    def list_papers(self) -> list[str]:
        """저장된 논문 슬러그 목록.

        Returns:
            슬러그 목록 (최신순)
        """
        slugs = []
        for path in self.reports_dir.iterdir():
            if path.is_dir() and (path / "deep.md").exists():
                slugs.append(path.name)
        return sorted(slugs, reverse=True)

    def save_verification(self, slug: str, data: VerificationOutput) -> Path:
        """verification.json 저장.

        Args:
            slug: 논문 슬러그
            data: 검증 결과

        Returns:
            저장된 파일 경로
        """
        paper_dir = self.get_paper_dir(slug)
        path = paper_dir / "verification.json"

        content = data.model_dump()
        path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load_verification(self, slug: str) -> Optional[VerificationOutput]:
        """verification.json 로드."""
        path = self.reports_dir / slug / "verification.json"
        if not path.exists():
            return None

        content = json.loads(path.read_text(encoding="utf-8"))
        return VerificationOutput(**content)

    def paper_exists(self, slug: str) -> bool:
        """논문 디렉토리 존재 여부."""
        return (self.reports_dir / slug / "deep.md").exists()

    def get_paper_metadata(self, slug: str) -> dict:
        """논문 메타데이터 조회."""
        extraction = self.load_extraction(slug)
        scoring = self.load_scoring(slug)

        if not extraction:
            return {}

        return {
            "slug": slug,
            "arxiv_id": extraction.arxiv_id,
            "title": extraction.title,
            "score": scoring.total if scoring else None,
            "recommendation": scoring.recommendation if scoring else None,
        }
