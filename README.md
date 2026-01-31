# Paper Digest Agent

> 매일 HuggingFace에서 LLM/Agent 관련 논문을 자동 수집하고, 트렌드를 파악하여 핵심 분석 리포트를 생성하는 에이전트

## 프로젝트 소개

**Paper Digest Agent**는 LangGraph 기반의 자동화된 연구 논문 분석 파이프라인입니다.

- **자동 논문 수집**: 매일 HuggingFace Daily Papers에서 LLM/Agent 관련 최신 논문을 수집합니다
- **LLM 기반 평가**: 실용성, 구현 가능성, 신뢰도를 기준으로 논문을 평가합니다
- **트렌드 감지**: 최근 연구 흐름과 핵심 변화점을 파악합니다
- **GitHub 코드 분석**: 논문의 공식 구현 코드를 분석하여 방법론과 매핑합니다
- **한글 리포트**: 모든 분석 결과를 한글로 제공합니다

## 핵심 원칙

### 정확성 가이드

이 프로젝트는 논문을 깊이 리뷰하기보다, **최근 연구 트렌드를 정확하게 감지**하는 것을 목표로 합니다.

**과장 표현 금지**
- ❌ "해결했다", "자동화했다", "보장한다", "최초다"
- ✅ "제안한다", "개선한다", "지원한다", "목표로 한다"

**확장 해석 금지**
- 논문이 직접 언급하지 않은 상위 해석을 추가하지 않습니다
- 반드시 논문에서 명시적으로 언급한 범위까지만 요약합니다

## 주요 기능

| 기능 | 설명 |
|------|------|
| 📚 논문 수집 (Skim) | HuggingFace Daily Papers에서 논문 수집 및 빠른 스크리닝 |
| 🎯 심층 분석 (Deep) | 실용성, 구현 가능성, 신뢰도 점수 산출 + Delta 분석 |
| 🔍 PDF 분석 | GROBID/PyMuPDF를 활용한 구조화된 PDF 파싱 |
| 💻 GitHub 분석 | 공식 코드 저장소 분석 및 방법론 매핑 |
| ✅ 검증 | 추출된 정보와 논문 주장의 일치 여부 검증 |
| 📝 Daily Report | 일일 통합 리포트 자동 생성 |

## MCP 서버 구성

이 프로젝트는 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 패턴을 활용하여 외부 서비스와의 통신을 모듈화합니다.

| MCP 서버 | 역할 | 설명 |
|----------|------|------|
| `HFPapersServer` | 논문 수집 | HuggingFace Daily Papers API에서 최신 논문 메타데이터 수집 |
| `GrobidServer` | PDF 구조화 파싱 | GROBID를 통해 PDF를 TEI-XML로 변환, 섹션/테이블/참고문헌 추출 |
| `PyMuPDFParser` | PDF 텍스트 추출 | GROBID 미사용 시 폴백, PyMuPDF로 기본 텍스트 추출 |

```
[Fetcher] ──→ HFPapersServer ──→ HuggingFace API
                                      │
                                      ▼
                              논문 메타데이터 (title, abstract, arxiv_id, upvotes)
                                      │
                                      ▼
[Parser] ───→ GrobidServer ────→ GROBID Docker
              (또는 PyMuPDFParser)     │
                                      ▼
                              구조화된 PDF (sections, tables, figures)
```

## 파이프라인 구조

### Orchestrator 전체 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR                                   │
│                     (비-LLM, 파이프라인 조율)                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ 1. SKIM       │           │ 2. DEEP       │           │ 3. CODE       │
│   Pipeline    │──────────▶│   Pipeline    │──────────▶│   Pipeline    │
│               │           │   (병렬)       │           │   (선택)       │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ papers/       │           │ reports/      │           │ reports/      │
│  skim.json    │           │  {slug}/      │           │  {slug}/      │
│               │           │   *.json      │           │   github.json │
└───────────────┘           └───────────────┘           └───────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ 4. DAILY      │
                            │   Report      │
                            └───────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ reports/daily │
                            │  YYYY-MM-DD.md│
                            └───────────────┘
```

### 각 파이프라인 상세

**1. Skim Pipeline** - 빠른 스크리닝
```
HFPapersServer ──▶ Fetcher ──▶ Gatekeeper ──▶ SkimAgent (LLM)
     │                              │               │
     ▼                              ▼               ▼
  API 호출             키워드/upvote 필터      관심도 점수 (1-5)
                                               카테고리 분류
```

**2. Deep Pipeline** - 심층 분석 + 자기 교정 루프 (LangGraph 핵심 활용)
```
┌─────────┐    ┌────────────┐    ┌───────────┐    ┌──────────┐
│  Parse  │───▶│ Extraction │───▶│   Delta   │───▶│ Scoring  │
│ (PDF)   │    │   (LLM)    │    │   (LLM)   │    │  (LLM)   │
└─────────┘    └────────────┘    └───────────┘    └──────────┘
                     ▲                                  │
                     │                                  ▼
                     │                          ┌──────────────┐
                     │                          │ Verification │
                     │                          │    (LLM)     │
                     │                          └──────────────┘
                     │                                  │
                     │         ┌────────────────────────┼────────────────────────┐
                     │         │                        │                        │
                     │    [high: 통과]           [medium/low: 재시도]      [max retry 초과]
                     │         │                        │                        │
                     │         ▼                        ▼                        │
                     │      Report               ┌────────────┐                  │
                     │                           │ Correction │                  │
                     │                           │   (LLM)    │                  │
                     │                           └────────────┘                  │
                     │                                  │                        │
                     └──────────── 수정된 결과 ─────────┘                        │
                                                                                 │
                                     ┌───────────────────────────────────────────┘
                                     ▼
                                  Report
```

**왜 LangGraph인가?**
- **조건부 분기**: Verification 결과에 따라 Report 또는 Correction으로 분기
- **자기 교정 루프**: Correction → Extraction → Delta → Scoring → Verification 재실행
- **상태 관리**: `retry_count`로 최대 재시도 횟수 제어 (기본 2회)

이 루프를 통해 과장된 표현이나 부정확한 정보가 자동으로 교정됩니다.

**3. Code Pipeline** - GitHub 코드 분석 (선택)
```
GitHub URL ──▶ GitHubMethodAgent (LLM) ──▶ 방법론-코드 매핑
                       │
                       ▼
              핵심 파일/함수 식별
              구현 패턴 분석
```

### 에이전트 구성

| 에이전트 | 역할 | LLM 사용 | 모델 |
|----------|------|:--------:|------|
| `Orchestrator` | 전체 파이프라인 조율 | ❌ | - |
| `Fetcher` | HuggingFace에서 논문 수집 | ❌ | - |
| `Gatekeeper` | 키워드/upvote 기반 필터링 | ❌ | - |
| `SkimAgent` | 빠른 스크리닝, 관심도 점수 | ✅ | gpt-4o-mini |
| `ExtractionAgent` | 논문 구조화 정보 추출 | ✅ | gpt-4o |
| `DeltaAgent` | 기존 연구 대비 차별점 분석 | ✅ | gpt-4o |
| `ScoringAgent` | 실용성/구현성/신뢰도 평가 | ✅ | gpt-4o-mini |
| `VerificationAgent` | 과장 표현 검증 | ✅ | gpt-4o-mini |
| `CorrectionAgent` | 검증 실패 시 수정 | ✅ | gpt-4o-mini |
| `GitHubMethodAgent` | GitHub 코드-방법론 매핑 | ✅ | gpt-4o |
| `DailyReportAgent` | 일일 통합 리포트 생성 | ❌ | - |

## 설치 방법

### 요구사항

- Python 3.10 이상
- Docker (GROBID 실행용, 선택)
- API 키: OpenAI (필수), LangSmith (선택)

### 설치

```bash
# 저장소 클론
git clone <repo-url>
cd paper-digest-agent

# 의존성 설치
pip install -e .

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

### GROBID 실행 (선택)

```bash
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.0
```

> GROBID가 없으면 PyMuPDF로 자동 폴백됩니다.

## 사용법

### 전체 파이프라인 실행

```bash
# 오늘 날짜로 전체 파이프라인 실행
python -m rtc.agents.orchestrator

# 특정 날짜로 실행
python -m rtc.agents.orchestrator --date 2026-01-31

# GitHub 코드 분석 포함
python -m rtc.agents.orchestrator --code

# 강제 재실행 (이미 처리된 논문도 다시 분석)
python -m rtc.agents.orchestrator --force
```

### 개별 파이프라인 실행

```bash
# Deep Pipeline만 실행 (단일 논문)
python -m rtc.pipeline.deep --arxiv-id "2601.20833" --title "Paper Title"

# Skim Pipeline만 실행
python -m rtc.pipeline.skim --date 2026-01-31
```

### 주요 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--date` | 실행 날짜 (YYYY-MM-DD) | 오늘 |
| `--deep` / `--no-deep` | Deep 분석 실행 여부 | True |
| `--code` | GitHub 코드 분석 포함 | False |
| `--force` | 강제 재실행 | False |

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 | (필수) |
| `LANGSMITH_API_KEY` | LangSmith API 키 | (선택) |
| `LANGSMITH_PROJECT` | LangSmith 프로젝트명 | `paper-digest-agent` |
| `GROBID_URL` | GROBID 서비스 URL | `http://localhost:8070` |
| `HF_TOKEN` | HuggingFace 토큰 | (선택) |

## 관심사 설정

논문 수집 및 필터링에 사용되는 키워드는 `src/rtc/config.py`에서 설정합니다.

### 주요 설정 항목

```python
# src/rtc/config.py

class Settings(BaseSettings):
    # HuggingFace Papers 필터링 키워드
    hf_papers_keywords: list[str] = [
        "LLM", "large language model", "agent", "RAG",
        "reasoning", "tool use", "function calling", ...
    ]

    # 우선순위 관심 키워드 (agent > rag > reasoning)
    interest_keywords: list[str] = [
        "agent", "agentic", "multi-agent", "tool use",
        "RAG", "retrieval", "reasoning", "chain of thought", ...
    ]

    # 카테고리 우선순위
    category_priority: list[str] = [
        "agent", "rag", "reasoning", "training", "evaluation", "other"
    ]

    # 하루 최대 심층 분석 논문 수
    max_deep_papers_per_day: int = 3

    # 심층 분석 임계값 (1-5점 중 4점 이상)
    skim_interest_threshold: int = 4
```

### 관심사 변경 방법

**방법 1: config.py 직접 수정**

```python
# src/rtc/config.py 수정

hf_papers_keywords: list[str] = Field(
    default=[
        # 원하는 키워드 추가/수정
        "multimodal",
        "vision language",
        "image generation",
        "diffusion",
        ...
    ],
    alias="HF_PAPERS_KEYWORDS",
)
```

**방법 2: 관심 분야 예시**

| 관심 분야 | 추천 키워드 |
|-----------|-------------|
| LLM Agent | `agent`, `agentic`, `multi-agent`, `tool use`, `function calling`, `ReAct` |
| RAG | `RAG`, `retrieval`, `retrieval augmented`, `knowledge base`, `vector` |
| 추론 | `reasoning`, `chain of thought`, `CoT`, `planning`, `problem solving` |
| 멀티모달 | `multimodal`, `vision language`, `VLM`, `image`, `video` |
| 코드 생성 | `code generation`, `programming`, `software engineering`, `code LLM` |
| 파인튜닝 | `fine-tuning`, `RLHF`, `DPO`, `instruction tuning`, `alignment` |

### 필터링 조건 변경

```python
# 최소 upvote 수 (HuggingFace Papers)
hf_papers_min_votes: int = 5  # 기본값: 5

# 검색 기간 (일)
hf_papers_lookback_days: int = 1  # 기본값: 1일

# 하루 최대 심층 분석 수
max_deep_papers_per_day: int = 3  # 기본값: 3편
```

## 프로젝트 구조

```
paper-digest-agent/
├── src/rtc/
│   ├── config.py              # 설정 관리
│   ├── schemas/               # Pydantic 데이터 모델
│   │   ├── skim.py            # 스킴 스키마
│   │   ├── extraction_v2.py   # 추출 스키마
│   │   ├── delta_v2.py        # 차별점 스키마
│   │   ├── scoring_v2.py      # 점수 스키마
│   │   └── github_method.py   # GitHub 분석 스키마
│   ├── agents/                # 에이전트 구현
│   │   ├── orchestrator.py    # 전체 조율
│   │   ├── extraction.py      # 정보 추출
│   │   ├── delta_agent.py     # 차별점 분석
│   │   ├── scoring_agent.py   # 점수 평가
│   │   ├── verification_agent.py  # 검증
│   │   ├── correction_agent.py    # 수정
│   │   ├── github_method_agent.py # GitHub 분석
│   │   └── daily_report_agent.py  # 일일 리포트
│   ├── pipeline/              # LangGraph 파이프라인
│   │   ├── skim.py            # 스킴 파이프라인
│   │   ├── deep.py            # 심층 분석 파이프라인
│   │   └── code.py            # 코드 분석 파이프라인
│   ├── mcp/servers/           # MCP 서버
│   │   ├── hf_papers_server.py # HuggingFace Papers
│   │   ├── grobid_server.py   # GROBID API
│   │   └── pymupdf_parser.py  # PyMuPDF 파서
│   ├── llm/                   # LLM 클라이언트
│   │   ├── openai.py          # OpenAI 클라이언트
│   │   └── claude.py          # Claude 클라이언트
│   ├── storage/               # 저장소
│   │   ├── skim_store.py      # 스킴 결과 저장
│   │   ├── deep_store.py      # 심층 분석 결과 저장
│   │   ├── code_store.py      # 코드 분석 결과 저장
│   │   └── report_store.py    # 리포트 저장
│   └── tracing/               # LangSmith 트레이싱
├── reports/                   # 생성된 리포트
│   ├── daily/                 # 일일 통합 리포트
│   └── {paper-slug}/          # 개별 논문 리포트
├── index/                     # 인덱스 파일
└── papers/                    # 다운로드된 PDF
```

## 출력 예시

### Daily Report

```markdown
# 2026-01-31 Daily Paper Report

> 이 리포트는 논문을 상세히 분석하기 위한 것이 아니라,
> 최근 연구 흐름을 빠르게 파악하기 위한 데일리 요약입니다.

## 📚 오늘의 논문 (3편)

### 1. Paper Title ⭐⭐⭐⭐ [GitHub ✓]

**arXiv**: [2601.xxxxx](https://arxiv.org/abs/2601.xxxxx)

## 왜 이 논문인가?
총점: 11/15
- 실용성: 4/5
- 구현 가능성: 3/5
- 신뢰도: 4/5

## 한 줄 요약
이 논문은 [기존 방법]의 [한계]를 [새로운 접근법]을 통해 개선한다.

## 차별점 (Delta)
- [기존: ...] → [변경: ...]

...
```

### 개별 논문 리포트

각 논문별로 `reports/{paper-slug}/` 폴더에 다음 파일이 생성됩니다:

- `extraction.json` - 구조화된 정보 추출 결과
- `delta.json` - 차별점 분석 결과
- `scoring.json` - 점수 평가 결과
- `verification.json` - 검증 결과
- `deep.md` - 마크다운 리포트

## 개발

```bash
# 개발 의존성 설치
pip install -e ".[dev]"

# 테스트 실행
pytest

# 코드 포맷팅
ruff format .

# 린트 검사
ruff check .
```

## 라이선스

MIT
