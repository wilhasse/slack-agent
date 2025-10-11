"""Deterministic heuristics for classifying Slack alerts without heavy LLM usage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import (
    AlertDecision,
    ChannelRule,
    RealtimeMonitorConfig,
    SeverityLevel,
)
from .storage import AlertStore
from .utils import compute_content_hash, normalize_text


@dataclass
class ClassificationContext:
    """Contextual information produced during classification."""

    content_hash: str
    recurrence_count: int
    matched_keyword: Optional[str] = None
    ignored_pattern: Optional[str] = None


class HeuristicClassifier:
    """Fast classifier combining channel hints, keywords, and recurrence logic."""

    def __init__(self, store: AlertStore, config: RealtimeMonitorConfig):
        self.store = store
        self.config = config

    def classify(self, channel_rule: ChannelRule, message_text: str) -> tuple[AlertDecision, ClassificationContext]:
        text = normalize_text(message_text)
        text_lower = text.lower()

        content_hash = compute_content_hash(text, extra_keys=[channel_rule.id])

        # Check ignore patterns first
        for pattern in channel_rule.ignore_patterns:
            pattern_lower = pattern.lower()
            if pattern_lower and pattern_lower in text_lower:
                decision = AlertDecision(
                    severity=SeverityLevel.IGNORE,
                    reason=f"Ignored due to pattern '{pattern}'",
                    notify=False,
                )
                context = ClassificationContext(content_hash=content_hash, recurrence_count=0, ignored_pattern=pattern)
                return decision, context

        severity = channel_rule.severity_hint
        reason_parts = [f"Base severity {severity.value} (channel hint)"]
        matched_keyword: Optional[str] = None

        for keyword in channel_rule.critical_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower and keyword_lower in text_lower:
                severity = SeverityLevel.CRITICAL
                matched_keyword = keyword
                reason_parts.append(f"Matched critical keyword '{keyword}'")
                break

        # Recurrence logic uses count of existing alerts with same hash
        prior_occurrences = self.store.count_recent_occurrences(
            content_hash,
            window_minutes=self.config.duplicate_window_minutes,
        )

        recurrence_threshold = max(1, channel_rule.recurrence_threshold)
        if prior_occurrences + 1 >= recurrence_threshold and severity != SeverityLevel.CRITICAL:
            severity = SeverityLevel.CRITICAL
            reason_parts.append(f"Recurrence threshold reached ({prior_occurrences + 1}/{recurrence_threshold})")
        elif prior_occurrences > 0:
            reason_parts.append(f"Seen {prior_occurrences} time(s) recently")

        notify = severity.at_least(self.config.severity_threshold)
        decision = AlertDecision(
            severity=severity,
            reason="; ".join(reason_parts),
            notify=notify,
            notify_targets=["slack"] if notify else [],
            recurrence_count=prior_occurrences + 1,
        )

        context = ClassificationContext(
            content_hash=content_hash,
            recurrence_count=prior_occurrences + 1,
            matched_keyword=matched_keyword,
        )
        return decision, context
