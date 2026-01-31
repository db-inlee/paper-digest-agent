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

    def __init__(self, base_dir: Path):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리
        """
        self.papers_dir = base_dir / "papers"
        self.papers_dir.mkdir(parents=True, exist_ok=True)

    def save(self, output: DailySkimOutput) -> Path:
        """일별 스킴 결과 저장.

        Args:
            output: 저장할 스킴 결과

        Returns:
            저장된 파일 경로
        """
        path = self.papers_dir / f"{output.date}.yaml"

        # Pydantic 모델을 dict로 변환 (datetime 처리)
        data = output.model_dump()
        data["skimmed_at"] = output.skimmed_at.isoformat()

        # 각 paper의 datetime도 처리
        for paper in data.get("papers", []):
            if "skimmed_at" in paper and isinstance(paper["skimmed_at"], datetime):
                paper["skimmed_at"] = paper["skimmed_at"].isoformat()

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return path

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
