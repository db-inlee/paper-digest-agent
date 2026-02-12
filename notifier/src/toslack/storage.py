"""Vote storage using local JSON file."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .config import settings

# Migration mapping: old vote types -> new vote types
_VOTE_MIGRATION = {"keep": "applicable", "drop": "pass"}


class Vote(BaseModel):
    """Single vote record."""

    user_id: str
    user_name: str
    paper_arxiv_id: str
    paper_title: str
    vote: Literal["applicable", "idea", "pass"]
    voted_at: str


class VoteStore:
    """Simple JSON-based vote storage."""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or (settings.report_base_dir / "votes.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure storage file exists."""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        """Load votes from file, migrating old format if needed."""
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        return self._migrate(data)

    def _migrate(self, data: dict) -> dict:
        """Migrate old keep/drop votes to applicable/idea/pass format."""
        migrated = False
        for date_key in data:
            for arxiv_id in data[date_key]:
                paper = data[date_key][arxiv_id]

                # Migrate count fields
                if "keep_count" in paper and "applicable_count" not in paper:
                    paper["applicable_count"] = paper.pop("keep_count")
                    paper["idea_count"] = 0
                    paper["pass_count"] = paper.pop("drop_count")
                    migrated = True

                # Migrate individual votes
                for user_id, vote_info in paper.get("votes", {}).items():
                    old_vote = vote_info.get("vote", "")
                    if old_vote in _VOTE_MIGRATION:
                        vote_info["vote"] = _VOTE_MIGRATION[old_vote]
                        migrated = True

        if migrated:
            self._save(data)
        return data

    def _save(self, data: dict) -> None:
        """Save votes to file."""
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_vote(
        self,
        report_date: str,
        arxiv_id: str,
        paper_title: str,
        user_id: str,
        user_name: str,
        vote: Literal["applicable", "idea", "pass"],
    ) -> dict:
        """Add or update a vote. Returns updated vote counts."""
        data = self._load()

        # Initialize structure if needed
        if report_date not in data:
            data[report_date] = {}
        if arxiv_id not in data[report_date]:
            data[report_date][arxiv_id] = {
                "title": paper_title,
                "votes": {},
                "applicable_count": 0,
                "idea_count": 0,
                "pass_count": 0,
            }

        paper_data = data[report_date][arxiv_id]
        old_vote = paper_data["votes"].get(user_id)

        # Decrement old vote count
        if old_vote:
            old_type = old_vote["vote"]
            count_key = f"{old_type}_count"
            if count_key in paper_data:
                paper_data[count_key] -= 1

        # Increment new vote count
        paper_data[f"{vote}_count"] += 1

        # Record vote
        paper_data["votes"][user_id] = {
            "user_name": user_name,
            "vote": vote,
            "voted_at": datetime.now().isoformat(),
        }

        self._save(data)

        return {
            "applicable_count": paper_data["applicable_count"],
            "idea_count": paper_data["idea_count"],
            "pass_count": paper_data["pass_count"],
        }

    def get_paper_votes(self, report_date: str, arxiv_id: str) -> dict:
        """Get vote counts for a paper."""
        data = self._load()
        if report_date in data and arxiv_id in data[report_date]:
            paper = data[report_date][arxiv_id]
            return {
                "applicable_count": paper.get("applicable_count", 0),
                "idea_count": paper.get("idea_count", 0),
                "pass_count": paper.get("pass_count", 0),
                "voters": paper["votes"],
            }
        return {"applicable_count": 0, "idea_count": 0, "pass_count": 0, "voters": {}}

    def get_applicable_papers(self, report_date: str | None = None) -> list[dict]:
        """Get papers that have applicable votes > 0."""
        data = self._load()
        result = []

        dates = [report_date] if report_date else list(data.keys())

        for date in dates:
            if date not in data:
                continue
            for arxiv_id, paper in data[date].items():
                if paper.get("applicable_count", 0) > 0:
                    result.append({
                        "date": date,
                        "arxiv_id": arxiv_id,
                        "title": paper["title"],
                        "applicable_count": paper.get("applicable_count", 0),
                        "idea_count": paper.get("idea_count", 0),
                        "pass_count": paper.get("pass_count", 0),
                    })

        return result

    def get_idea_papers(self, report_date: str | None = None) -> list[dict]:
        """Get papers that have idea votes > 0."""
        data = self._load()
        result = []

        dates = [report_date] if report_date else list(data.keys())

        for date in dates:
            if date not in data:
                continue
            for arxiv_id, paper in data[date].items():
                if paper.get("idea_count", 0) > 0:
                    result.append({
                        "date": date,
                        "arxiv_id": arxiv_id,
                        "title": paper["title"],
                        "applicable_count": paper.get("applicable_count", 0),
                        "idea_count": paper.get("idea_count", 0),
                        "pass_count": paper.get("pass_count", 0),
                    })

        return result


class CommentStore:
    """JSON-based comment storage."""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or (settings.report_base_dir / "comments.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        return json.loads(self.storage_path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_comment(
        self,
        report_date: str,
        arxiv_id: str,
        user_name: str,
        text: str,
    ) -> dict:
        """Add a comment. Returns the created comment."""
        data = self._load()

        if report_date not in data:
            data[report_date] = {}
        if arxiv_id not in data[report_date]:
            data[report_date][arxiv_id] = []

        comment = {
            "id": str(uuid.uuid4()),
            "user_name": user_name,
            "text": text,
            "created_at": datetime.now().isoformat(),
        }

        data[report_date][arxiv_id].append(comment)
        self._save(data)
        return comment

    def get_comments(self, report_date: str, arxiv_id: str) -> list[dict]:
        """Get comments for a paper."""
        data = self._load()
        if report_date in data and arxiv_id in data[report_date]:
            return data[report_date][arxiv_id]
        return []

    def delete_comment(
        self,
        report_date: str,
        arxiv_id: str,
        comment_id: str,
        user_name: str,
    ) -> bool:
        """Delete a comment by ID. Only the author can delete."""
        data = self._load()

        if report_date not in data or arxiv_id not in data[report_date]:
            return False

        comments = data[report_date][arxiv_id]
        for i, comment in enumerate(comments):
            if comment["id"] == comment_id and comment["user_name"] == user_name:
                comments.pop(i)
                self._save(data)
                return True

        return False


# Global instances
vote_store = VoteStore()
comment_store = CommentStore()
