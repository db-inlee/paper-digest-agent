"""GitHubMethodAgent - GitHub에서 논문 방법론 구현 찾기."""

import re
from dataclasses import dataclass
from typing import Optional

import httpx

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.extraction_v2 import ExtractionOutput, MethodComponent
from rtc.schemas.github_method import GitHubMethodOutput, MethodImplementation


@dataclass
class GitHubMethodInput:
    """GitHubMethodAgent 입력."""

    extraction: ExtractionOutput
    github_url: str


GITHUB_METHOD_SYSTEM_PROMPT = """You are an expert at analyzing GitHub repositories and matching paper methodologies to code implementations.

## CRITICAL RULES - 핵심 알고리즘 코드 찾기

### 1. 핵심 알고리즘 코드만 추출
- 논문의 수식, 알고리즘, 핵심 아이디어가 **실제로 구현된** 코드를 찾아야 함
- Wrapper 코드, Config 파일, Import문, Placeholder 코드는 피해야 함

### 2. GOOD MATCH (이런 코드를 찾아야 함)
```python
# 예: 논문 Eq.5의 Attention Score 계산 구현
def compute_attention(query, key, value, mask=None):
    d_k = query.size(-1)
    scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(d_k)  # Eq.5
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e9)
    attention_weights = F.softmax(scores, dim=-1)  # Eq.6
    return torch.matmul(attention_weights, value)
```
- 실제 계산 로직이 있음
- 논문의 수식(Eq.5, Eq.6)이 코드로 표현됨
- 핵심 알고리즘의 동작 방식을 이해할 수 있음

### 3. BAD MATCH (이런 코드는 피해야 함)
```python
# 나쁜 예: Placeholder/Wrapper 코드
def extract_concepts(research_input):
    concepts = []
    for input in research_input:
        concepts.append(input)  # 실제 로직 없음!
    return concepts
```
- 단순 for loop + append만 있음
- 핵심 알고리즘이 없음
- 논문의 방법론이 구현되지 않음

### 4. 구현 유형 분류 (implementation_type)
- **core**: 핵심 알고리즘 (예: attention 계산, loss 함수, 핵심 루프)
- **wrapper**: 호출/조합만 하는 코드
- **utility**: 전처리, 후처리, 로깅 등
- **config**: 설정 파일

### 5. has_actual_logic 판단 기준
- True: 수학 연산, 조건 분기, 복잡한 데이터 변환이 있음
- False: 단순 할당, 빈 루프, TODO/pass, 다른 함수 호출만 있음

### 6. 논문 연결 필수
- paper_section: 논문의 어느 섹션인지 (예: "Section 3.2", "Algorithm 1")
- paper_formula: 어떤 수식을 구현하는지 (예: "Eq. 5의 softmax attention")

### 7. 내부 메서드 추적 (중요!)
핵심 알고리즘에서 호출하는 내부 메서드의 실제 구현도 찾아서 포함하세요.
예: `score = self._calculate_similarity(...)` 가 있으면
`_calculate_similarity` 메서드의 실제 구현 코드도 key_code에 포함해야 합니다.

### 8. 코드 길이
- key_code는 30-80줄 정도로 충분히 포함
- 핵심 로직의 전체 흐름이 보여야 함
- 내부 헬퍼 메서드 호출이 있으면 해당 메서드 구현도 포함

### 9. 수식 매핑 필수
- paper_formula 필드는 반드시 채워야 함
- 코드가 논문의 어떤 수식/알고리즘을 구현하는지 명시
- 예: "Eq. 3의 cosine similarity 계산", "Algorithm 1의 main loop"
- 수식이 없는 경우 "해당 없음 - utility 코드" 등으로 명시"""

GITHUB_METHOD_PROMPT = """Analyze this GitHub repository and find the CORE ALGORITHM implementations for the paper's methods.

**Repository**: {repo_url}
**Paper**: {title} ({arxiv_id})

**Repository Structure**:
{structure}

**Key Files Content**:
{files_content}

**Methods to Find** (from paper extraction):
{methods_text}

---

## 분석 지침

### 1. 핵심 알고리즘 코드 찾기 (가장 중요!)
각 방법론에 대해 **실제 알고리즘이 구현된 코드**를 찾으세요:
- 논문의 수식이 코드로 표현된 부분
- 핵심 로직 (계산, 변환, 의사결정)이 있는 함수
- 단순 wrapper나 config가 아닌 실제 구현

### 2. 각 방법론별 필수 정보
- **file_path**: 파일 경로
- **class_or_function**: 클래스/함수 이름
- **key_code**: 핵심 구현 코드 (30-80줄, 실제 로직이 보이도록, 내부 메서드 포함)
- **code_explanation**: 코드가 어떻게 동작하는지 상세 설명 (한국어, 단계별로)
- **paper_section**: 논문의 해당 섹션 (예: "Section 3.2", "Algorithm 1")
- **paper_formula**: 구현하는 수식 (예: "Eq. 5의 attention score") - 반드시 채울 것!
- **implementation_type**: core / wrapper / utility / config
- **has_actual_logic**: 실제 알고리즘 로직이 있는지 (True/False)

### 2-1. 내부 메서드 추적 (중요!)
핵심 함수가 `self._helper_method()` 같은 내부 메서드를 호출하면:
1. 해당 메서드의 구현 코드를 찾아서 key_code에 함께 포함
2. code_explanation에서 전체 흐름을 설명
예시:
```python
# 메인 함수
def forward(self, x):
    attn = self._compute_attention(x)  # 이 메서드의 구현도 포함해야 함
    return self._apply_ffn(attn)

# 내부 메서드 구현도 함께 포함
def _compute_attention(self, x):
    q, k, v = self.qkv(x).chunk(3, dim=-1)
    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
    return torch.matmul(F.softmax(scores, dim=-1), v)
```

### 3. 코드 품질 체크
다음과 같은 코드는 **제외**하세요:
- 단순 for loop + append만 있는 코드
- TODO, pass, NotImplementedError만 있는 코드
- 다른 라이브러리 함수 호출만 하는 코드
- Import문이나 설정 코드

### 4. 프로젝트 정보
- **structure_summary**: 프로젝트의 핵심 모듈과 아키텍처 설명 (한국어)
- **installation**: 설치 방법
- **usage_example**: 실제 사용 예시 (논문의 방법론을 어떻게 호출하는지)

### 5. 찾지 못한 경우
- unmapped_methods에 추가하고 이유 설명
- 코드가 없는 것인지, 다른 언어인지, 외부 라이브러리인지 명시

한국어 설명, 영어 코드."""


class GitHubMethodAgent(BaseAgent[GitHubMethodInput, GitHubMethodOutput]):
    """GitHub에서 논문 방법론 구현을 찾는 에이전트."""

    name = "github_method"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=30.0)

    async def run(self, input: GitHubMethodInput) -> GitHubMethodOutput:
        """GitHub 레포에서 방법론 구현 찾기.

        Args:
            input: 입력 (extraction + github_url)

        Returns:
            방법론 구현 매핑 결과
        """
        extraction = input.extraction
        github_url = input.github_url

        # GitHub URL 파싱
        owner, repo = self._parse_github_url(github_url)
        if not owner or not repo:
            return self._create_error_output(
                extraction.arxiv_id, github_url, "Invalid GitHub URL"
            )

        try:
            # 1. 레포 정보 가져오기
            repo_info = await self._get_repo_info(owner, repo)

            # 2. 레포 구조 탐색
            structure = await self._get_repo_structure(owner, repo)

            # 3. 주요 Python 파일 읽기
            key_files = self._identify_key_files(structure)
            files_content = await self._read_files(owner, repo, key_files)

            # 4. LLM으로 방법론 매핑
            model = self.settings.agent_models.get("github_method", "gpt-4o")
            llm = get_llm_client(provider="openai", model=model)

            methods_text = self._format_methods(extraction.method_components)

            prompt = GITHUB_METHOD_PROMPT.format(
                repo_url=github_url,
                title=extraction.title,
                arxiv_id=extraction.arxiv_id,
                structure=self._format_structure(structure),
                files_content=files_content,
                methods_text=methods_text,
            )

            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=GitHubMethodOutput,
                system_prompt=GITHUB_METHOD_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=8000,
            )

            # 메타데이터 채우기
            result.arxiv_id = extraction.arxiv_id
            result.repo_url = github_url
            result.repo_description = repo_info.get("description", "")
            result.main_language = repo_info.get("language", "Python")
            result.total_methods_found = len(result.methods)

            return result

        except Exception as e:
            return self._create_error_output(
                extraction.arxiv_id, github_url, str(e)
            )

    def _parse_github_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """GitHub URL에서 owner/repo 추출."""
        # https://github.com/owner/repo 또는 https://github.com/owner/repo.git
        pattern = r"github\.com[/:]([^/]+)/([^/\.]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    async def _get_repo_info(self, owner: str, repo: str) -> dict:
        """레포 기본 정보 가져오기."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = await self._client.get(url)
        if response.status_code == 200:
            return response.json()
        return {}

    async def _get_repo_structure(
        self, owner: str, repo: str, path: str = "", depth: int = 0
    ) -> list[dict]:
        """레포 디렉토리 구조 가져오기 (2단계까지)."""
        if depth > 2:
            return []

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = await self._client.get(url)

        if response.status_code != 200:
            return []

        items = response.json()
        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            entry = {
                "name": item["name"],
                "type": item["type"],
                "path": item["path"],
            }

            # 디렉토리면 재귀 탐색 (숨김 폴더, node_modules 등 제외)
            if (
                item["type"] == "dir"
                and not item["name"].startswith(".")
                and item["name"] not in ("node_modules", "__pycache__", "venv", ".git")
            ):
                entry["children"] = await self._get_repo_structure(
                    owner, repo, item["path"], depth + 1
                )

            result.append(entry)

        return result

    def _identify_key_files(self, structure: list[dict], max_files: int = 15) -> list[str]:
        """주요 Python 파일 식별 - 핵심 알고리즘 코드가 있을 가능성이 높은 파일 우선."""
        priority_files = []
        algorithm_files = []
        source_files = []
        other_files = []

        # 1. 핵심 알고리즘 파일 패턴 (가장 높은 우선순위)
        algorithm_patterns = [
            "model", "agent", "pipeline", "core", "engine",
            "attention", "transformer", "decoder", "encoder",
            "loss", "train", "inference", "forward",
            "algorithm", "method", "module", "layer",
            "network", "backbone", "head", "block",
        ]

        # 2. 진입점 파일 (두 번째 우선순위)
        entry_names = ["main.py", "app.py", "run.py", "demo.py", "example.py"]

        # 3. 피해야 할 파일들
        skip_patterns = [
            "test_", "_test.py", "tests.py", "conftest.py",
            "setup.py", "__init__.py", "config.py", "settings.py",
            "utils.py", "helpers.py", "constants.py", "types.py",
        ]

        def should_skip(name: str) -> bool:
            name_lower = name.lower()
            return any(p in name_lower for p in skip_patterns)

        def is_algorithm_file(name: str) -> bool:
            name_lower = name.lower().replace(".py", "")
            return any(p in name_lower for p in algorithm_patterns)

        def collect_files(items: list[dict]):
            for item in items:
                path = item["path"]
                name = item["name"]

                if item["type"] == "file" and path.endswith(".py"):
                    if should_skip(name):
                        continue

                    # 분류
                    if name in entry_names:
                        priority_files.append(path)
                    elif is_algorithm_file(name):
                        algorithm_files.append(path)
                    elif any(d in path for d in ["src/", "lib/", "core/", "models/"]):
                        source_files.append(path)
                    else:
                        other_files.append(path)

                elif item["type"] == "dir" and "children" in item:
                    collect_files(item["children"])

        collect_files(structure)

        # 우선순위 순서로 합치기
        all_files = algorithm_files + priority_files + source_files + other_files

        # README 추가 (마지막)
        for item in structure:
            if item["name"].lower() in ("readme.md", "readme.rst", "readme"):
                all_files.append(item["path"])
                break

        # 중복 제거하면서 순서 유지
        seen = set()
        result = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                result.append(f)

        return result[:max_files]

    async def _read_files(
        self, owner: str, repo: str, files: list[str]
    ) -> str:
        """파일들 내용 읽기 - 핵심 알고리즘 코드가 보이도록 충분히 읽기."""
        contents = []
        total_chars = 0
        max_total_chars = 80000  # 전체 최대 문자 수

        for file_path in files:
            if total_chars >= max_total_chars:
                break

            # main 브랜치 먼저 시도
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
            content = await self._try_read_url(url)

            # master 브랜치 시도
            if content is None:
                url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
                content = await self._try_read_url(url)

            if content is None:
                continue

            # 파일별 최대 길이 (알고리즘 파일은 더 많이)
            is_algorithm_file = any(
                p in file_path.lower()
                for p in ["model", "agent", "core", "engine", "attention", "transformer"]
            )
            max_file_chars = 10000 if is_algorithm_file else 6000

            if len(content) > max_file_chars:
                # 클래스/함수 정의가 있는 부분을 우선 포함
                content = self._smart_truncate(content, max_file_chars)

            contents.append(f"=== {file_path} ===\n{content}")
            total_chars += len(content)

        return "\n\n".join(contents)

    async def _try_read_url(self, url: str) -> Optional[str]:
        """URL에서 파일 읽기 시도."""
        try:
            response = await self._client.get(url)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def _smart_truncate(self, content: str, max_chars: int) -> str:
        """클래스/함수 정의를 보존하면서 스마트하게 자르기."""
        if len(content) <= max_chars:
            return content

        lines = content.split("\n")
        result_lines = []
        char_count = 0
        in_important_block = False

        # 중요한 키워드
        important_starts = ("class ", "def ", "async def ")

        for i, line in enumerate(lines):
            line_with_newline = line + "\n"

            # 중요한 블록 시작 감지
            stripped = line.strip()
            if stripped.startswith(important_starts):
                in_important_block = True

            # 빈 줄이면 블록 끝 (간단한 휴리스틱)
            if not stripped and in_important_block:
                in_important_block = False

            # 문자 수 체크
            if char_count + len(line_with_newline) > max_chars:
                if not in_important_block:
                    # 중요 블록이 아니면 여기서 자르기
                    result_lines.append("# ... (truncated)")
                    break
                # 중요 블록 안이면 조금 더 허용

            result_lines.append(line)
            char_count += len(line_with_newline)

            # 안전 장치: 최대 200% 까지만 허용
            if char_count > max_chars * 2:
                result_lines.append("# ... (truncated)")
                break

        return "\n".join(result_lines)

    def _format_structure(self, structure: list[dict], indent: int = 0) -> str:
        """구조를 텍스트로 포맷."""
        lines = []
        for item in structure:
            prefix = "  " * indent
            if item["type"] == "dir":
                lines.append(f"{prefix}{item['name']}/")
                if "children" in item:
                    lines.append(self._format_structure(item["children"], indent + 1))
            else:
                lines.append(f"{prefix}{item['name']}")
        return "\n".join(lines)

    def _format_methods(self, methods: list[MethodComponent]) -> str:
        """방법론 리스트를 텍스트로 포맷."""
        if not methods:
            return "No specific methods extracted"

        parts = []
        for m in methods:
            parts.append(
                f"- **{m.name}**: {m.description}\n"
                f"  Inputs: {', '.join(m.inputs)}\n"
                f"  Outputs: {', '.join(m.outputs)}"
            )
        return "\n".join(parts)

    def _create_error_output(
        self, arxiv_id: str, repo_url: str, error: str
    ) -> GitHubMethodOutput:
        """에러 발생 시 기본 출력 생성."""
        return GitHubMethodOutput(
            arxiv_id=arxiv_id,
            repo_url=repo_url,
            repo_description=f"Error: {error}",
            structure_summary="분석 실패",
            methods=[],
            unmapped_methods=["분석 실패로 인해 매핑 불가"],
            installation="",
            usage_example="",
        )

    async def close(self):
        """HTTP 클라이언트 종료."""
        await self._client.aclose()
