"""Slack webhook sender with retry logic."""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings


class SlackSendError(Exception):
    """Error occurred while sending to Slack."""

    pass


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def send_to_slack(payload: dict[str, Any], webhook_url: str | None = None) -> bool:
    """Send payload to Slack webhook.

    Args:
        payload: Slack message payload (blocks format).
        webhook_url: Optional webhook URL override. Uses settings if not provided.

    Returns:
        True if successful.

    Raises:
        SlackSendError: If sending fails after retries.
    """
    url = webhook_url or settings.slack_webhook_url

    if not url:
        raise SlackSendError("SLACK_WEBHOOK_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise SlackSendError(
                f"Slack API error: {response.status_code} - {response.text}"
            )

    return True


def send_to_slack_sync(payload: dict[str, Any], webhook_url: str | None = None) -> bool:
    """Synchronous version of send_to_slack.

    Args:
        payload: Slack message payload (blocks format).
        webhook_url: Optional webhook URL override. Uses settings if not provided.

    Returns:
        True if successful.

    Raises:
        SlackSendError: If sending fails after retries.
    """
    import asyncio

    return asyncio.run(send_to_slack(payload, webhook_url))
