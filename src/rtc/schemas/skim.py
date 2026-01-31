"""Skim Pipeline 스키마 정의."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SkimSummary(BaseModel):
    """Ultra-Skim 결과 (단일 논문)."""

    arxiv_id: str
    title: str
    one_liner: str = Field(..., description="한 줄 요약 (한국어)")
    tags: list[str] = Field(default_factory=list, description="키워드 태그")
    interest_score: int = Field(..., ge=1, le=5, description="관심도 점수 1-5")
    interest_reason: str = Field(..., description="관심도 판단 근거")
    baseline_mentioned: Optional[str] = Field(
        default=None, description="언급된 주요 베이스라인"
    )
    category: Literal["agent", "rag", "reasoning", "training", "evaluation", "other"] = Field(
        ..., description="논문 카테고리"
    )
    has_code: bool = Field(default=False, description="코드 공개 여부")
    link: str = Field(..., description="논문 링크 (arxiv 또는 github)")
    # GitHub 정보
    github_url: Optional[str] = Field(default=None, description="GitHub 레포 URL")
    github_stars: Optional[int] = Field(default=None, description="GitHub 스타 수")


class BatchSkimResult(BaseModel):
    """배치 스킴 결과."""

    papers: list[SkimSummary]
    skimmed_at: datetime = Field(default_factory=datetime.now)
    total_processed: int = 0
    errors: list[str] = Field(default_factory=list)


class DailySkimOutput(BaseModel):
    """papers/YYYY-MM-DD.yaml 스키마."""

    date: str = Field(..., description="YYYY-MM-DD 형식")
    total_collected: int = Field(..., description="수집된 전체 논문 수")
    total_skimmed: int = Field(..., description="스킴 완료된 논문 수")
    papers: list[SkimSummary] = Field(default_factory=list)
    deep_candidates: list[str] = Field(
        default_factory=list, description="Deep 분석 대상 arxiv_ids"
    )
    skimmed_at: datetime = Field(default_factory=datetime.now)


class SkimConfig(BaseModel):
    """Skim Pipeline 설정."""

    batch_size: int = Field(default=10, description="배치당 논문 수")
    interest_threshold: int = Field(default=4, description="Deep 분석 임계 점수")
    max_deep_papers: int = Field(default=3, description="하루 최대 Deep 분석 수")
