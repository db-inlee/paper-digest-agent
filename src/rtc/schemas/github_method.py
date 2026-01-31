"""GitHub Method 스키마 - 논문 방법론의 GitHub 구현 매핑."""

from typing import Optional

from pydantic import BaseModel, Field

from rtc.schemas.extraction_v2 import Evidence


class MethodImplementation(BaseModel):
    """방법론 구현 정보."""

    method_name: str = Field(..., description="방법론 이름 (논문에서)")
    description: str = Field(..., description="방법론 설명 (한국어)")

    # GitHub 구현 위치
    file_path: str = Field(..., description="파일 경로 (예: src/agent/react.py)")
    class_or_function: str = Field(..., description="클래스/함수 이름")
    line_start: Optional[int] = Field(default=None, description="시작 라인")
    line_end: Optional[int] = Field(default=None, description="끝 라인")

    # 핵심 코드
    key_code: str = Field(..., description="핵심 구현 코드 스니펫")
    code_explanation: str = Field(..., description="코드 설명 (한국어)")

    # 논문 연결 - 강화
    paper_section: str = Field(
        default="", description="논문의 해당 섹션 (예: Section 3.2, Algorithm 1)"
    )
    paper_formula: Optional[str] = Field(
        default=None, description="구현하는 수식 (예: Eq. 5의 attention score 계산)"
    )
    paper_evidence: Optional[Evidence] = Field(
        default=None, description="논문 내 근거"
    )

    # 코드 품질 메타
    implementation_type: str = Field(
        default="core",
        description="구현 유형: core(핵심 알고리즘), wrapper(래퍼), utility(유틸리티), config(설정)"
    )
    has_actual_logic: bool = Field(
        default=True,
        description="실제 로직이 있는지 (False면 placeholder/stub)"
    )

    # 추가 정보
    dependencies: list[str] = Field(
        default_factory=list, description="사용된 라이브러리"
    )
    notes: Optional[str] = Field(default=None, description="구현 관련 노트")


class GitHubMethodOutput(BaseModel):
    """GitHubMethodAgent 출력."""

    arxiv_id: str = Field(..., description="arXiv ID")
    repo_url: str = Field(..., description="GitHub 레포 URL")
    repo_description: str = Field(..., description="레포 설명")

    # 레포 구조
    main_language: str = Field(default="Python", description="주 언어")
    structure_summary: str = Field(..., description="프로젝트 구조 요약")

    # 방법론 구현 매핑
    methods: list[MethodImplementation] = Field(
        default_factory=list, description="방법론별 구현"
    )

    # 메타
    total_methods_found: int = Field(default=0, description="찾은 방법론 수")
    unmapped_methods: list[str] = Field(
        default_factory=list, description="구현을 찾지 못한 방법론"
    )

    # 사용법
    installation: str = Field(default="", description="설치 방법")
    usage_example: str = Field(default="", description="사용 예시")

    @property
    def has_implementations(self) -> bool:
        """구현이 있는지 여부."""
        return len(self.methods) > 0
