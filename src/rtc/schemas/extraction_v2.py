"""Extraction 스키마 v2 - Evidence 포함."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """근거 정보."""

    page: Optional[int] = Field(default=None, description="페이지 번호")
    section: Optional[str] = Field(default=None, description="섹션 이름")
    quote: Optional[str] = Field(default=None, description="인용문")
    type: Literal["quote", "table", "figure", "equation"] = Field(
        default="quote", description="근거 유형"
    )

    def to_pointer(self) -> str:
        """Evidence pointer 문자열 생성."""
        parts = []
        if self.page:
            parts.append(f"p.{self.page}")
        if self.section:
            parts.append(f"§{self.section}")
        return f"(Evidence: {' '.join(parts)})" if parts else ""


class ProblemDefinition(BaseModel):
    """문제 정의."""

    statement: str = Field(..., description="문제 설명")
    baseline_methods: list[str] = Field(
        default_factory=list, description="기존 방법들"
    )
    structural_limitation: str = Field(..., description="기존 방법의 구조적 한계")
    evidence: list[Evidence] = Field(default_factory=list)


class BaselineWithEvidence(BaseModel):
    """베이스라인 정보 (Evidence 포함)."""

    name: str = Field(..., description="베이스라인 이름")
    description: str = Field(..., description="베이스라인 설명")
    limitation: str = Field(..., description="한계점")
    evidence: list[Evidence] = Field(default_factory=list)


class MethodComponent(BaseModel):
    """방법론 구성 요소."""

    name: str = Field(..., description="구성 요소 이름 (예: Multi-Head Attention)")
    description: str = Field(
        ...,
        description="상세 설명 - 이 구성 요소가 무엇이고 어떻게 작동하는지 2-3문장으로 기술",
    )
    inputs: list[str] = Field(default_factory=list, description="입력 (예: Query, Key, Value)")
    outputs: list[str] = Field(default_factory=list, description="출력 (예: 어텐션 가중치 적용된 Value)")
    implementation_hint: Optional[str] = Field(
        default=None,
        description="구현 힌트 - 핵심 수식이나 알고리즘 단계 요약",
    )
    role: Optional[str] = Field(
        default=None,
        description="이 구성 요소의 역할 (novel: 새로운 기여, adapted: 기존 기법 변형, standard: 표준 기법 활용)",
    )
    evidence: list[Evidence] = Field(default_factory=list)


class BenchmarkInfo(BaseModel):
    """벤치마크 정보."""

    dataset: str = Field(..., description="데이터셋 이름")
    metrics: list[str] = Field(default_factory=list, description="평가 지표")
    baseline_results: dict[str, str] = Field(
        default_factory=dict, description="베이스라인 결과"
    )
    proposed_results: dict[str, str] = Field(
        default_factory=dict, description="제안 방법 결과"
    )
    evidence: list[Evidence] = Field(default_factory=list)


class ClaimWithEvidence(BaseModel):
    """클레임 (Evidence 포함)."""

    claim_id: str = Field(..., description="클레임 ID")
    text: str = Field(..., description="클레임 내용")
    claim_type: Literal[
        "method", "result", "comparison", "limitation",
        "architecture", "efficiency", "ablation",
    ] = Field(
        ..., description="클레임 유형"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="신뢰도"
    )
    evidence: list[Evidence] = Field(default_factory=list)


class ExtractionOutput(BaseModel):
    """Extraction Agent 출력 - extraction.json 스키마."""

    arxiv_id: str = Field(..., description="arXiv ID")
    title: str = Field(..., description="논문 제목")
    problem_definition: ProblemDefinition = Field(..., description="문제 정의")
    baselines: list[BaselineWithEvidence] = Field(
        default_factory=list, description="베이스라인 목록"
    )
    method_components: list[MethodComponent] = Field(
        default_factory=list,
        min_length=2,
        description="방법론 구성 요소 (최소 2개 이상, 각 모듈/기법을 개별 항목으로 분리)",
    )
    benchmarks: list[BenchmarkInfo] = Field(
        default_factory=list, description="벤치마크 정보 목록 (여러 벤치마크 지원)"
    )
    # 하위 호환성: 기존 단일 benchmark 필드도 허용
    benchmark: Optional[BenchmarkInfo] = Field(
        default=None, description="(deprecated) 단일 벤치마크 - benchmarks 사용 권장",
    )
    claims: list[ClaimWithEvidence] = Field(
        default_factory=list, description="주요 클레임"
    )
    extraction_mode: Literal["full", "lite"] = Field(
        default="full", description="추출 모드"
    )

    @property
    def all_benchmarks(self) -> list[BenchmarkInfo]:
        """모든 벤치마크 반환 (benchmarks + 레거시 benchmark 통합)."""
        result = list(self.benchmarks)
        if self.benchmark and self.benchmark not in result:
            result.append(self.benchmark)
        return result

    @property
    def total_claims(self) -> int:
        """총 클레임 수."""
        return len(self.claims)

    @property
    def claims_with_evidence(self) -> int:
        """Evidence가 있는 클레임 수."""
        return sum(1 for c in self.claims if c.evidence)

    @property
    def evidence_coverage(self) -> float:
        """Evidence 커버리지."""
        if not self.claims:
            return 0.0
        return self.claims_with_evidence / self.total_claims
