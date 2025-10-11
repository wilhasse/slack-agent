"""Configuration loader with backward compatibility for the legacy YAML schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import yaml

from .models import (
    ChannelRule,
    DigestConfig,
    LLMConfig,
    NotificationConfig,
    RealtimeMonitorConfig,
    RuntimeConfig,
    SeverityLevel,
    SlackConfig,
)


class ConfigurationError(RuntimeError):
    """Raised when the configuration file is invalid."""


def _resolve_env(value: Optional[str]) -> Optional[str]:
    """Support ${ENV_VAR} references in YAML values."""
    if value is None or not isinstance(value, str):
        return value
    value = value.strip()
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name)
    return value


def _parse_severity(value: Optional[str], default: SeverityLevel) -> SeverityLevel:
    if not value:
        return default
    try:
        return SeverityLevel(value.upper())
    except ValueError as exc:
        raise ConfigurationError(f"Unknown severity level '{value}'") from exc


def _parse_llm_config(data: Optional[Dict[str, Any]]) -> LLMConfig:
    if not data:
        return LLMConfig(enabled=False)

    enabled = bool(data.get("enabled", False))
    api_key = _resolve_env(data.get("api_key"))
    api_key_env = data.get("api_key_env")
    if api_key_env and not api_key:
        api_key = os.getenv(api_key_env)

    return LLMConfig(
        enabled=enabled,
        provider=data.get("provider"),
        model=data.get("model"),
        endpoint=_resolve_env(data.get("endpoint")),
        api_key=api_key,
        api_key_env=api_key_env,
        prompt_template=_resolve_env(data.get("prompt_template")),
        timeout_seconds=float(data.get("timeout_seconds", 8.0)),
        max_tokens=int(data.get("max_tokens", 256)),
    )


def _parse_notification_config(data: Optional[Dict[str, Any]]) -> NotificationConfig:
    if not data:
        return NotificationConfig()
    slack_webhook = _resolve_env(data.get("slack_webhook"))

    whatsapp = data.get("whatsapp") or {}
    # Resolve env references inside whatsapp config
    for key in ("service_file", "account_sid", "auth_token", "from_number", "to_number", "content_sid"):
        if key in whatsapp:
            whatsapp[key] = _resolve_env(whatsapp[key])

    email = data.get("email") or {}
    if "smtp_password" in email:
        email["smtp_password"] = _resolve_env(email["smtp_password"])

    return NotificationConfig(slack_webhook=slack_webhook, whatsapp=whatsapp, email=email)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be a YAML mapping.")
    return data


def _load_bot_token(slack_section: Dict[str, Any]) -> str:
    token = _resolve_env(slack_section.get("bot_token"))
    token_env = slack_section.get("bot_token_env")

    if not token and token_env:
        token = os.getenv(token_env)

    if not token:
        # Legacy fallback: environment variables used by Claude monitor
        token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_MCP_XOXP_TOKEN")

    if not token:
        raise ConfigurationError("Slack bot token not found. Define slack.bot_token or slack.bot_token_env.")
    return token


def _parse_channel_rules(channels_data: List[Dict[str, Any]]) -> List[ChannelRule]:
    channels: List[ChannelRule] = []
    for entry in channels_data:
        if not isinstance(entry, dict):
            raise ConfigurationError("Each channel entry must be a mapping.")
        channel_id = str(entry.get("id") or entry.get("channel") or "").strip()
        if not channel_id:
            raise ConfigurationError("Channel entry missing 'id'.")
        label = str(entry.get("label") or channel_id)
        severity_hint = _parse_severity(entry.get("severity_hint"), SeverityLevel.NORMAL)
        recurrence_threshold = int(entry.get("recurrence_threshold", 3))
        critical_keywords = [str(item) for item in entry.get("critical_keywords", []) if item]
        ignore_patterns = [str(item) for item in entry.get("ignore_patterns", []) if item]
        muted = bool(entry.get("muted", False))

        channels.append(
            ChannelRule(
                id=channel_id,
                label=label,
                severity_hint=severity_hint,
                recurrence_threshold=max(1, recurrence_threshold),
                critical_keywords=critical_keywords,
                ignore_patterns=ignore_patterns,
                muted=muted,
            )
        )
    return channels


def _convert_legacy_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map legacy config.yaml structure into the new schema."""
    channels = data.get("channels", []) or []
    aliases = data.get("channel_aliases", {}) or {}
    channel_rules = data.get("channel_rules", {}) or {}
    smart_filtering = data.get("smart_filtering", {}) or {}
    smart_summary = data.get("smart_summary", {}) or {}
    advanced = data.get("advanced", {}) or {}

    converted_channels: List[Dict[str, Any]] = []
    for channel_id in channels:
        cid = str(channel_id)
        rule = channel_rules.get(cid, {})
        label = aliases.get(cid, rule.get("alias", cid))
        severity_hint = rule.get("importance_hint", "NORMAL")
        recurrence_threshold = rule.get("recurrence_threshold", 3)
        critical_keywords = rule.get("patterns_to_watch", [])
        ignore_patterns = rule.get("ignore_patterns", [])

        converted_channels.append(
            {
                "id": cid,
                "label": label,
                "severity_hint": severity_hint,
                "recurrence_threshold": recurrence_threshold,
                "critical_keywords": critical_keywords,
                "ignore_patterns": ignore_patterns,
            }
        )

    config_new = {
        "slack": {
            "bot_token_env": "SLACK_BOT_TOKEN",
            "summary_channel": data.get("summary_channel"),
            "summary_channel_id": data.get("summary_channel_id"),
            "critical_channel": data.get("summary_channel"),  # Legacy did not distinguish
        },
        "channels": converted_channels,
        "notifications": {
            "slack_webhook": advanced.get("slack_webhook_url"),
            "whatsapp": smart_summary.get("whatsapp", {}),
        },
        "realtime_monitor": {
            "enabled": True,
            "check_interval_seconds": data.get("check_interval", 60),
            "severity_threshold": smart_filtering.get("min_urgency_level", "IMPORTANT"),
            "duplicate_window_minutes": int(float(smart_filtering.get("duplicate_window_hours", 24)) * 60),
        },
        "digest": {
            "enabled": smart_summary.get("enabled", False),
            "interval_minutes": smart_summary.get("interval_minutes", 60),
            "lookback_minutes": smart_summary.get("lookback_minutes", 60),
            "include_filtered": smart_summary.get("include_filtered", True),
            "send_initial": smart_summary.get("send_initial", False),
        },
        "database": advanced.get("smart_database", "smart_alerts.db"),
        "prompt_log_path": smart_filtering.get("prompt_log_file"),
        "timezone": None,
    }

    return config_new


def load_runtime_config(path: str | Path = "config.yaml") -> RuntimeConfig:
    """Load configuration from YAML, supporting both new and legacy schema."""
    path = Path(path)
    raw = _load_yaml(path)

    if "slack" not in raw or "channels" not in raw or not isinstance(raw["channels"], list):
        raw = _convert_legacy_config(raw)

    slack_section = raw.get("slack") or {}
    bot_token = _load_bot_token(slack_section)

    slack_config = SlackConfig(
        bot_token=bot_token,
        summary_channel=slack_section.get("summary_channel"),
        summary_channel_id=slack_section.get("summary_channel_id"),
        critical_channel=slack_section.get("critical_channel"),
        use_socket_mode=bool(slack_section.get("use_socket_mode", False)),
    )

    channels = _parse_channel_rules(raw.get("channels", []))
    notifications = _parse_notification_config(raw.get("notifications"))

    realtime_section = raw.get("realtime_monitor", {})
    realtime_config = RealtimeMonitorConfig(
        enabled=bool(realtime_section.get("enabled", True)),
        check_interval_seconds=int(realtime_section.get("check_interval_seconds", 30)),
        severity_threshold=_parse_severity(realtime_section.get("severity_threshold"), SeverityLevel.IMPORTANT),
        llm=_parse_llm_config(realtime_section.get("llm")),
        lookback_minutes=int(realtime_section.get("lookback_minutes", 60)),
        duplicate_window_minutes=int(realtime_section.get("duplicate_window_minutes", 60)),
    )

    digest_section = raw.get("digest", {})
    digest_config = DigestConfig(
        enabled=bool(digest_section.get("enabled", False)),
        interval_minutes=int(digest_section.get("interval_minutes", 60)),
        lookback_minutes=int(digest_section.get("lookback_minutes", 60)),
        include_filtered=bool(digest_section.get("include_filtered", True)),
        send_initial=bool(digest_section.get("send_initial", False)),
        llm=_parse_llm_config(digest_section.get("llm")),
    )

    database_path = raw.get("database") or raw.get("database_path") or "smart_alerts.db"
    prompt_log_path = raw.get("prompt_log_path")
    timezone_name = raw.get("timezone")

    return RuntimeConfig(
        slack=slack_config,
        channels=channels,
        notifications=notifications,
        realtime=realtime_config,
        digest=digest_config,
        database_path=database_path,
        prompt_log_path=prompt_log_path,
        timezone_name=timezone_name,
    )
