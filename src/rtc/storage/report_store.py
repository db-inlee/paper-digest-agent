"""ReportStore - reports/daily/ 저장 관리."""

from datetime import datetime
from pathlib import Path
from typing import Optional


class ReportStore:
    """reports/daily/ 디렉토리 저장 관리.

    구조:
    - reports/daily/2026-01-31.md: 일일 통합 리포트
    """

    def __init__(self, base_dir: Path):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리
        """
        self.daily_dir = base_dir / "reports" / "daily"
        self.daily_dir.mkdir(parents=True, exist_ok=True)

    def get_report_path(self, date: str) -> Path:
        """일일 리포트 파일 경로.

        Args:
            date: 날짜 (YYYY-MM-DD)

        Returns:
            리포트 파일 경로
        """
        return self.daily_dir / f"{date}.md"

    def save_daily_report(self, date: str, markdown: str) -> Path:
        """일일 리포트 저장.

        Args:
            date: 날짜 (YYYY-MM-DD)
            markdown: 마크다운 내용

        Returns:
            저장된 파일 경로
        """
        path = self.get_report_path(date)
        path.write_text(markdown, encoding="utf-8")
        return path

    def load_daily_report(self, date: str) -> Optional[str]:
        """일일 리포트 로드.

        Args:
            date: 날짜 (YYYY-MM-DD)

        Returns:
            마크다운 내용 또는 None
        """
        path = self.get_report_path(date)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def report_exists(self, date: str) -> bool:
        """일일 리포트 존재 여부.

        Args:
            date: 날짜 (YYYY-MM-DD)

        Returns:
            존재 여부
        """
        return self.get_report_path(date).exists()

    def list_reports(self, limit: int = 30) -> list[str]:
        """저장된 일일 리포트 목록 (최신순).

        Args:
            limit: 최대 개수

        Returns:
            날짜 목록 (YYYY-MM-DD)
        """
        reports = []
        for path in sorted(self.daily_dir.glob("*.md"), reverse=True):
            if path.stem and len(path.stem) == 10:  # YYYY-MM-DD format
                reports.append(path.stem)
                if len(reports) >= limit:
                    break
        return reports

    def get_latest_report_date(self) -> Optional[str]:
        """가장 최근 리포트 날짜.

        Returns:
            날짜 (YYYY-MM-DD) 또는 None
        """
        reports = self.list_reports(limit=1)
        return reports[0] if reports else None
