"""Thin wrapper around slack_sdk.WebClient used by the monitors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


@dataclass
class SlackMessage:
    channel: str
    ts: str
    user: Optional[str]
    text: str
    thread_ts: Optional[str]
    raw: Dict[str, object]


class SlackAPIError(RuntimeError):
    """Simple wrapper for errors interacting with Slack."""


class SlackClientWrapper:
    """Provides convenience helpers around Slack Web API."""

    def __init__(self, token: str, rate_limit_sleep: float = 1.0):
        self.client = WebClient(token=token)
        self._user_cache: Dict[str, str] = {}
        self.rate_limit_sleep = rate_limit_sleep

    async def fetch_recent_messages(
        self,
        channel_id: str,
        oldest_ts: Optional[str] = None,
        limit: int = 100,
    ) -> List[SlackMessage]:
        """Fetch messages in descending order newer than oldest_ts."""
        try:
            response = await self._call_async(
                self.client.conversations_history,
                channel=channel_id,
                oldest=oldest_ts,
                limit=limit,
                inclusive=False,
            )
        except SlackApiError as error:
            raise SlackAPIError(f"Failed to fetch history for {channel_id}: {error}") from error

        messages = []
        for item in response.get("messages", []):
            if not isinstance(item, dict):
                continue
            ts = item.get("ts")
            text = item.get("text", "")
            if not ts or not text:
                continue
            messages.append(
                SlackMessage(
                    channel=channel_id,
                    ts=str(ts),
                    user=item.get("user"),
                    text=text,
                    thread_ts=item.get("thread_ts"),
                    raw=item,
                )
            )

        # Slack returns messages newest-first; reverse to chronological order
        return list(reversed(messages))

    async def get_user_display_name(self, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            response = await self._call_async(self.client.users_info, user=user_id)
        except SlackApiError:
            return user_id

        profile = (response or {}).get("user", {}).get("profile", {})
        display_name = profile.get("display_name") or profile.get("real_name")
        if display_name:
            self._user_cache[user_id] = display_name
            return display_name
        return user_id

    async def post_message(self, channel: str, text: str) -> bool:
        try:
            await self._call_async(self.client.chat_postMessage, channel=channel, text=text)
            return True
        except SlackApiError:
            return False

    async def _call_async(self, func, *args, **kwargs):
        """Run slack_sdk WebClient methods in thread executor with simple retry."""

        loop = asyncio.get_running_loop()

        async def _invoke():
            attempts = 0
            while True:
                attempts += 1
                try:
                    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                except SlackApiError as error:
                    if error.response is not None and error.response.status_code == 429:
                        retry_after = int(error.response.headers.get("Retry-After", self.rate_limit_sleep))
                        await asyncio.sleep(retry_after)
                        continue
                    raise
                except Exception:
                    if attempts >= 3:
                        raise
                    await asyncio.sleep(self.rate_limit_sleep * attempts)

        return await _invoke()
