"""CodeStore - reports/<slug>/code/ 저장 관리."""

import json
import re
from pathlib import Path
from typing import Optional

from rtc.schemas.github_method import GitHubMethodOutput


class CodeStore:
    """reports/<slug>/code/ 디렉토리 저장 관리.

    GitHub Method 결과 저장:
    - github_methods.json: 전체 결과
    - methods.md: 마크다운 형식
    - method_*.py: 개별 방법론 코드
    """

    def __init__(self, base_dir: Path, *, reports_dir: Path | None = None):
        """초기화.

        Args:
            base_dir: 프로젝트 베이스 디렉토리 (레거시)
            reports_dir: reports 디렉토리 경로 (우선 사용)
        """
        self.reports_dir = reports_dir if reports_dir is not None else base_dir / "reports"

    def get_code_dir(self, slug: str) -> Path:
        """코드 디렉토리 경로."""
        code_dir = self.reports_dir / slug / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        return code_dir

    def github_method_exists(self, slug: str) -> bool:
        """GitHub Method 결과 존재 여부."""
        return (self.reports_dir / slug / "code" / "github_methods.json").exists()

    def save_github_method(self, slug: str, result: GitHubMethodOutput) -> Path:
        """GitHub Method 결과 저장.

        Args:
            slug: 논문 슬러그
            result: GitHub Method 출력

        Returns:
            저장된 파일 경로
        """
        code_dir = self.get_code_dir(slug)

        # 1. github_methods.json 저장 (전체 결과)
        json_path = code_dir / "github_methods.json"
        json_path.write_text(
            json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 2. methods.md 저장 (읽기 좋은 형식)
        md_path = code_dir / "methods.md"
        md_content = self._format_github_method_md(result)
        md_path.write_text(md_content, encoding="utf-8")

        # 3. 각 방법론별 코드 파일 저장
        for i, method in enumerate(result.methods):
            filename = f"method_{i+1}_{self._sanitize_filename(method.method_name)}.py"
            method_path = code_dir / filename
            method_content = self._format_method_file(method, result)
            method_path.write_text(method_content, encoding="utf-8")

        return code_dir

    def load_github_method(self, slug: str) -> Optional[GitHubMethodOutput]:
        """GitHub Method 결과 로드."""
        path = self.reports_dir / slug / "code" / "github_methods.json"
        if not path.exists():
            return None

        content = json.loads(path.read_text(encoding="utf-8"))
        return GitHubMethodOutput(**content)

    def _format_github_method_md(self, result: GitHubMethodOutput) -> str:
        """GitHub Method 결과를 Markdown으로 포맷."""
        lines = [
            f"# {result.arxiv_id} - GitHub Method Analysis",
            "",
            f"**Repository**: [{result.repo_url}]({result.repo_url})",
            f"**Language**: {result.main_language}",
            "",
            "## 프로젝트 구조",
            "",
            result.structure_summary,
            "",
            "## 방법론 구현",
            "",
        ]

        for i, method in enumerate(result.methods, 1):
            lines.extend([
                f"### {i}. {method.method_name}",
                "",
                f"**설명**: {method.description}",
                "",
                f"**위치**: `{method.file_path}`",
                f"**함수/클래스**: `{method.class_or_function}`",
                "",
                "```python",
                method.key_code,
                "```",
                "",
                f"**코드 설명**: {method.code_explanation}",
                "",
            ])

        if result.unmapped_methods:
            lines.extend([
                "## 미구현 방법론",
                "",
                *[f"- {m}" for m in result.unmapped_methods],
                "",
            ])

        if result.installation:
            lines.extend([
                "## 설치 방법",
                "",
                "```bash",
                result.installation,
                "```",
                "",
            ])

        if result.usage_example:
            lines.extend([
                "## 사용 예시",
                "",
                "```python",
                result.usage_example,
                "```",
                "",
            ])

        return "\n".join(lines)

    def _format_method_file(self, method, result: GitHubMethodOutput) -> str:
        """개별 방법론 코드 파일 포맷."""
        lines = [
            f'"""',
            f'{method.method_name}',
            f'',
            f'원본: {result.repo_url}',
            f'파일: {method.file_path}',
            f'',
            f'{method.description}',
            f'',
            f'코드 설명:',
            f'{method.code_explanation}',
            f'"""',
            '',
            method.key_code,
        ]
        return "\n".join(lines)

    def _sanitize_filename(self, name: str) -> str:
        """파일명으로 사용 가능하도록 정리."""
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized[:50]
