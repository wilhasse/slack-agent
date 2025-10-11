#!/usr/bin/env python3
"""Legacy configuration facade preserved for backward compatibility.

The new monitoring pipeline relies on ``monitoring.configuration`` and
``monitoring.models``.  This module wraps that functionality to keep older
scripts (e.g., ``slack_monitor_yaml.py``) working while they are gradually
retired.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from monitoring.configuration import ConfigurationError, load_runtime_config
from monitoring.models import RuntimeConfig


class Config:
    """Compatibility wrapper exposing a subset of the legacy API."""

    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.runtime: RuntimeConfig = load_runtime_config(config_file)

    # ------------------------------------------------------------------
    # Legacy-style helpers (used by slack_monitor_yaml.py)
    # ------------------------------------------------------------------

    @property
    def keywords(self) -> List[str]:
        # Keywords are no longer needed; return empty list for compatibility.
        return []

    @property
    def check_interval(self) -> int:
        return max(5, self.runtime.realtime.check_interval_seconds)

    @property
    def enable_notifications(self) -> bool:
        return bool(self.runtime.notifications.slack_webhook or self.runtime.notifications.whatsapp)

    @property
    def database_path(self) -> str:
        return self.runtime.database_path

    @property
    def mcp_server_config(self) -> Dict[str, Any]:
        """Return a minimal MCP config for scripts that still rely on Claude."""
        bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        mcp_binary = str(Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server")
        return {
            "type": "stdio",
            "command": mcp_binary,
            "args": ["--transport", "stdio"],
            "env": {
                "SLACK_BOT_TOKEN": bot_token,
                "SLACK_MCP_ADD_MESSAGE_TOOL": "true",
            },
        }

    def get_channel_pattern(self) -> str:
        if not self.runtime.channels:
            return "all channels"
        parts = [f"#{rule.label}" for rule in self.runtime.channels]
        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Extended helpers retained for advanced scripts/tests
    # ------------------------------------------------------------------

    @property
    def channel_aliases(self) -> Dict[str, str]:
        return {rule.id: rule.label for rule in self.runtime.channels}

    def resolve_channel_label(self, channel_id: str) -> str:
        label = self.channel_aliases.get(channel_id, channel_id)
        return f"{label} ({channel_id})"

    def get_channel_rule(self, channel: str) -> Dict[str, Any]:
        for rule in self.runtime.channels:
            if rule.id == channel or rule.label == channel.lstrip("#"):
                return {
                    "alias": rule.label,
                    "recurrence_threshold": rule.recurrence_threshold,
                    "importance_hint": rule.severity_hint.value,
                    "patterns_to_watch": rule.critical_keywords,
                    "ignore_patterns": rule.ignore_patterns,
                }
        return {
            "alias": channel,
            "recurrence_threshold": 3,
            "importance_hint": "IMPORTANT",
            "patterns_to_watch": [],
            "ignore_patterns": [],
        }

    def should_ignore_pattern(self, channel_name: str, text: str) -> tuple[bool, str]:
        rule = self.get_channel_rule(channel_name)
        text_lower = text.lower()
        for pattern in rule.get("ignore_patterns", []):
            if pattern.lower() in text_lower:
                return True, f"Matches ignore pattern: {pattern}"
        return False, ""


def load_config(config_file: str = "config.yaml") -> Config:
    return Config(config_file)


if __name__ == "__main__":  # pragma: no cover - manual check helper
    try:
        cfg = load_config()
    except ConfigurationError as error:
        print(f"❌ Failed to load config: {error}")
    else:
        print("✅ Configuration loaded successfully")
        print(f"Channels monitored: {cfg.get_channel_pattern()}")
