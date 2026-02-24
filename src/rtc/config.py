"""Configuration management for Paper Digest Agent."""

import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")

    # LangSmith
    langsmith_project: str = Field(default="paper-digest-agent", alias="LANGSMITH_PROJECT")
    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")

    # LLM Provider
    llm_provider: Literal["claude", "openai"] = Field(default="claude", alias="LLM_PROVIDER")
    llm_model_claude: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL_CLAUDE")
    llm_model_openai: str = Field(default="gpt-4o", alias="LLM_MODEL_OPENAI")

    # GROBID
    grobid_url: str = Field(default="http://localhost:8070", alias="GROBID_URL")

    # Output Language
    output_language: str = Field(
        default="ko",
        alias="OUTPUT_LANGUAGE",
        description="Output language for reports: 'ko' (Korean) or 'en' (English)",
    )

    # Paper Source
    paper_source: Literal["hf_papers", "arxiv"] = Field(
        default="hf_papers",
        alias="PAPER_SOURCE",
        description="Paper source: 'hf_papers' (Hugging Face Daily Papers) or 'arxiv'",
    )

    # Hugging Face Papers
    hf_papers_min_votes: int = Field(
        default=5,
        alias="HF_PAPERS_MIN_VOTES",
        description="Minimum upvotes to filter papers (0 for no filter)",
    )
    hf_papers_lookback_days: int = Field(
        default=1,
        alias="HF_PAPERS_LOOKBACK_DAYS",
    )
    hf_papers_keywords: list[str] = Field(
        default=[
            # LLM 기본
            "LLM",
            "large language model",
            "language model",
            # Agent
            "agent",
            "agentic",
            "multi-agent",
            "autonomous",
            # RAG
            "RAG",
            "retrieval",
            "retrieval augmented",
            # 추론/계획
            "reasoning",
            "planning",
            "chain of thought",
            "CoT",
            # 도구/함수
            "tool use",
            "function calling",
            "tool learning",
            # 기타
            "ReAct",
            "prompt",
            "fine-tuning",
            "RLHF",
            "instruction",
        ],
        alias="HF_PAPERS_KEYWORDS",
        description="Keywords to filter HF papers (case-insensitive, matches title or abstract)",
    )

    # Interest Keywords (우선순위별 관심 키워드)
    interest_keywords: list[str] = Field(
        default=[
            # LLM Agent (최우선)
            "agent",
            "agentic",
            "multi-agent",
            "tool use",
            "function calling",
            "ReAct",
            "autonomous",
            # RAG
            "RAG",
            "retrieval",
            "retrieval augmented",
            "knowledge base",
            # 추론/계획
            "reasoning",
            "chain of thought",
            "CoT",
            "planning",
            "problem solving",
        ],
        alias="INTEREST_KEYWORDS",
        description="Priority keywords for filtering papers (agent > rag > reasoning)",
    )

    # Category Priority (카테고리 우선순위)
    category_priority: list[str] = Field(
        default=["agent", "rag", "reasoning", "training", "evaluation", "other"],
        alias="CATEGORY_PRIORITY",
        description="Category priority order for filtering papers",
    )

    # arXiv
    arxiv_categories: list[str] = Field(
        default=["cs.LG", "cs.CL", "cs.AI", "cs.CV"],
        alias="ARXIV_CATEGORIES",
    )
    arxiv_keywords: list[str] = Field(
        default=[
            "LLM",
            "large language model",
            "agent",
            "AI agent",
            "autonomous agent",
            "RAG",
            "retrieval augmented generation",
            "tool use",
            "function calling",
            "reasoning",
            "planning",
            "chain of thought",
            "ReAct",
            "multi-agent",
            "agentic",
        ],
        alias="ARXIV_KEYWORDS",
    )
    arxiv_max_results: int = Field(default=100, alias="ARXIV_MAX_RESULTS")
    arxiv_lookback_days: int = Field(default=7, alias="ARXIV_LOOKBACK_DAYS")

    # Skim Pipeline Settings
    skim_batch_size: int = Field(
        default=10,
        alias="SKIM_BATCH_SIZE",
        description="Number of papers to process in a single LLM call",
    )
    skim_interest_threshold: int = Field(
        default=4,
        alias="SKIM_INTEREST_THRESHOLD",
        description="Minimum interest score (1-5) for deep analysis",
    )
    max_deep_papers_per_day: int = Field(
        default=3,
        alias="MAX_DEEP_PAPERS_PER_DAY",
        description="Maximum number of papers for deep analysis per day",
    )

    # Venue/Conference Filter
    venue_filter_enabled: bool = Field(default=False, alias="VENUE_FILTER_ENABLED")
    venue_filter_conferences: list[str] = Field(
        default=[
            "NeurIPS", "NIPS", "ICML", "ICLR",
            "ACL", "EMNLP", "NAACL",
            "AAAI", "IJCAI",
            "CVPR", "ICCV", "ECCV",
            "KDD", "WWW", "SIGIR",
        ],
        alias="VENUE_FILTER_CONFERENCES",
    )
    venue_filter_mode: Literal["only", "boost"] = Field(
        default="boost",
        alias="VENUE_FILTER_MODE",
        description="'only': 학회 논문만 통과, 'boost': 학회 논문 우선 표시 (matched_keywords에 학회명 추가)",
    )

    # GitHub Method Analysis
    analyze_github: bool = Field(
        default=False,
        alias="ANALYZE_GITHUB",
        description="Whether to analyze GitHub repositories for papers",
    )

    # Agent-specific model settings
    agent_models: dict[str, str] = Field(
        default={
            "skim": "gpt-4o-mini",
            "scoring": "gpt-4o-mini",
            "extraction": "gpt-4o",
            "delta": "gpt-4o",
            "verification": "gpt-4o-mini",
            "correction": "gpt-4o-mini",
            "github_method": "gpt-4o",
        },
        alias="AGENT_MODELS",
        description="에이전트별 OpenAI 모델 설정",
    )

    # Timezone
    scheduler_timezone: str = Field(default="Asia/Seoul", alias="SCHEDULER_TIMEZONE")

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    report_base_dir: Optional[Path] = Field(default=None, alias="REPORT_BASE_DIR")

    @property
    def papers_dir(self) -> Path:
        """papers/ 디렉토리 (스킴 결과 저장)."""
        return self.base_dir / "papers"

    @property
    def reports_dir(self) -> Path:
        """reports/ 디렉토리 (딥 분석 결과 저장)."""
        if self.report_base_dir is not None:
            return self.report_base_dir
        return self.base_dir / "reports"

    @property
    def index_dir(self) -> Path:
        """index/ 디렉토리 (인덱스 저장)."""
        return self.base_dir / "index"

    def get_effective_hf_keywords(self) -> list[str]:
        """topics.json 반영: disabled 제외 + custom 추가 + 중복 제거."""
        import json

        topics_path = self.reports_dir / "topics.json"
        if not topics_path.exists():
            return self.hf_papers_keywords

        try:
            data = json.loads(topics_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self.hf_papers_keywords

        disabled_lower = {
            d.lower() for d in data.get("disabled_default_keywords", [])
        }
        result = [
            kw for kw in self.hf_papers_keywords
            if kw.lower() not in disabled_lower
        ]
        existing_lower = {kw.lower() for kw in result}

        for entry in data.get("custom_keywords", []):
            kw = entry.get("keyword", "")
            if kw and kw.lower() not in existing_lower:
                result.append(kw)
                existing_lower.add(kw.lower())

        return result

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
