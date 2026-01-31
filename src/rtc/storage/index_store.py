"""IndexStore - index/ 디렉토리 관리."""

from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

from rtc.schemas.skim import SkimSummary


class IndexStore:
    """index/ 디렉토리 관리.

    구조:
    - by_date.yaml: 날짜별 논문 인덱스
    - by_tag.yaml: 태그별 논문 인덱스
    - by_score.yaml: 점수별 논문 인덱스
    """

    def __init__(self, base_dir: Path):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리
        """
        self.index_dir = base_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def update_by_date(self, date: str, arxiv_ids: list[str]) -> Path:
        """날짜별 인덱스 업데이트.

        Args:
            date: YYYY-MM-DD 형식 날짜
            arxiv_ids: 해당 날짜에 처리된 논문 ID들

        Returns:
            인덱스 파일 경로
        """
        path = self.index_dir / "by_date.yaml"

        # 기존 데이터 로드
        data = self._load_yaml(path) or {}

        # 업데이트
        data[date] = arxiv_ids

        # 저장 (최신 날짜 순으로 정렬)
        sorted_data = dict(sorted(data.items(), reverse=True))
        self._save_yaml(path, sorted_data)

        return path

    def update_by_tag(self, papers: list[SkimSummary]) -> Path:
        """태그별 인덱스 업데이트.

        Args:
            papers: 스킴 결과 목록

        Returns:
            인덱스 파일 경로
        """
        path = self.index_dir / "by_tag.yaml"

        # 기존 데이터 로드
        data = self._load_yaml(path) or {}

        # 태그별로 그룹화
        for paper in papers:
            for tag in paper.tags:
                tag_lower = tag.lower()
                if tag_lower not in data:
                    data[tag_lower] = []
                if paper.arxiv_id not in data[tag_lower]:
                    data[tag_lower].append(paper.arxiv_id)

        # 저장 (태그 알파벳 순)
        sorted_data = dict(sorted(data.items()))
        self._save_yaml(path, sorted_data)

        return path

    def update_by_score(self, score_data: list[tuple[str, int]]) -> Path:
        """점수별 인덱스 업데이트.

        Args:
            score_data: (arxiv_id, score) 튜플 리스트

        Returns:
            인덱스 파일 경로
        """
        path = self.index_dir / "by_score.yaml"

        # 기존 데이터 로드
        data = self._load_yaml(path) or {}

        # 점수 업데이트
        for arxiv_id, score in score_data:
            data[arxiv_id] = score

        # 저장 (점수 높은 순)
        sorted_data = dict(sorted(data.items(), key=lambda x: x[1], reverse=True))
        self._save_yaml(path, sorted_data)

        return path

    def get_by_date(self, date: str) -> list[str]:
        """특정 날짜의 논문 목록.

        Args:
            date: YYYY-MM-DD 형식 날짜

        Returns:
            arxiv_id 목록
        """
        path = self.index_dir / "by_date.yaml"
        data = self._load_yaml(path) or {}
        return data.get(date, [])

    def get_by_tag(self, tag: str) -> list[str]:
        """특정 태그의 논문 목록.

        Args:
            tag: 태그 (소문자로 변환됨)

        Returns:
            arxiv_id 목록
        """
        path = self.index_dir / "by_tag.yaml"
        data = self._load_yaml(path) or {}
        return data.get(tag.lower(), [])

    def get_top_scored(self, n: int = 10) -> list[tuple[str, int]]:
        """점수 높은 논문 목록.

        Args:
            n: 반환할 개수

        Returns:
            (arxiv_id, score) 튜플 리스트
        """
        path = self.index_dir / "by_score.yaml"
        data = self._load_yaml(path) or {}

        # 점수 높은 순으로 정렬
        sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def get_all_dates(self) -> list[str]:
        """저장된 모든 날짜.

        Returns:
            날짜 목록 (최신순)
        """
        path = self.index_dir / "by_date.yaml"
        data = self._load_yaml(path) or {}
        return sorted(data.keys(), reverse=True)

    def get_all_tags(self) -> list[str]:
        """저장된 모든 태그.

        Returns:
            태그 목록 (알파벳순)
        """
        path = self.index_dir / "by_tag.yaml"
        data = self._load_yaml(path) or {}
        return sorted(data.keys())

    def get_stats(self) -> dict:
        """인덱스 통계.

        Returns:
            통계 딕셔너리
        """
        by_date = self._load_yaml(self.index_dir / "by_date.yaml") or {}
        by_tag = self._load_yaml(self.index_dir / "by_tag.yaml") or {}
        by_score = self._load_yaml(self.index_dir / "by_score.yaml") or {}

        return {
            "total_dates": len(by_date),
            "total_papers_by_date": sum(len(v) for v in by_date.values()),
            "total_tags": len(by_tag),
            "total_scored_papers": len(by_score),
            "average_score": (
                sum(by_score.values()) / len(by_score) if by_score else 0
            ),
        }

    def _load_yaml(self, path: Path) -> Optional[dict]:
        """YAML 파일 로드."""
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _save_yaml(self, path: Path, data: dict) -> None:
        """YAML 파일 저장."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
