"""Topic/keyword management with JSON persistence and LLM extraction."""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

from .config import settings


class TopicStore:
    """JSON-based topic/keyword storage following VoteStore pattern."""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or (settings.report_base_dir / "topics.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(
                json.dumps({"custom_keywords": [], "disabled_default_keywords": []},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _load(self) -> dict:
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        data.setdefault("custom_keywords", [])
        data.setdefault("disabled_default_keywords", [])
        return data

    def _save(self, data: dict) -> None:
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_all(self) -> dict:
        return self._load()

    def add_keywords(
        self,
        keywords: list[str],
        source: Literal["manual", "arxiv", "freetext"] = "manual",
        added_by: str = "",
        source_detail: str | None = None,
    ) -> dict:
        data = self._load()
        existing = {kw["keyword"].lower() for kw in data["custom_keywords"]}
        now = datetime.now().isoformat()

        for kw in keywords:
            kw_stripped = kw.strip()
            if not kw_stripped or kw_stripped.lower() in existing:
                continue
            data["custom_keywords"].append({
                "keyword": kw_stripped,
                "source": source,
                "added_at": now,
                "added_by": added_by,
                "source_detail": source_detail,
            })
            existing.add(kw_stripped.lower())

        self._save(data)
        return data

    def remove_keyword(self, keyword: str) -> dict:
        data = self._load()
        data["custom_keywords"] = [
            kw for kw in data["custom_keywords"]
            if kw["keyword"].lower() != keyword.lower()
        ]
        self._save(data)
        return data

    def toggle_default_keyword(self, keyword: str) -> dict:
        data = self._load()
        disabled = data["disabled_default_keywords"]
        kw_lower = keyword.lower()
        existing = [d.lower() for d in disabled]

        if kw_lower in existing:
            data["disabled_default_keywords"] = [
                d for d in disabled if d.lower() != kw_lower
            ]
        else:
            data["disabled_default_keywords"].append(keyword)

        self._save(data)
        return data

    def get_effective_keywords(self, default_keywords: list[str]) -> list[str]:
        data = self._load()
        disabled_lower = {d.lower() for d in data["disabled_default_keywords"]}
        result = [kw for kw in default_keywords if kw.lower() not in disabled_lower]
        existing_lower = {kw.lower() for kw in result}

        for entry in data["custom_keywords"]:
            if entry["keyword"].lower() not in existing_lower:
                result.append(entry["keyword"])
                existing_lower.add(entry["keyword"].lower())

        return result


async def fetch_arxiv_abstract(arxiv_id: str) -> dict:
    """Fetch paper title and abstract from arXiv Atom API."""
    clean_id = arxiv_id.strip().replace("https://arxiv.org/abs/", "")
    url = f"https://export.arxiv.org/api/query?id_list={clean_id}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise ValueError(f"Paper not found: {arxiv_id}")

    title_el = entry.find("atom:title", ns)
    summary_el = entry.find("atom:summary", ns)

    title = " ".join((title_el.text or "").split()) if title_el is not None else ""
    abstract = " ".join((summary_el.text or "").split()) if summary_el is not None else ""

    return {"arxiv_id": clean_id, "title": title, "abstract": abstract}


async def extract_keywords_via_llm(text: str) -> list[str]:
    """Extract 3-8 research keywords from text using an OpenAI-compatible API."""
    if not settings.llm_api_key:
        raise ValueError("LLM API key not configured (LLM_API_KEY)")

    prompt = (
        "Extract 3 to 8 concise research topic keywords from the following text. "
        "Return ONLY a JSON array of strings, e.g. [\"keyword1\", \"keyword2\"]. "
        "Focus on technical terms useful for filtering academic papers.\n\n"
        f"Text:\n{text[:3000]}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.llm_base_url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Parse JSON array from response (handle markdown fences)
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)


# Global instance
topic_store = TopicStore()
