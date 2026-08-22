"""Ranking 스키마 정의 - 상대 순위 기반 deep 후보 선별."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

RankingMethod = Literal["llm", "fallback"]


class RankedPaper(BaseModel):
    """단일 논문의 순위와 이유.

    상위(선정) 논문은 선정 이유를, 나머지는 탈락 사유를 담습니다.
    """

    arxiv_id: str
    rank: int = Field(..., ge=1, description="1이 최상위")
    reason: str = Field(..., description="순위 근거 (한국어 1-2문장)")


class RankingOutput(BaseModel):
    """RankingAgent의 LLM 구조화 출력."""

    ranked: list[RankedPaper] = Field(default_factory=list)


class RankingResult(BaseModel):
    """RankingAgent 최종 결과.

    ``method``가 ``"fallback"``이면 ``ranked``는 비어 있고, 호출자는 기존
    gatekeeper 선별을 그대로 유지해야 합니다.
    """

    ranked: list[RankedPaper] = Field(default_factory=list)
    method: RankingMethod = "fallback"
    error: Optional[str] = Field(default=None, description="폴백 사유")

    @property
    def ok(self) -> bool:
        """LLM 순위가 건전성 검사까지 통과했는가."""
        return self.method == "llm" and bool(self.ranked)

    def top_ids(self, limit: int) -> list[str]:
        """상위 ``limit``개 arxiv_id (순위 오름차순)."""
        return [p.arxiv_id for p in sorted(self.ranked, key=lambda p: p.rank)][:limit]
