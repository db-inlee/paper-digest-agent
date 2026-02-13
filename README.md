# Paper Digest Agent

> 매일 쏟아지는 AI 논문, 자동으로 분석하고 골라보세요.

**Paper Digest Agent**는 HuggingFace Daily Papers에서 LLM/Agent 관련 논문을 매일 자동으로 수집하고 분석해주는 도구입니다. 혼자 쓸 수도 있고, Slack을 연동하면 팀원들과 투표·댓글로 함께 의사결정할 수 있습니다.

- AI가 논문의 실용성·구현 가능성·신뢰도를 평가하고 한글 리포트를 생성합니다
- 웹 대시보드에서 분석 결과 확인, 투표, 댓글, 논문 수동 추가가 가능합니다
- Slack 연동(선택)으로 팀원들과 투표·댓글 협업을 할 수 있습니다

---

## 빠른 시작

Docker만 있으면 바로 시작할 수 있습니다.

```bash
git clone https://github.com/db-inlee/paper-digest-agent.git
cd paper-digest-agent
cp .env.example .env   # API 키 입력
docker-compose up --build
```

`.env` 파일에 LLM API 키를 입력합니다.

```bash
# 필수 - 논문 분석용 (둘 중 하나)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

http://localhost:8000 에서 웹 대시보드에 접속할 수 있습니다.

> API 키는 `.env` 파일에만 저장되며, `.gitignore`에 포함되어 Git에 커밋되지 않습니다.

여기까지가 공통 설정입니다. 이후는 사용 방식에 따라 다릅니다.

---

## 개인 사용

Slack 없이, 웹 대시보드만으로 모든 기능을 사용할 수 있습니다.

### 웹 대시보드

| 탭 | 설명 |
|----|------|
| **논문 보기** | 날짜별 분석 리포트 열람, 투표, 댓글 |
| **논문 추가** | arXiv URL을 입력하면 즉시 분석이 시작됩니다 |
| **관심사 설정** | 논문 수집에 사용할 키워드를 관리합니다 |

### 논문 분석 실행

논문 분석을 실행하는 방법은 3가지입니다.

**방법 A: 매일 자동 실행 (스케줄러)**

`.env`에서 스케줄러를 켜면, 매일 아침 지정한 시각에 자동으로 실행됩니다.

```bash
# .env
SCHEDULER_ENABLED=true       # 자동 실행 켜기
SCHEDULER_CRON_HOUR=9        # 매일 오전 9시 (KST)
SCHEDULER_TIMEZONE=Asia/Seoul
```

```
매일 09:00 (스케줄러)
    │
    ├──→ 논문 수집 (HuggingFace)
    ├──→ LLM 분석 (스크리닝 → 심층 분석 → 검증)
    └──→ 리포트 생성 → 웹 대시보드에서 확인
```

Docker 서버가 실행 중이기만 하면 별도 조작 없이 매일 자동으로 동작합니다.

**방법 B: 웹 대시보드에서 논문 추가**

"논문 추가" 탭에서 arXiv URL을 입력하면 해당 논문만 즉시 분석합니다.

**방법 C: 수동 실행**

```bash
docker-compose exec paper-digest python -m rtc.agents.orchestrator                    # 오늘 날짜
docker-compose exec paper-digest python -m rtc.agents.orchestrator --date 2026-01-31  # 특정 날짜
```

---

## 팀 사용 (Slack 연동)

Slack을 연동하면 팀원들이 Slack 채널에서 바로 투표·댓글할 수 있고, 웹 대시보드도 함께 공유됩니다.

### 추가로 필요한 것

| 항목 | 설명 |
|------|------|
| **Slack App** | 팀 워크스페이스에 Slack App을 만들어 연동합니다 |
| **ngrok** | 서버를 외부에 공개하여 팀원 접속 + Slack 버튼이 동작하게 합니다 |

### 1단계: `.env`에 Slack 키 추가

```bash
# Slack 연동
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_SIGNING_SECRET=your_signing_secret
SLACK_BOT_TOKEN=xoxb-your-bot-token
```

### 2단계: ngrok으로 서버 공개

[ngrok](https://ngrok.com/)을 사용하면 무료로 간단하게 서버를 외부에 공개할 수 있습니다.

```bash
# ngrok 설치 후 회원가입 (https://ngrok.com/download)
# 무료 고정 도메인 발급 (https://dashboard.ngrok.com/domains)

ngrok http 8000 --url your-team.ngrok-free.app
```

ngrok 무료 계정에는 **고정 도메인 1개**가 포함되어 있어 URL이 바뀌지 않습니다.
이 URL로 두 가지를 설정합니다:

1. **Slack App의 Request URL**로 설정 → Slack 투표·댓글 버튼이 동작합니다
2. **팀원에게 URL 공유** → 팀원이 웹 대시보드에 접속하여 상세 분석 결과를 볼 수 있습니다

```
나 (localhost:8000) ────────┐
팀원 A (ngrok URL) ─────────┤
팀원 B (ngrok URL) ─────────┼──→ 같은 Docker 컨테이너 (같은 데이터)
Slack 투표/댓글 (ngrok URL) ┘
```

`localhost:8000`과 ngrok URL은 같은 서버에 연결됩니다.
Slack에서 투표한 내용이 웹에 보이고, 웹에서 쓴 댓글이 Slack 스레드에 달립니다.

> **데이터는 안전하게 보존됩니다.** 투표, 댓글, 리포트는 Docker 볼륨(`./reports/`)에 저장되므로
> ngrok을 재시작하거나 PC를 껐다 켜도 데이터가 유지됩니다.
> 단, Docker 서버가 꺼져 있는 동안에는 접속과 Slack 버튼이 동작하지 않습니다.

### 3단계: Slack App 설정

<details>
<summary>Slack App 설정 방법 (4단계)</summary>

#### 1. Slack App 생성

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. App 이름과 워크스페이스를 지정합니다

#### 2. Incoming Webhooks

1. **Incoming Webhooks** → On
2. **Add New Webhook to Workspace** → 채널 선택
3. 생성된 Webhook URL을 `.env`의 `SLACK_WEBHOOK_URL`에 입력합니다

#### 3. Interactivity (투표·댓글 버튼)

1. **Interactivity & Shortcuts** → On
2. **Request URL**에 ngrok URL을 입력합니다: `https://your-team.ngrok-free.app/slack/interactions`
3. **Basic Information** → **Signing Secret**을 `.env`의 `SLACK_SIGNING_SECRET`에 입력합니다

#### 4. Bot Token (댓글 스레드 + 닉네임 연동)

1. **OAuth & Permissions** → **Bot Token Scopes**에 다음을 추가합니다:
   - `chat:write` — 댓글 스레드 전송
   - `commands` — 슬래시 커맨드
   - `users:read` — 웹 대시보드에서 Slack 닉네임 자동 연동
2. **Install to Workspace** → 생성된 Bot Token을 `.env`의 `SLACK_BOT_TOKEN`에 입력합니다
3. Slack 채널에서 `/invite @봇이름`을 실행합니다 (댓글 스레드 전송에 필요)

</details>

### Slack에서 할 수 있는 것

논문 리포트가 Slack 채널에 전송되면, 팀원들은 버튼으로 바로 투표하고 댓글을 남길 수 있습니다.
댓글은 해당 리포트 메시지의 **스레드**에 자동으로 달리며, 웹 대시보드에도 동시에 반영됩니다.

```
Slack 채널                          웹 대시보드
┌──────────────────┐
│ 📊 Daily Report  │
│ 논문1 [투표][댓글]│ ──투표──→  투표 현황 실시간 반영
│ 논문2 [투표][댓글]│
│  └─ 스레드 댓글   │ ──댓글──→  댓글 섹션에 동시 표시
│     @user: 의견   │
└──────────────────┘
```

### 자동 실행 시 Slack 전송

스케줄러가 켜져 있으면 매일 파이프라인 완료 후 Slack 채널에 리포트가 자동 전송됩니다.

```
매일 09:00 (스케줄러)
    │
    ├──→ 논문 수집 → LLM 분석 → 리포트 생성
    └──→ Slack 채널에 자동 전송 (투표 버튼 포함)
```

### 닉네임 연동

- **개인 사용 시**: 웹 대시보드에서 닉네임을 직접 입력합니다
- **팀 사용 시**: 닉네임 설정에서 Slack 멤버 목록이 표시되고, 선택하면 Slack과 웹의 투표·댓글이 동일 사용자로 통합됩니다

---

## 기능별 필요한 키

| 기능 | 필요한 키 | Slack 필요 |
|------|----------|:----------:|
| 웹 대시보드 열람 + 투표 + 댓글 | 없음 | - |
| 논문 자동 수집·분석 | `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` | - |
| 논문 수동 추가 (웹에서) | `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` | - |
| 관심사 키워드 추출 | `OPENAI_API_KEY` | - |
| Slack 리포트 자동 전송 | `SLACK_WEBHOOK_URL` | ✅ |
| Slack 투표·댓글 버튼 | `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN` | ✅ |
| 웹에서 Slack 닉네임 연동 | `SLACK_BOT_TOKEN` + `users:read` 스코프 | ✅ |

---

## 아키텍처

이 도구는 논문을 깊이 리뷰하기보다, **최근 연구 트렌드를 정확하게 감지**하는 것을 목표로 합니다.
과장된 표현이나 확장 해석 없이, 논문이 명시한 범위까지만 요약합니다.

### 파이프라인 흐름

전체 파이프라인은 3단계로 구성되어 있습니다.

```
Orchestrator
    │
    ├──→ 1. Skim Pipeline ──→ HuggingFace에서 수집 → 키워드 필터 → LLM 스크리닝 (관심도 1-5점)
    │
    ├──→ 2. Deep Pipeline ──→ PDF 파싱 → 정보 추출 → 차별점 분석 → 점수 평가
    │         │                  → 검증 → [실패 시 교정 → 재분석 루프]
    │         │
    │         └──→ Daily Report 생성
    │
    └──→ 3. Code Pipeline ──→ GitHub 코드 분석 → 방법론-코드 매핑 (선택)
```

Deep Pipeline에서는 LangGraph의 조건부 분기를 활용하여 **자기 교정 루프**를 구현합니다.
Verification 단계에서 과장이나 부정확을 탐지하면, Correction → 재추출 → 재검증을 자동으로 수행합니다.

<details>
<summary>MCP 서버 구성</summary>

[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 패턴으로 외부 서비스와의 통신을 모듈화하고 있습니다.

| MCP 서버 | 역할 |
|----------|------|
| `HFPapersServer` | HuggingFace Daily Papers에서 논문 메타데이터 수집 |
| `GrobidServer` | GROBID를 통해 PDF → TEI-XML 변환, 섹션·테이블·참고문헌 추출 |
| `PyMuPDFParser` | GROBID 미사용 시 폴백으로 PyMuPDF로 텍스트 추출 |

</details>

<details>
<summary>에이전트 구성</summary>

| 에이전트 | 역할 | LLM | 모델 |
|----------|------|:---:|------|
| `Orchestrator` | 전체 파이프라인 조율 | - | - |
| `Fetcher` | HuggingFace에서 논문 수집 | - | - |
| `Gatekeeper` | 키워드·upvote 기반 필터링 | - | - |
| `SkimAgent` | 빠른 스크리닝, 관심도 점수 | ✅ | gpt-4o-mini |
| `ExtractionAgent` | 논문 구조화 정보 추출 | ✅ | gpt-4o |
| `DeltaAgent` | 기존 연구 대비 차별점 분석 | ✅ | gpt-4o |
| `ScoringAgent` | 실용성·구현성·신뢰도 평가 | ✅ | gpt-4o-mini |
| `VerificationAgent` | 과장 표현 검증 | ✅ | gpt-4o-mini |
| `CorrectionAgent` | 검증 실패 시 수정 | ✅ | gpt-4o-mini |
| `GitHubMethodAgent` | GitHub 코드-방법론 매핑 | ✅ | gpt-4o |
| `DailyReportAgent` | 일일 통합 리포트 생성 | - | - |

</details>

---

## 관심사 설정

수집할 논문의 키워드는 웹 대시보드의 "관심사 설정" 탭에서 변경할 수 있습니다.

<details>
<summary>config.py에서 직접 설정하기</summary>

```python
# src/rtc/config.py

class Settings(BaseSettings):
    hf_papers_keywords: list[str] = [
        "LLM", "large language model", "agent", "RAG",
        "reasoning", "tool use", "function calling", ...
    ]

    interest_keywords: list[str] = [
        "agent", "agentic", "multi-agent", "tool use",
        "RAG", "retrieval", "reasoning", "chain of thought", ...
    ]

    max_deep_papers_per_day: int = 3        # 하루 최대 심층 분석 수
    skim_interest_threshold: int = 4        # 심층 분석 임계값 (1-5점)
```

</details>

<details>
<summary>관심 분야별 추천 키워드</summary>

| 관심 분야 | 추천 키워드 |
|-----------|-------------|
| LLM Agent | `agent`, `agentic`, `multi-agent`, `tool use`, `function calling`, `ReAct` |
| RAG | `RAG`, `retrieval`, `retrieval augmented`, `knowledge base`, `vector` |
| 추론 | `reasoning`, `chain of thought`, `CoT`, `planning`, `problem solving` |
| 멀티모달 | `multimodal`, `vision language`, `VLM`, `image`, `video` |
| 코드 생성 | `code generation`, `programming`, `software engineering`, `code LLM` |
| 파인튜닝 | `fine-tuning`, `RLHF`, `DPO`, `instruction tuning`, `alignment` |

</details>

---

## 환경 변수 전체 목록

<details>
<summary>전체 환경 변수 보기</summary>

```bash
# LLM API (논문 분석용, 둘 중 하나 필수)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# LLM 설정
LLM_PROVIDER=openai              # openai 또는 claude
LLM_MODEL_OPENAI=gpt-4o
LLM_MODEL_CLAUDE=claude-sonnet-4-20250514

# Slack (선택 - 팀 협업 시)
SLACK_WEBHOOK_URL=               # 메시지 발송용
SLACK_SIGNING_SECRET=            # 투표 콜백 검증용
SLACK_BOT_TOKEN=                 # 댓글 스레드 + 닉네임 연동용

# LangSmith (선택, 트레이싱)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=paper-digest-agent
LANGSMITH_TRACING=true

# 스케줄러 (자동 실행)
SCHEDULER_ENABLED=false          # true로 설정 시 매일 자동 실행
SCHEDULER_CRON_HOUR=9
SCHEDULER_TIMEZONE=Asia/Seoul
```

</details>

---

## CLI 사용법

Docker 없이 직접 실행할 수도 있습니다.

<details>
<summary>설치 및 실행 명령어</summary>

```bash
# 설치
pip install -e .              # 핵심 파이프라인
pip install -e notifier/      # Slack/Web 모듈
cp .env.example .env          # 환경 변수

# 파이프라인 실행
python -m rtc.agents.orchestrator                    # 오늘 날짜
python -m rtc.agents.orchestrator --date 2026-01-31  # 특정 날짜
python -m rtc.agents.orchestrator --code             # GitHub 코드 분석 포함

# Slack 전송
cd notifier
toslack send                    # 오늘 리포트 전송
toslack send -d 2026-02-10     # 특정 날짜 전송
toslack send --interactive      # 투표 버튼 포함

# 서버 실행
toslack server                  # http://localhost:8000
```

</details>

---

## 프로젝트 구조

<details>
<summary>디렉토리 구조 보기</summary>

```
paper-digest-agent/
├── src/rtc/
│   ├── config.py              # 설정 관리
│   ├── schemas/               # Pydantic 데이터 모델
│   ├── agents/                # LLM 에이전트
│   ├── pipeline/              # LangGraph 파이프라인 (skim, deep, code)
│   ├── mcp/servers/           # MCP 서버 (HuggingFace, GROBID, PyMuPDF)
│   ├── llm/                   # LLM 클라이언트 (OpenAI, Claude)
│   ├── storage/               # 데이터 저장소
│   └── tracing/               # LangSmith 트레이싱
├── notifier/                  # Slack + 웹 대시보드
│   ├── src/toslack/           # FastAPI 서버 + Slack 연동
│   └── web/                   # SvelteKit 프론트엔드
├── docker/                    # Docker 빌드 파일
├── docker-compose.yml
├── reports/                   # 생성된 리포트 (데이터 저장)
└── .env.example               # 환경 변수 템플릿
```

</details>

## 출력 예시

<details>
<summary>Daily Report 예시</summary>

```markdown
# 2026-01-31 Daily Paper Report

## 오늘의 논문 (3편)

### 1. Paper Title [GitHub ✓]

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
```

</details>

<details>
<summary>개별 논문 리포트 파일</summary>

각 논문별로 `reports/{paper-slug}/` 폴더에 다음 파일들이 생성됩니다.

| 파일 | 내용 |
|------|------|
| `extraction.json` | 구조화된 정보 추출 |
| `delta.json` | 차별점 분석 |
| `scoring.json` | 점수 평가 |
| `verification.json` | 검증 결과 |
| `deep.md` | 마크다운 리포트 |

</details>

---

## 개발

<details>
<summary>개발 환경 설정</summary>

```bash
pip install -e ".[dev]"
pytest
ruff format .
ruff check .
```

</details>

## 라이선스

MIT
