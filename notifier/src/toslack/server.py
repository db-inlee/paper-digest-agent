"""FastAPI server for handling Slack interactions."""

import hashlib
import hmac
import json
import logging
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .analysis import find_paper_dir, load_paper_detail
from .config import settings
from .converter import parse_report, to_slack_blocks_interactive, to_slack_payload_interactive
from .reader import list_available_reports, read_daily_report
from .scheduler import start_scheduler, stop_scheduler
from .storage import comment_store, vote_store
from .topics import extract_keywords_via_llm, fetch_arxiv_abstract, topic_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pipeline execution state
pipeline_status: dict[str, Any] = {"state": "idle", "date": None, "error": None}

# Paper add jobs: { arxiv_id: { state, title, date, error } }
paper_add_jobs: dict[str, dict[str, Any]] = {}


def _send_report_to_slack(target_date: str) -> None:
    """Send the daily report to Slack after pipeline completion."""
    try:
        if not settings.slack_webhook_url:
            logger.info("SLACK_WEBHOOK_URL not configured, skipping Slack send")
            return

        content = read_daily_report(target_date)
        papers, skim_papers = parse_report(content)
        if not papers and not skim_papers:
            logger.warning("No papers found in report for %s, skipping Slack send", target_date)
            return

        vote_counts = {}
        for paper in papers:
            votes = vote_store.get_paper_votes(target_date, paper.arxiv_id)
            vote_counts[paper.arxiv_id] = {
                "applicable_count": votes["applicable_count"],
                "idea_count": votes["idea_count"],
                "pass_count": votes["pass_count"],
            }

        payload = to_slack_payload_interactive(papers, target_date, vote_counts, skim_papers)
        from .sender import send_to_slack_sync

        send_to_slack_sync(payload)
        logger.info("Daily report for %s sent to Slack", target_date)
    except Exception as exc:
        logger.error("Failed to send report to Slack: %s", exc)


def trigger_pipeline(target_date: str, send_slack: bool = True) -> bool:
    """Trigger pipeline in a background thread. Returns False if already running."""
    if pipeline_status["state"] == "running":
        return False

    pipeline_status.update(state="running", date=target_date, error=None)

    def _run() -> None:
        try:
            result = subprocess.run(
                ["python", "-m", "rtc.agents.orchestrator", "--date", target_date],
                capture_output=True,
                text=True,
                timeout=1800,
            )
            logger.info("Pipeline stdout: %s", result.stdout[-2000:] if result.stdout else "(empty)")
            logger.info("Pipeline stderr: %s", result.stderr[-2000:] if result.stderr else "(empty)")
            if result.returncode == 0:
                pipeline_status.update(state="completed", error=None)
                if send_slack:
                    _send_report_to_slack(target_date)
            else:
                pipeline_status.update(state="error", error=result.stderr[:500])
        except Exception as exc:
            pipeline_status.update(state="error", error=str(exc)[:500])

    threading.Thread(target=_run, daemon=True).start()
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="toslack Vote Server", lifespan=lifespan)

# CORS middleware for web dashboard
if settings.allowed_origins:
    origins = [o.strip() for o in settings.allowed_origins.split(",")]
else:
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SvelteKit static build directory
# In Docker: set WEB_BUILD_DIR env; locally: resolve relative to source tree
WEB_BUILD_DIR = (
    Path(settings.web_build_dir) if settings.web_build_dir
    else Path(__file__).resolve().parent.parent.parent / "web" / "build"
)


class WebVoteRequest(BaseModel):
    """Request body for web voting."""

    user_name: str
    arxiv_id: str
    report_date: str
    vote: Literal["applicable", "idea", "pass"]
    slack_user_id: str | None = None  # If set, unifies with Slack identity


class CommentRequest(BaseModel):
    """Request body for adding a comment."""

    user_name: str
    arxiv_id: str
    report_date: str
    text: str


class CommentDeleteRequest(BaseModel):
    """Request body for deleting a comment."""

    user_name: str
    report_date: str
    arxiv_id: str
    comment_id: str


class TopicAddRequest(BaseModel):
    keywords: list[str]
    source: Literal["manual", "arxiv", "freetext"] = "manual"
    added_by: str = ""
    source_detail: str | None = None


class TopicRemoveRequest(BaseModel):
    keyword: str


class TopicToggleDefaultRequest(BaseModel):
    keyword: str


class ArxivExtractRequest(BaseModel):
    arxiv_id: str


class TextExtractRequest(BaseModel):
    text: str


class PaperAddRequest(BaseModel):
    url: str  # arXiv URL, e.g. https://arxiv.org/abs/2602.06540


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    signature: str,
    body: bytes,
) -> bool:
    """Verify that the request came from Slack."""
    # Check timestamp to prevent replay attacks (within 5 minutes)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = (
        "v0=" + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
    )
    return hmac.compare_digest(my_signature, signature)


@app.post("/slack/interactions")
async def handle_interaction(request: Request):
    """Handle Slack interactive component callbacks."""
    body = await request.body()

    # Verify Slack signature (skip if no signing secret configured for dev)
    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not verify_slack_signature(
            settings.slack_signing_secret, timestamp, signature, body
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the payload
    form_data = await request.form()
    payload_str = form_data.get("payload", "")
    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")

    payload = json.loads(payload_str)

    # Handle button clicks
    if payload.get("type") == "block_actions":
        actions = payload.get("actions", [])
        if actions and actions[0].get("action_id") == "add_comment":
            return await handle_comment_button(payload)
        return await handle_vote_action(payload)

    # Handle modal submission
    if payload.get("type") == "view_submission":
        return await handle_comment_submit(payload)

    return JSONResponse({"ok": True})


# Slack action_id -> vote type mapping
_SLACK_ACTION_MAP = {
    "vote_applicable": "applicable",
    "vote_idea": "idea",
    "vote_pass": "pass",
}


async def handle_comment_button(payload: dict[str, Any]) -> JSONResponse:
    """Open a modal for the user to add a comment."""
    trigger_id = payload.get("trigger_id")
    if not trigger_id or not settings.slack_bot_token:
        return JSONResponse({"ok": True})

    action = payload["actions"][0]
    value = action.get("value", "")  # "date|arxiv_id|title"
    channel_id = payload.get("channel", {}).get("id", "")
    message_ts = payload.get("message", {}).get("ts", "")

    # Include channel_id and message_ts in metadata so we can reply in thread
    metadata = f"{value}|{channel_id}|{message_ts}"

    modal = {
        "type": "modal",
        "callback_id": "comment_submit",
        "private_metadata": metadata,
        "title": {"type": "plain_text", "text": "논문 댓글"},
        "submit": {"type": "plain_text", "text": "등록"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{value.split('|', 2)[2] if len(value.split('|', 2)) > 2 else 'Paper'}*",
                },
            },
            {
                "type": "input",
                "block_id": "comment_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "comment_text",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "이 논문에 대한 의견을 남겨주세요..."},
                },
                "label": {"type": "plain_text", "text": "댓글"},
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/views.open",
            json={"trigger_id": trigger_id, "view": modal},
            headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
            timeout=10.0,
        )

    return JSONResponse({"ok": True})


async def handle_comment_submit(payload: dict[str, Any]) -> JSONResponse:
    """Handle modal submission — save comment and post to channel."""
    user = payload.get("user", {})
    user_id = user.get("id", "")
    user_name = user.get("username", user.get("name", "Unknown"))

    view = payload.get("view", {})
    metadata = view.get("private_metadata", "")
    # metadata format: "date|arxiv_id|title|channel_id|message_ts"
    parts = metadata.split("|")
    if len(parts) < 3:
        return JSONResponse({"response_action": "clear"})

    report_date = parts[0]
    arxiv_id = parts[1]
    paper_title = parts[2]
    channel_id = parts[3] if len(parts) > 3 else ""
    message_ts = parts[4] if len(parts) > 4 else ""

    values = view.get("state", {}).get("values", {})
    text = values.get("comment_block", {}).get("comment_text", {}).get("value", "")
    if not text.strip():
        return JSONResponse({"response_action": "clear"})

    comment_store.add_comment(
        report_date=report_date,
        arxiv_id=arxiv_id,
        user_name=user_name,
        text=text.strip(),
    )

    # Post comment to channel so everyone can see it
    if channel_id and settings.slack_bot_token:
        total_comments = len(comment_store.get_comments(report_date, arxiv_id))
        message_text = (
            f"💬 *{paper_title}*\n"
            f"<@{user_id}>: {text.strip()}\n"
            f"_댓글 {total_comments}개 · <https://paper-digest.fly.dev/paper/{arxiv_id}|웹에서 보기>_"
        )
        try:
            post_body: dict[str, str] = {"channel": channel_id, "text": message_text}
            if message_ts:
                post_body["thread_ts"] = message_ts
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    json=post_body,
                    headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                    timeout=10.0,
                )
                resp_data = resp.json()
                if not resp_data.get("ok"):
                    logger.error("Slack chat.postMessage failed: %s", resp_data.get("error"))
                else:
                    logger.info("Comment posted to channel %s", channel_id)
        except Exception as e:
            logger.error("Failed to post comment to channel: %s", e)
    else:
        logger.warning("Comment not posted: channel_id=%r, bot_token=%s", channel_id, bool(settings.slack_bot_token))

    return JSONResponse({"response_action": "clear"})


async def handle_vote_action(payload: dict[str, Any]) -> JSONResponse:
    """Handle vote button clicks."""
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    user_name = user.get("username", user.get("name", "Unknown"))

    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse({"ok": True})

    action = actions[0]
    action_id = action.get("action_id", "")
    value = action.get("value", "")

    # Parse action value: "report_date|arxiv_id|title"
    parts = value.split("|", 2)
    if len(parts) < 3:
        return JSONResponse({"ok": True})

    report_date, arxiv_id, paper_title = parts

    # Determine vote type
    vote_type = _SLACK_ACTION_MAP.get(action_id)
    if not vote_type:
        return JSONResponse({"ok": True})

    # Record vote
    vote_store.add_vote(
        report_date=report_date,
        arxiv_id=arxiv_id,
        paper_title=paper_title,
        user_id=user_id,
        user_name=user_name,
        vote=vote_type,
    )

    # Update the message with new vote counts
    await update_message_votes(payload, report_date)

    return JSONResponse({"ok": True})


async def update_message_votes(payload: dict[str, Any], report_date: str) -> None:
    """Update the Slack message with current vote counts."""
    response_url = payload.get("response_url")
    if not response_url:
        return

    try:
        # Re-parse the report to get paper info
        content = read_daily_report(report_date)
        papers, _ = parse_report(content)

        # Get current vote counts for all papers
        vote_counts = {}
        for paper in papers:
            votes = vote_store.get_paper_votes(report_date, paper.arxiv_id)
            vote_counts[paper.arxiv_id] = {
                "applicable_count": votes["applicable_count"],
                "idea_count": votes["idea_count"],
                "pass_count": votes["pass_count"],
            }

        # Generate updated blocks
        new_blocks = to_slack_blocks_interactive(papers, report_date, vote_counts)

        # Send update via response_url
        async with httpx.AsyncClient() as client:
            await client.post(
                response_url,
                json={
                    "replace_original": True,
                    "blocks": new_blocks,
                },
                timeout=10.0,
            )
    except Exception as e:
        print(f"Error updating message: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/votes/{report_date}")
async def get_votes(report_date: str):
    """Get vote summary for a report date."""
    try:
        content = read_daily_report(report_date)
        papers, _ = parse_report(content)

        result = []
        for paper in papers:
            votes = vote_store.get_paper_votes(report_date, paper.arxiv_id)
            result.append({
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "applicable_count": votes["applicable_count"],
                "idea_count": votes["idea_count"],
                "pass_count": votes["pass_count"],
            })

        return {"date": report_date, "papers": result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_date}")


@app.get("/applicable")
async def get_applicable_papers():
    """Get all papers that have been voted as applicable."""
    return {"applicable_papers": vote_store.get_applicable_papers()}


@app.get("/ideas")
async def get_idea_papers():
    """Get all papers that have been voted as ideas."""
    return {"idea_papers": vote_store.get_idea_papers()}


# =============================================================================
# Web Dashboard API Endpoints
# =============================================================================


@app.get("/api/reports")
async def api_list_reports():
    """List all available report dates for the web dashboard."""
    dates = list_available_reports()
    return {"dates": dates}


@app.get("/api/reports/{date}")
async def api_get_report(date: str):
    """Get papers with full details and vote info for a specific date."""
    try:
        content = read_daily_report(date)
        papers, skim_papers = parse_report(content)

        def _voters_for(report_date: str, arxiv_id: str) -> dict:
            votes = vote_store.get_paper_votes(report_date, arxiv_id)
            voters = votes.get("voters", {})
            applicable_voters, idea_voters, pass_voters = [], [], []
            for user_id, vote_info in voters.items():
                voter_data = {
                    "user_id": user_id,
                    "user_name": vote_info["user_name"],
                    "voted_at": vote_info["voted_at"],
                }
                if vote_info["vote"] == "applicable":
                    applicable_voters.append(voter_data)
                elif vote_info["vote"] == "idea":
                    idea_voters.append(voter_data)
                else:
                    pass_voters.append(voter_data)
            return {
                "applicable_count": votes["applicable_count"],
                "idea_count": votes["idea_count"],
                "pass_count": votes["pass_count"],
                "applicable_voters": applicable_voters,
                "idea_voters": idea_voters,
                "pass_voters": pass_voters,
            }

        result = []
        for paper in papers:
            v = _voters_for(date, paper.arxiv_id)
            result.append({
                "arxiv_id": paper.arxiv_id,
                "arxiv_url": paper.arxiv_url,
                "title": paper.title,
                "score": paper.score,
                "max_score": paper.max_score,
                "stars": paper.stars,
                "star_emoji": paper.star_emoji,
                "summary": paper.summary,
                "problem": paper.problem,
                "when_to_use": paper.when_to_use,
                "when_not_to_use": paper.when_not_to_use,
                "github_url": paper.github_url,
                **v,
            })

        skim_result = []
        for sp in skim_papers:
            v = _voters_for(date, sp.arxiv_id)
            skim_result.append({
                "arxiv_id": sp.arxiv_id,
                "arxiv_url": sp.arxiv_url,
                "title": sp.title,
                "one_liner": sp.one_liner,
                "category": sp.category,
                "matched_keywords": sp.matched_keywords,
                **v,
            })

        return {"date": date, "papers": result, "skim_papers": skim_result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report not found: {date}")


@app.post("/api/vote")
async def api_web_vote(request: WebVoteRequest):
    """Handle voting from the web dashboard."""
    user_id = request.slack_user_id if request.slack_user_id else f"web_{request.user_name}"

    # Get paper title from existing data (deep + skim)
    try:
        content = read_daily_report(request.report_date)
        papers, skim_papers = parse_report(content)
        paper_title = next(
            (p.title for p in papers if p.arxiv_id == request.arxiv_id),
            None,
        )
        if paper_title is None:
            paper_title = next(
                (s.title for s in skim_papers if s.arxiv_id == request.arxiv_id),
                "Unknown Paper",
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report not found: {request.report_date}")

    result = vote_store.add_vote(
        report_date=request.report_date,
        arxiv_id=request.arxiv_id,
        paper_title=paper_title,
        user_id=user_id,
        user_name=request.user_name,
        vote=request.vote,
    )

    return {
        "success": True,
        "applicable_count": result["applicable_count"],
        "idea_count": result["idea_count"],
        "pass_count": result["pass_count"],
    }


@app.get("/api/papers/{arxiv_id}")
async def api_get_paper_detail(arxiv_id: str):
    """Get detailed analysis data for a specific paper."""
    detail = load_paper_detail(arxiv_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    return detail


@app.get("/api/stats")
async def api_get_stats():
    """Get overall voting statistics."""
    dates = list_available_reports()
    total_papers = 0
    total_applicable = 0
    total_idea = 0
    total_pass = 0
    total_no_vote = 0

    for date in dates:
        try:
            content = read_daily_report(date)
            papers, _ = parse_report(content)
            for paper in papers:
                total_papers += 1
                votes = vote_store.get_paper_votes(date, paper.arxiv_id)
                ac = votes["applicable_count"]
                ic = votes["idea_count"]
                pc = votes["pass_count"]
                if ac == 0 and ic == 0 and pc == 0:
                    total_no_vote += 1
                elif ac >= ic and ac >= pc:
                    total_applicable += 1
                elif ic >= ac and ic >= pc:
                    total_idea += 1
                else:
                    total_pass += 1
        except FileNotFoundError:
            continue

    return {
        "total_papers": total_papers,
        "total_applicable": total_applicable,
        "total_idea": total_idea,
        "total_pass": total_pass,
        "total_no_vote": total_no_vote,
        "report_count": len(dates),
    }


# =============================================================================
# Comment API Endpoints
# =============================================================================


@app.post("/api/comments")
async def api_add_comment(request: CommentRequest):
    """Add a comment to a paper."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Comment text cannot be empty")

    comment = comment_store.add_comment(
        report_date=request.report_date,
        arxiv_id=request.arxiv_id,
        user_name=request.user_name,
        text=request.text.strip(),
    )
    return {"success": True, "comment": comment}


@app.get("/api/comments/{date}/{arxiv_id}")
async def api_get_comments(date: str, arxiv_id: str):
    """Get comments for a paper."""
    comments = comment_store.get_comments(date, arxiv_id)
    return {"comments": comments}


@app.delete("/api/comments")
async def api_delete_comment(request: CommentDeleteRequest):
    """Delete a comment."""
    deleted = comment_store.delete_comment(
        report_date=request.report_date,
        arxiv_id=request.arxiv_id,
        comment_id=request.comment_id,
        user_name=request.user_name,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Comment not found or not authorized")
    return {"success": True}


# =============================================================================
# Topic Management API
# =============================================================================

DEFAULT_HF_KEYWORDS: list[str] = [
    # LLM 기본
    "LLM", "large language model", "language model",
    # Agent
    "agent", "agentic", "multi-agent", "autonomous",
    # RAG
    "RAG", "retrieval", "retrieval augmented",
    # 추론/계획
    "reasoning", "planning", "chain of thought", "CoT",
    # 도구/함수
    "tool use", "function calling", "tool learning",
    # 기타
    "ReAct", "prompt", "fine-tuning", "RLHF", "instruction",
]


@app.get("/api/topics")
async def api_get_topics():
    """Get all keywords: default list, custom additions, disabled list, and effective result."""
    data = topic_store.get_all()
    effective = topic_store.get_effective_keywords(DEFAULT_HF_KEYWORDS)
    return {
        "default_keywords": DEFAULT_HF_KEYWORDS,
        "custom_keywords": data["custom_keywords"],
        "disabled_default_keywords": data["disabled_default_keywords"],
        "effective_keywords": effective,
    }


@app.post("/api/topics/add")
async def api_add_topics(req: TopicAddRequest):
    data = topic_store.add_keywords(
        keywords=req.keywords,
        source=req.source,
        added_by=req.added_by,
        source_detail=req.source_detail,
    )
    effective = topic_store.get_effective_keywords(DEFAULT_HF_KEYWORDS)
    return {"success": True, **data, "effective_keywords": effective}


@app.delete("/api/topics/remove")
async def api_remove_topic(req: TopicRemoveRequest):
    data = topic_store.remove_keyword(req.keyword)
    effective = topic_store.get_effective_keywords(DEFAULT_HF_KEYWORDS)
    return {"success": True, **data, "effective_keywords": effective}


@app.post("/api/topics/toggle-default")
async def api_toggle_default_topic(req: TopicToggleDefaultRequest):
    data = topic_store.toggle_default_keyword(req.keyword)
    effective = topic_store.get_effective_keywords(DEFAULT_HF_KEYWORDS)
    return {"success": True, **data, "effective_keywords": effective}


@app.post("/api/topics/extract-arxiv")
async def api_extract_arxiv(req: ArxivExtractRequest):
    """Fetch arXiv abstract and extract keywords (preview only, does not save)."""
    try:
        paper = await fetch_arxiv_abstract(req.arxiv_id)
        text = f"{paper['title']}\n\n{paper['abstract']}"
        keywords = await extract_keywords_via_llm(text)
        return {
            "success": True,
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "keywords": keywords,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/topics/extract-text")
async def api_extract_text(req: TextExtractRequest):
    """Extract keywords from freeform text (preview only, does not save)."""
    try:
        keywords = await extract_keywords_via_llm(req.text)
        return {"success": True, "keywords": keywords}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Votes / Pipeline API
# =============================================================================


@app.get("/api/votes/all")
async def api_votes_all():
    """Return all voted papers across every report date."""
    data = vote_store._load()
    papers: list[dict] = []
    for report_date, arxiv_map in data.items():
        for arxiv_id, paper in arxiv_map.items():
            ac = paper.get("applicable_count", 0)
            ic = paper.get("idea_count", 0)
            pc = paper.get("pass_count", 0)
            total = ac + ic + pc
            if total == 0:
                continue
            if ac >= ic and ac >= pc:
                dominant = "applicable"
            elif ic >= ac and ic >= pc:
                dominant = "idea"
            else:
                dominant = "pass"
            papers.append({
                "arxiv_id": arxiv_id,
                "title": paper.get("title", ""),
                "date": report_date,
                "applicable_count": ac,
                "idea_count": ic,
                "pass_count": pc,
                "dominant_vote": dominant,
            })
    papers.sort(key=lambda p: p["date"], reverse=True)
    return {"papers": papers}


class PipelineRunRequest(BaseModel):
    date: str | None = None


@app.post("/api/pipeline/run")
async def api_pipeline_run(req: PipelineRunRequest | None = None):
    """Trigger the paper-digest pipeline."""
    tz = ZoneInfo(settings.scheduler_timezone)
    target = (req and req.date) or datetime.now(tz).strftime("%Y-%m-%d")
    ok = trigger_pipeline(target)
    if not ok:
        raise HTTPException(status_code=409, detail="Pipeline is already running")
    return {"success": True, "date": target, "state": "running"}


@app.get("/api/pipeline/status")
async def api_pipeline_status():
    """Return current pipeline execution status."""
    return pipeline_status


# =============================================================================
# Slack Members API
# =============================================================================


@app.get("/api/slack/members")
async def api_slack_members():
    """Fetch workspace members using the Slack bot token.

    Requires ``users:read`` bot scope.  Returns an empty list when no
    bot token is configured (personal / non-Slack mode).
    """
    if not settings.slack_bot_token:
        return {"members": [], "slack_connected": False}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://slack.com/api/users.list",
                headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                timeout=10.0,
            )
            data = resp.json()

        if not data.get("ok"):
            logger.warning("Slack users.list failed: %s", data.get("error"))
            return {"members": [], "slack_connected": True, "error": data.get("error")}

        members = []
        for m in data.get("members", []):
            # Skip bots and deactivated accounts
            if m.get("is_bot") or m.get("deleted") or m.get("id") == "USLACKBOT":
                continue
            profile = m.get("profile", {})
            members.append({
                "id": m["id"],
                "name": m.get("name", ""),
                "display_name": (
                    profile.get("display_name")
                    or profile.get("real_name")
                    or m.get("name", "")
                ),
                "avatar": profile.get("image_48", ""),
            })

        return {"members": members, "slack_connected": True}
    except Exception as e:
        logger.error("Failed to fetch Slack members: %s", e)
        return {"members": [], "slack_connected": True, "error": str(e)}


# =============================================================================
# Paper Add (Single paper analysis via arXiv URL)
# =============================================================================


def _extract_arxiv_id(url: str) -> str:
    """Extract arXiv ID from various URL formats or plain ID."""
    url = url.strip()
    # https://arxiv.org/abs/2602.06540  or  https://arxiv.org/pdf/2602.06540
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url)
    if m:
        return m.group(1)
    # Plain ID like 2602.06540
    m = re.match(r"^(\d{4}\.\d{4,5})$", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot parse arXiv ID from: {url}")


def _append_paper_to_daily_report(arxiv_id: str, title: str, run_date: str) -> bool:
    """Append a newly analyzed paper to the daily report markdown.

    Returns True if the paper was successfully appended, False otherwise.
    """
    report_path = settings.daily_reports_dir / f"{run_date}.md"

    # Load analysis data
    detail = load_paper_detail(arxiv_id)
    if detail is None:
        logger.warning("No analysis data found for %s after deep pipeline", arxiv_id)
        return False

    scoring = detail.get("scoring") or {}
    delta = detail.get("delta") or {}
    extraction = detail.get("extraction") or {}

    # Build star emoji — total is computed from sub-scores
    total_score = scoring.get("practicality", 0) + scoring.get("codeability", 0) + scoring.get("signal", 0)
    if total_score >= 13:
        stars = "⭐⭐⭐⭐⭐"
    elif total_score >= 11:
        stars = "⭐⭐⭐⭐"
    elif total_score >= 9:
        stars = "⭐⭐⭐"
    elif total_score >= 7:
        stars = "⭐⭐"
    else:
        stars = "⭐"

    # Determine next paper index
    next_index = 1
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8")
        # Skip if this arxiv_id is already in the report
        if arxiv_id in existing:
            logger.info("Paper %s already in daily report %s, skipping", arxiv_id, run_date)
            return True
        # Count existing papers
        next_index = len(re.findall(r"^### \d+\.", existing, re.MULTILINE)) + 1
    else:
        # Create minimal daily report
        existing = (
            f"# {run_date} Daily Paper Report\n\n"
            "> 이 리포트는 논문을 상세히 분석하기 위한 것이 아니라,\n"
            "> 최근 연구 흐름을 빠르게 파악하기 위한 데일리 요약입니다.\n\n"
            f"## 📚 오늘의 논문 (0편)\n\n---\n\n"
            f"---\n\n*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        )

    # Generate the paper markdown section
    lines = [f"### {next_index}. {title} {stars}", ""]
    lines.append(f"**arXiv**: [{arxiv_id}](https://arxiv.org/abs/{arxiv_id})")
    lines.append(f"**PDF**: [다운로드](https://arxiv.org/pdf/{arxiv_id}.pdf)")
    lines.append("")

    # Scoring section
    if scoring:
        lines.append("## 왜 이 논문인가?")
        lines.append(f"총점: {total_score}/15")
        lines.append("")
        lines.append("🎯 점수 상세:")
        lines.append(f"  - 실용성 (Practicality): {scoring.get('practicality', 0)}/5")
        lines.append(f"  - 구현 가능성 (Codeability): {scoring.get('codeability', 0)}/5")
        lines.append(f"  - 신뢰도 (Signal): {scoring.get('signal', 0)}/5")
        lines.append("")
        if scoring.get("reasoning"):
            lines.append("💡 평가 근거:")
            lines.append(scoring["reasoning"])
            lines.append("")
        if scoring.get("key_strength"):
            lines.append(f"**주요 강점**: {scoring['key_strength']}")
        if scoring.get("main_concern"):
            lines.append(f"**주요 우려**: {scoring['main_concern']}")
        lines.append("")

    # One-line takeaway
    if delta.get("one_line_takeaway"):
        lines.append("## 한 줄 요약")
        lines.append(delta["one_line_takeaway"])
        lines.append("")

    # Problem definition
    problem_def = extraction.get("problem_definition") or {}
    if problem_def.get("statement"):
        lines.append("## 문제 정의")
        lines.append(problem_def["statement"])
        lines.append("")
    if problem_def.get("structural_limitation"):
        lines.append(f"**기존 방법의 한계**: {problem_def['structural_limitation']}")
        lines.append("")

    # Core contributions (method claims)
    claims = extraction.get("claims") or []
    method_claims = [c for c in claims if c.get("claim_type") == "method"]
    if method_claims:
        lines.append("## 핵심 기여")
        for claim in method_claims[:3]:
            lines.append(f"- {claim.get('text', '')}")
        lines.append("")

    # Methodology
    components = extraction.get("method_components") or []
    if components:
        lines.append("## 방법론")
        for comp in components:
            lines.append(f"**{comp.get('name', '')}**")
            lines.append(comp.get("description", ""))
            if comp.get("inputs"):
                lines.append(f"- **입력**: {', '.join(comp['inputs'])}")
            if comp.get("outputs"):
                lines.append(f"- **출력**: {', '.join(comp['outputs'])}")
            if comp.get("implementation_hint"):
                lines.append(f"- **구현 힌트**: {comp['implementation_hint']}")
            lines.append("")

    # When to use / not
    if delta.get("when_to_use"):
        lines.append("## 언제 사용해야 하는가?")
        lines.append(f"✅ **사용 권장**: {delta['when_to_use']}")
        if delta.get("when_not_to_use"):
            lines.append(f"❌ **사용 비권장**: {delta['when_not_to_use']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    paper_section = "\n".join(lines)

    # Insert before the footer (---\n\n*Generated at...)
    footer_pattern = r"\n---\n\n\*Generated at .+\*\s*$"
    footer_match = re.search(footer_pattern, existing)
    if footer_match:
        insert_pos = footer_match.start()
        new_content = existing[:insert_pos] + "\n" + paper_section + existing[footer_match.start():]
    else:
        # No footer found — just append
        new_content = existing.rstrip() + "\n\n" + paper_section

    # Update paper count in header
    new_count = len(re.findall(r"^### \d+\.", new_content, re.MULTILINE))
    new_content = re.sub(
        r"## 📚 오늘의 논문 \(\d+편\)",
        f"## 📚 오늘의 논문 ({new_count}편)",
        new_content,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(new_content, encoding="utf-8")
    logger.info("Appended paper %s to daily report %s (paper #%d)", arxiv_id, run_date, next_index)
    return True


def _run_paper_add(arxiv_id: str, title: str, abstract: str, run_date: str) -> None:
    """Run deep analysis for a single paper in a background thread."""
    try:
        # Locate project root and src dir
        import os
        src_dir = os.environ.get("PYTHONPATH")
        if not src_dir or not Path(src_dir).joinpath("rtc").exists():
            candidate = settings.report_base_dir.resolve().parent / "src"
            if candidate.joinpath("rtc").exists():
                src_dir = str(candidate)
            else:
                candidate = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
                src_dir = str(candidate)

        project_root = str(Path(src_dir).parent)
        deep_script = str(Path(src_dir) / "rtc" / "pipeline" / "deep.py")
        env = {**os.environ, "PYTHONPATH": src_dir}
        result = subprocess.run(
            [
                "python", deep_script,
                "--arxiv-id", arxiv_id,
                "--title", title,
                "--abstract", abstract,
                "--date", run_date,
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            env=env,
            cwd=project_root,  # Use project root so rtc picks up root .env
        )
        if result.returncode == 0:
            appended = _append_paper_to_daily_report(arxiv_id, title, run_date)
            if appended:
                paper_add_jobs[arxiv_id].update(state="completed", error=None)
            else:
                paper_add_jobs[arxiv_id].update(
                    state="error",
                    error="Deep analysis succeeded but no output files found. Check report_base_dir configuration.",
                )
        else:
            paper_add_jobs[arxiv_id].update(state="error", error=result.stderr[:500])
    except Exception as exc:
        paper_add_jobs[arxiv_id].update(state="error", error=str(exc)[:500])


@app.post("/api/papers/add")
async def api_add_paper(req: PaperAddRequest):
    """Submit a paper for analysis via arXiv URL."""
    try:
        arxiv_id = _extract_arxiv_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if already running
    existing = paper_add_jobs.get(arxiv_id)
    if existing and existing["state"] == "running":
        raise HTTPException(status_code=409, detail=f"Paper {arxiv_id} is already being analyzed")

    # Check if already analyzed (has analysis files)
    detail = load_paper_detail(arxiv_id)
    if detail is not None:
        raise HTTPException(status_code=409, detail=f"Paper {arxiv_id} has already been analyzed")

    # Fetch metadata from arXiv
    try:
        meta = await fetch_arxiv_abstract(arxiv_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch arXiv metadata: {e}")

    tz = ZoneInfo(settings.scheduler_timezone)
    run_date = datetime.now(tz).strftime("%Y-%m-%d")

    paper_add_jobs[arxiv_id] = {
        "state": "running",
        "arxiv_id": arxiv_id,
        "title": meta["title"],
        "date": run_date,
        "error": None,
    }

    threading.Thread(
        target=_run_paper_add,
        args=(arxiv_id, meta["title"], meta["abstract"], run_date),
        daemon=True,
    ).start()

    return {
        "success": True,
        "arxiv_id": arxiv_id,
        "title": meta["title"],
        "date": run_date,
        "state": "running",
    }


@app.get("/api/papers/add/status")
async def api_paper_add_status():
    """Return status of all paper analysis jobs."""
    return {"jobs": list(paper_add_jobs.values())}


@app.get("/api/papers/add/status/{arxiv_id}")
async def api_paper_add_status_single(arxiv_id: str):
    """Return status of a specific paper analysis job."""
    job = paper_add_jobs.get(arxiv_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"No job found for {arxiv_id}")
    return job


# =============================================================================
# SvelteKit Static File Serving (SPA fallback)
# =============================================================================

if WEB_BUILD_DIR.exists():
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        """Serve SvelteKit build files with SPA fallback."""
        file = WEB_BUILD_DIR / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(WEB_BUILD_DIR / "200.html")


def run_server():
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(
        "toslack.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )
