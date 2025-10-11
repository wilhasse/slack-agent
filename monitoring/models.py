"""Core dataclasses and enums used across the monitoring system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional


class SeverityLevel(str, Enum):
    """Discrete severity levels used for alert decisions."""

    IGNORE = "IGNORE"
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"

    @classmethod
    def ordered(cls) -> List["SeverityLevel"]:
        """Return severities from lowest to highest."""
        return [cls.IGNORE, cls.NORMAL, cls.IMPORTANT, cls.CRITICAL]

    def at_least(self, other: "SeverityLevel") -> bool:
        """Return True if this severity is greater than or equal to another."""
        order = {level: index for index, level in enumerate(self.ordered())}
        return order[self] >= order[other]


@dataclass
class ChannelRule:
    """Configuration for a monitored Slack channel."""

    id: str
    label: str
    severity_hint: SeverityLevel = SeverityLevel.NORMAL
    recurrence_threshold: int = 3
    critical_keywords: List[str] = field(default_factory=list)
    ignore_patterns: List[str] = field(default_factory=list)
    muted: bool = False


@dataclass
class SlackConfig:
    """Slack authentication and channel targets."""

    bot_token: str
    summary_channel: Optional[str] = None
    summary_channel_id: Optional[str] = None
    critical_channel: Optional[str] = None
    use_socket_mode: bool = False


@dataclass
class NotificationConfig:
    """Notification channel configuration."""

    slack_webhook: Optional[str] = None
    whatsapp: Dict[str, object] = field(default_factory=dict)
    email: Dict[str, object] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """External LLM provider configuration."""

    enabled: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    prompt_template: Optional[str] = None
    timeout_seconds: float = 8.0
    max_tokens: int = 256


@dataclass
class RealtimeMonitorConfig:
    """Configuration for the realtime critical monitor."""

    enabled: bool = True
    check_interval_seconds: int = 30
    severity_threshold: SeverityLevel = SeverityLevel.IMPORTANT
    llm: LLMConfig = field(default_factory=LLMConfig)
    lookback_minutes: int = 60
    duplicate_window_minutes: int = 60


@dataclass
class DigestConfig:
    """Configuration for periodic digests."""

    enabled: bool = True
    interval_minutes: int = 60
    lookback_minutes: int = 60
    include_filtered: bool = True
    send_initial: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig)


@dataclass
class RuntimeConfig:
    """Root configuration object for the monitoring system."""

    slack: SlackConfig
    channels: List[ChannelRule]
    notifications: NotificationConfig
    realtime: RealtimeMonitorConfig
    digest: DigestConfig
    database_path: str = "smart_alerts.db"
    prompt_log_path: Optional[str] = None
    timezone_name: Optional[str] = None


@dataclass
class AlertRecord:
    """Normalized alert data stored in SQLite."""

    message_id: str
    channel_id: str
    channel_label: str
    user: Optional[str]
    text: str
    slack_ts: str
    importance: SeverityLevel
    decision_reason: str
    detected_at: datetime
    event_ts: Optional[datetime] = None
    content_hash: Optional[str] = None
    pattern_signature: Optional[str] = None
    sent_to_slack: bool = False


@dataclass
class AlertDecision:
    """Decision result returned by classifiers."""

    severity: SeverityLevel
    reason: str
    notify: bool
    notify_targets: List[str] = field(default_factory=list)
    recurrence_count: int = 1
    ttl: Optional[timedelta] = None
