"""SkimStore - papers/YYYY-MM-DD.yaml 저장 관리."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from rtc.schemas.skim import DailySkimOutput, SkimSummary


class SkimStore:
    """papers/ 디렉토리 저장 관리.

    papers/YYYY-MM-DD.yaml 형식으로 일별 스킴 결과를 저장합니다.
    """

    def __init__(self, base_dir: Path, *, papers_dir: Path | None = None):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리 (레거시)
            papers_dir: papers 디렉토리 경로 (우선 사용)
        """
        self.papers_dir = papers_dir if papers_dir is not None else base_dir / "papers"
        self.papers_dir.mkdir(parents=True, exist_ok=True)

    def save(self, output: DailySkimOutput) -> Path:
        """일별 스킴 결과 저장.

        A same-date rerun never blindly overwrites: existing paper records are
        merged by arxiv_id so that no previously stored skim record is lost.

        Args:
            output: 저장할 스킴 결과

        Returns:
            저장된 파일 경로
        """
        path = self.papers_dir / f"{output.date}.yaml"
        merged = self._merge_with_existing(output, path)

        # Pydantic 모델을 dict로 변환 (datetime 처리)
        data = merged.model_dump()
        data["skimmed_at"] = merged.skimmed_at.isoformat()

        # 각 paper의 datetime도 처리
        for paper in data.get("papers", []):
            if "skimmed_at" in paper and isinstance(paper["skimmed_at"], datetime):
                paper["skimmed_at"] = paper["skimmed_at"].isoformat()

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return path

    def _merge_with_existing(
        self, output: DailySkimOutput, path: Path
    ) -> DailySkimOutput:
        """Merge a fresh run with whatever is already stored for that date.

        Papers and deep candidates are unioned by arxiv_id (the fresh record
        wins on collision). Run-level counters describe the latest run only.
        A file that cannot be parsed is moved aside instead of being dropped.

        Args:
            output: 새로 저장할 스킴 결과
            path: 대상 yaml 경로

        Returns:
            병합된 스킴 결과 (기존 파일이 없으면 output 그대로)
        """
        if not path.exists():
            return output

        try:
            existing = self.load(output.date)
        except Exception:
            self._backup_unreadable(path)
            return output

        if existing is None:
            return output

        # Papers: keep existing order, refresh on collision, append newcomers.
        by_id = {paper.arxiv_id: paper for paper in existing.papers}
        for paper in output.papers:
            by_id[paper.arxiv_id] = paper

        deep_candidates = list(existing.deep_candidates)
        for arxiv_id in output.deep_candidates:
            if arxiv_id not in deep_candidates:
                deep_candidates.append(arxiv_id)

        # Keyword snapshot: the fresh run wins unless it carries none.
        effective_keywords = output.effective_keywords or existing.effective_keywords

        return output.model_copy(
            update={
                "papers": list(by_id.values()),
                "deep_candidates": deep_candidates,
                "effective_keywords": effective_keywords,
            }
        )

    def _backup_unreadable(self, path: Path) -> Path:
        """Move an unparsable yaml aside so a fresh save can proceed.

        Args:
            path: 읽을 수 없는 yaml 경로

        Returns:
            백업된 파일 경로
        """
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.{stamp}.bak")
        path.rename(backup)
        return backup

    def load(self, date: str) -> Optional[DailySkimOutput]:
        """일별 스킴 결과 로드.

        Args:
            date: YYYY-MM-DD 형식 날짜

        Returns:
            스킴 결과 또는 None
        """
        path = self.papers_dir / f"{date}.yaml"

        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # datetime 문자열을 datetime 객체로 변환
        if "skimmed_at" in data and isinstance(data["skimmed_at"], str):
            data["skimmed_at"] = datetime.fromisoformat(data["skimmed_at"])

        return DailySkimOutput(**data)

    def list_dates(self) -> list[str]:
        """저장된 날짜 목록 반환.

        Returns:
            YYYY-MM-DD 형식 날짜 목록 (최신순)
        """
        dates = []
        for path in self.papers_dir.glob("*.yaml"):
            date = path.stem  # 파일명에서 확장자 제거
            dates.append(date)
        return sorted(dates, reverse=True)

    def get_deep_candidates(self, date: str) -> list[str]:
        """특정 날짜의 Deep 분석 대상 목록.

        Args:
            date: YYYY-MM-DD 형식 날짜

        Returns:
            Deep 분석 대상 arxiv_id 목록
        """
        output = self.load(date)
        if output is None:
            return []
        return output.deep_candidates

    def get_paper(self, date: str, arxiv_id: str) -> Optional[SkimSummary]:
        """특정 논문 정보 조회.

        Args:
            date: YYYY-MM-DD 형식 날짜
            arxiv_id: 논문 ID

        Returns:
            스킴 결과 또는 None
        """
        output = self.load(date)
        if output is None:
            return None

        for paper in output.papers:
            if paper.arxiv_id == arxiv_id:
                return paper
        return None
