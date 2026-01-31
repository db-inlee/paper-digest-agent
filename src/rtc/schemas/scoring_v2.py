"""Scoring 스키마 v2 - 단순화된 구조."""

from typing import Literal

from pydantic import BaseModel, Field


class ScoringOutput(BaseModel):
    """Scoring Agent 출력 - scoring.json 스키마.

    총점 15점 체계:
    - practicality: 0-5 (실용성)
    - codeability: 0-5 (구현 가능성)
    - signal: 0-5 (결과 신뢰도)

    추천 등급:
    - must_read: total >= 12
    - worth_reading: total >= 8
    - skip: total < 8
    """

    arxiv_id: str = Field(..., description="arXiv ID")

    # 점수 (각 0-5, 총 15점)
    practicality: int = Field(
        ...,
        ge=0,
        le=5,
        description="실용성: 실제 문제 해결 가능성 (0-5)",
    )
    codeability: int = Field(
        ...,
        ge=0,
        le=5,
        description="구현 가능성: 코드로 만들기 쉬운 정도 (0-5)",
    )
    signal: int = Field(
        ...,
        ge=0,
        le=5,
        description="신뢰도: 결과/주장의 근거 강도 (0-5)",
    )

    # 추천
    recommendation: Literal["must_read", "worth_reading", "skip"] = Field(
        ..., description="추천 등급"
    )
    reasoning: str = Field(..., description="점수 판단 근거 (한국어)")

    # 추가 정보
    key_strength: str = Field(..., description="주요 강점")
    main_concern: str = Field(default="", description="주요 우려 사항")

    @property
    def total(self) -> int:
        """총점 (최대 15점)."""
        return self.practicality + self.codeability + self.signal

    @classmethod
    def get_recommendation_from_score(cls, total: int) -> Literal["must_read", "worth_reading", "skip"]:
        """총점으로부터 추천 등급 결정."""
        if total >= 12:
            return "must_read"
        elif total >= 8:
            return "worth_reading"
        else:
            return "skip"

    def model_post_init(self, __context) -> None:
        """모델 초기화 후 추천 등급 검증."""
        expected = self.get_recommendation_from_score(self.total)
        if self.recommendation != expected:
            # 자동 수정하지 않고 경고만 (LLM 출력 존중)
            pass


# 점수 기준 상수
SCORE_THRESHOLD_MUST_READ = 12
SCORE_THRESHOLD_WORTH_READING = 8


# 점수 설명
SCORING_CRITERIA = {
    "practicality": {
        0: "순수 이론, 실용적 가치 없음",
        1: "잠재적 응용 가능성 있음",
        2: "일부 실용적 응용 가능",
        3: "명확한 실용적 응용 가능",
        4: "즉시 적용 가능, 실제 문제 해결",
        5: "혁신적 실용성, 게임체인저",
    },
    "codeability": {
        0: "구현 불가능 수준의 복잡도",
        1: "전문 인프라 필요, 매우 복잡",
        2: "상당한 전문성 필요",
        3: "중간 복잡도, 구현 가능",
        4: "명확한 알고리즘, 쉬운 구현",
        5: "즉시 구현 가능, 코드 제공됨",
    },
    "signal": {
        0: "결과 없거나 신뢰 불가",
        1: "약한 결과, 불명확",
        2: "일부 제한적 결과",
        3: "합리적 결과, 일부 한계",
        4: "강력한 결과, 잘 뒷받침됨",
        5: "매우 강력한 결과, 완벽한 근거",
    },
}
