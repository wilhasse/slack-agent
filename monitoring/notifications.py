"""Notification helpers used by realtime and digest monitor paths."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Optional

import httpx

from .models import NotificationConfig, SlackConfig
from .slack_client import SlackClientWrapper


class NotificationManager:
    """Aggregate all outbound notification mechanisms."""

    def __init__(
        self,
        slack_config: SlackConfig,
        notification_config: NotificationConfig,
        slack_client: Optional[SlackClientWrapper] = None,
    ):
        self.slack_config = slack_config
        self.notification_config = notification_config
        self.slack_client = slack_client
        self._whatsapp_config = self._prepare_whatsapp_config(notification_config.whatsapp or {})

    async def send_slack_message(self, text: str, channel_override: Optional[str] = None) -> bool:
        """Send message either via webhook or chat.postMessage."""
        channel = self._resolve_slack_channel(channel_override)
        if not channel:
            return False

        if self.notification_config.slack_webhook:
            return await self._post_webhook(text)

        if not self.slack_client:
            return False

        return await self.slack_client.post_message(channel=channel, text=text)

    def _resolve_slack_channel(self, override: Optional[str]) -> Optional[str]:
        if override:
            return self._normalize_channel_reference(override)

        if self.slack_config.critical_channel:
            return self._normalize_channel_reference(self.slack_config.critical_channel)

        if self.slack_config.summary_channel_id:
            return self.slack_config.summary_channel_id

        if self.slack_config.summary_channel:
            return self._normalize_channel_reference(self.slack_config.summary_channel)

        return None

    @staticmethod
    def _normalize_channel_reference(value: str) -> str:
        value = value.strip()
        if value.startswith("C") and len(value) > 5:
            return value  # already channel ID
        if value.startswith("#"):
            return value
        return f"#{value}"

    async def _post_webhook(self, text: str) -> bool:
        url = self.notification_config.slack_webhook
        if not url:
            return False
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(url, json={"text": text})
            return response.status_code == 200

    async def send_whatsapp_message(self, message: str) -> bool:
        cfg = self._whatsapp_config
        if not cfg.get("enabled"):
            return False

        account_sid = cfg.get("account_sid")
        auth_token = cfg.get("auth_token")
        from_number = cfg.get("from_number")
        to_number = cfg.get("to_number")
        content_sid = cfg.get("content_sid")
        use_template = cfg.get("use_template", False)

        if not all([account_sid, auth_token, from_number, to_number]):
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload: Dict[str, str]
        if use_template and content_sid:
            payload = {
                "To": to_number,
                "From": from_number,
                "ContentSid": content_sid,
                "ContentVariables": json.dumps({"1": message}),
            }
        else:
            payload = {"To": to_number, "From": from_number, "Body": message}

        auth = (account_sid, auth_token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, data=payload, auth=auth)
            return response.status_code in (200, 201)

    @staticmethod
    def _prepare_whatsapp_config(raw_config: Dict[str, object]) -> Dict[str, object]:
        config = dict(raw_config) if raw_config else {}
        if not config.get("enabled"):
            return config

        # Resolve environment variables
        def _resolve(value: Optional[str]) -> Optional[str]:
            if not value or not isinstance(value, str):
                return value
            value = value.strip()
            if value.startswith("${") and value.endswith("}"):
                return os.getenv(value[2:-1])
            return value

        for key in ("service_file", "account_sid", "auth_token", "from_number", "to_number", "content_sid"):
            config[key] = _resolve(config.get(key))

        if config.get("service_file"):
            parsed = NotificationManager._parse_whatsapp_service_file(config["service_file"])
            for key in ("account_sid", "auth_token", "from", "to", "content_sid"):
                if key in parsed and parsed[key]:
                    normalized_key = "from_number" if key == "from" else "to_number" if key == "to" else key
                    config.setdefault(normalized_key, parsed[key])

        if config.get("to_number") and not str(config["to_number"]).startswith("whatsapp:"):
            config["to_number"] = f"whatsapp:{config['to_number']}"
        if config.get("from_number") and not str(config["from_number"]).startswith("whatsapp:"):
            config["from_number"] = f"whatsapp:{config['from_number']}"

        if not config.get("auth_token") and config.get("auth_token_env"):
            config["auth_token"] = os.getenv(config["auth_token_env"])

        return config

    @staticmethod
    def _parse_whatsapp_service_file(path: str) -> Dict[str, Optional[str]]:
        result: Dict[str, Optional[str]] = {}
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError:
            return result

        import re

        match_account = re.search(r"Accounts/([A-Za-z0-9]+)/Messages", content)
        if match_account:
            result["account_sid"] = match_account.group(1)

        match_to = re.search(r"--data-urlencode 'To=([^']+)'", content)
        if match_to:
            value = match_to.group(1)
            result["to"] = value if value.startswith("whatsapp:") else f"whatsapp:{value}"

        match_from = re.search(r"--data-urlencode 'From=([^']+)'", content)
        if match_from:
            value = match_from.group(1)
            result["from"] = value if value.startswith("whatsapp:") else f"whatsapp:{value}"

        match_content = re.search(r"--data-urlencode 'ContentSid=([^']+)'", content)
        if match_content:
            result["content_sid"] = match_content.group(1)

        match_credentials = re.search(r"-u\s+([A-Za-z0-9]+):([^\\s]+)", content)
        if match_credentials:
            result["account_sid"] = match_credentials.group(1)
            token = match_credentials.group(2)
            if token and not token.startswith("["):
                result["auth_token"] = token

        return result
