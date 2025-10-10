#!/usr/bin/env python3
"""
Smart Slack Monitor with Intelligent Alert Filtering

This enhanced monitor:
- Tracks alert history to detect patterns
- Deduplicates similar alerts to avoid noise
- Only sends truly urgent or recurrent issues to Slack
- Uses Claude to analyze if an alert is worth sending
"""

import asyncio
import json
import hashlib
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from slack_monitor import SlackMonitor, SlackMessage
from config_loader import Config


@dataclass
class Alert:
    """Represents a processed alert"""
    message_id: str
    channel: str
    user: str
    text: str
    timestamp: Optional[str]
    importance: str
    reason: str
    content_hash: str
    pattern_signature: str
    slack_ts: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    occurrence_count: int = 1
    first_seen_dt: Optional[datetime] = None
    last_seen_dt: Optional[datetime] = None
    insights: Optional[Dict[str, str]] = None
    history_entries: List[Dict[str, Any]] = field(default_factory=list)
    history_context: Optional[str] = None
    escalation_reason: Optional[str] = None
    sent_to_slack: bool = False


class SmartSlackMonitor(SlackMonitor):
    """
    Enhanced monitor that intelligently filters alerts before sending to Slack.

    Features:
    - Deduplication: Avoids sending the same alert multiple times
    - Pattern detection: Identifies recurrent issues
    - Smart filtering: Only sends truly urgent/important alerts
    - Historical analysis: Compares with previous alerts to reduce noise
    """

    def __init__(
        self,
        db_path: str = "smart_alerts.db",
        min_urgency_level: str = "IMPORTANT",  # Only send IMPORTANT or CRITICAL
        duplicate_window_hours: int = 24,  # Don't resend similar alerts within 24h
        critical_dedup_hours: int = 2,  # Resend CRITICAL alerts every 2h if still active
        recurrence_threshold: int = 3,  # Alert if same issue happens 3+ times (default fallback)
        slack_webhook_url: str = None,  # Alternative to MCP for sending messages
        interaction_check_interval: int = 5,  # Check for interactions every 5 seconds
        active_hours: Optional[Dict[str, str]] = None,  # Optional active monitoring window
        prompt_log_file: Optional[str] = None,  # Optional path to log prompts sent to Claude
        summary_schedule: Optional[Dict[str, Any]] = None,  # Periodic summary configuration
        config: Config = None,  # Configuration with channel rules
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.min_urgency_level = min_urgency_level
        self.duplicate_window_hours = duplicate_window_hours
        self.critical_dedup_hours = critical_dedup_hours
        self.recurrence_threshold = recurrence_threshold  # Default fallback
        self.slack_webhook_url = slack_webhook_url
        self.interaction_check_interval = max(1, interaction_check_interval)
        self.last_interaction_check = datetime.now() - timedelta(seconds=self.interaction_check_interval)
        self._client_lock = asyncio.Lock()  # Prevent concurrent Claude queries
        self._summary_channel_id = None  # Cache channel ID for faster lookups
        self._responded_messages = set()  # Track which messages we've already responded to
        self._last_message_timestamp = 0.0  # Track timestamp of last message seen in summary channel
        self.config = config  # Store config for channel-specific rules
        self._channel_aliases = config.channel_aliases if config else {}
        tzinfo = datetime.now().astimezone().tzinfo
        self._local_timezone = tzinfo if tzinfo else timezone.utc
        self._initial_cycle_completed = False
        self._summary_channel_ref = self._coerce_channel_reference(getattr(self, "summary_channel", None))
        self._active_hours, self._active_hours_label = self._parse_active_hours(active_hours)
        self._outside_hours_logged = False
        self._summary_schedule = self._prepare_summary_schedule(summary_schedule)
        self._summary_schedule_label = self._summary_schedule.get("label")
        self._summary_task: Optional[asyncio.Task] = None
        self._prompt_log_file = Path(prompt_log_file).expanduser() if prompt_log_file else None
        self._prompt_log_lock = asyncio.Lock()

        self._init_database()

    @staticmethod
    def _coerce_channel_reference(channel: Optional[str]) -> Optional[str]:
        """Return channel identifier without leading # when using names."""
        if not channel:
            return None
        channel = channel.strip()
        return channel[1:] if channel.startswith("#") else channel

    def _get_summary_channel_reference(self) -> Optional[str]:
        """Prefer cached channel ID, fallback to sanitized channel name."""
        if self._summary_channel_id:
            return self._summary_channel_id
        return self._summary_channel_ref

    async def _log_prompt(self, label: str, prompt_text: str):
        """Append prompt text to configured log file with timestamp."""
        if not self._prompt_log_file:
            return

        try:
            async with self._prompt_log_lock:
                self._prompt_log_file.parent.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with self._prompt_log_file.open('a', encoding='utf-8') as log_file:
                    log_file.write(f"[{timestamp}] {label}\n")
                    log_file.write(prompt_text.strip() + "\n\n")
        except Exception as error:
            print(f"⚠️  Não foi possível registrar prompt ({label}): {error}")

    def _prepare_summary_schedule(self, schedule: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize summary schedule configuration."""
        default_schedule = {
            "enabled": False,
            "interval_minutes": 60,
            "lookback_minutes": 60,
            "max_alerts": 10,
            "include_filtered": False,
            "send_initial": False,
        }

        if not schedule:
            return default_schedule

        enabled = bool(schedule.get("enabled", False))
        interval_minutes = schedule.get("interval_minutes", default_schedule["interval_minutes"])
        lookback_minutes = schedule.get("lookback_minutes", default_schedule["lookback_minutes"])
        max_alerts = schedule.get("max_alerts", default_schedule["max_alerts"])
        include_filtered = bool(schedule.get("include_filtered", default_schedule["include_filtered"]))
        send_initial = bool(schedule.get("send_initial", default_schedule["send_initial"]))

        try:
            interval_minutes = max(5, int(interval_minutes))
        except (TypeError, ValueError):
            interval_minutes = default_schedule["interval_minutes"]

        try:
            lookback_minutes = max(5, int(lookback_minutes))
        except (TypeError, ValueError):
            lookback_minutes = default_schedule["lookback_minutes"]

        try:
            max_alerts = max(3, int(max_alerts))
        except (TypeError, ValueError):
            max_alerts = default_schedule["max_alerts"]

        # Get digest_only_mode setting
        digest_only_mode = bool(schedule.get("digest_only_mode", False))

        schedule_normalized = {
            "enabled": enabled,
            "interval_minutes": interval_minutes,
            "interval_seconds": interval_minutes * 60,
            "lookback_minutes": lookback_minutes,
            "lookback_delta": timedelta(minutes=lookback_minutes),
            "max_alerts": max_alerts,
            "include_filtered": include_filtered,
            "send_initial": send_initial,
            "digest_only_mode": digest_only_mode,
            "whatsapp": self._normalize_whatsapp_config(schedule.get("whatsapp")),
        }

        schedule_normalized["label"] = f"cada {interval_minutes} min (janela {lookback_minutes} min)"
        return schedule_normalized

    @staticmethod
    def _normalize_whatsapp_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize WhatsApp delivery configuration."""
        defaults = {
            "enabled": False,
            "service_file": "whatsapp.txt",
            "account_sid": None,
            "auth_token": None,
            "auth_token_env": "TWILIO_AUTH_TOKEN",
            "from_number": None,
            "to_number": None,
            "use_template": False,
            "content_sid": None,
        }

        if not config:
            return defaults

        normalized = defaults.copy()
        normalized.update({k: v for k, v in config.items() if v is not None})

        def _resolve_env(value: Optional[str]) -> Optional[str]:
            if not value or not isinstance(value, str):
                return value
            value = value.strip()
            if value.startswith("${") and value.endswith("}"):
                return os.getenv(value[2:-1])
            return value

        normalized["account_sid"] = _resolve_env(normalized.get("account_sid"))
        normalized["auth_token"] = _resolve_env(normalized.get("auth_token"))
        normalized["from_number"] = _resolve_env(normalized.get("from_number"))
        normalized["to_number"] = _resolve_env(normalized.get("to_number"))
        normalized["service_file"] = _resolve_env(normalized.get("service_file"))
        normalized["content_sid"] = _resolve_env(normalized.get("content_sid"))

        # Basic sanitation
        for key in ("from_number", "to_number"):
            number = normalized.get(key)
            if number and not number.startswith("whatsapp:"):
                normalized[key] = f"whatsapp:{number}"

        return normalized

    def _parse_active_hours(
        self,
        active_hours: Optional[Dict[str, str]],
    ) -> Tuple[Optional[Tuple[time, time]], Optional[str]]:
        """Validate and parse active hours window from configuration."""
        if not active_hours:
            return None, None

        start_raw = active_hours.get("start")
        end_raw = active_hours.get("end")

        if not start_raw or not end_raw:
            return None, None

        try:
            start_time = datetime.strptime(str(start_raw), "%H:%M").time()
            end_time = datetime.strptime(str(end_raw), "%H:%M").time()
        except ValueError:
            print(f"⚠️  Horário inválido em active_hours: start={start_raw}, end={end_raw}")
            return None, None

        label = f"{start_raw}-{end_raw}"
        return (start_time, end_time), label

    def _is_within_active_hours(self, current_time: time) -> bool:
        """Return True if current_time falls within configured active window."""
        if not self._active_hours:
            return True

        start, end = self._active_hours

        if start == end:
            # Treat identical times as 24h monitoring
            return True

        if start <= end:
            return start <= current_time < end

        # Window spans midnight (e.g., 22:00 - 06:00)
        return current_time >= start or current_time < end

    def _get_next_active_start(self, now_local: datetime) -> Optional[datetime]:
        """Compute the next datetime when monitoring becomes active."""
        if not self._active_hours:
            return None

        start, end = self._active_hours
        current_time = now_local.time()

        start_dt = datetime.combine(now_local.date(), start).replace(tzinfo=self._local_timezone)

        if self._is_within_active_hours(current_time):
            return now_local

        if start <= end:
            if current_time < start:
                return start_dt
            # After end -> next day
            return start_dt + timedelta(days=1)

        # Overnight window. Outside happens between end and start.
        if current_time < start and current_time >= end:
            return start_dt

        if current_time >= start:
            # Already past start (shouldn't happen here), next day to be safe
            return start_dt + timedelta(days=1)

        # current_time < end -> we are before end portion (still active), but fallback
        return start_dt

    def _init_database(self):
        """Initialize database for alert tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Alert history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                user TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                importance TEXT NOT NULL,
                reason TEXT,
                content_hash TEXT NOT NULL,
                pattern_signature TEXT NOT NULL,
                sent_to_slack BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id)
            )
        """)

        # Pattern tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_signature TEXT NOT NULL,
                first_seen DATETIME,
                last_seen DATETIME,
                occurrence_count INTEGER DEFAULT 1,
                last_sent DATETIME,
                UNIQUE(pattern_signature)
            )
        """)

        # Alert decision log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                decision TEXT NOT NULL,
                reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(alert_id) REFERENCES alerts(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON alerts(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern ON alerts(pattern_signature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON alerts(created_at)")

        conn.commit()
        conn.close()

    def _compute_content_hash(self, text: str) -> str:
        """Compute hash of message content for deduplication"""
        # Normalize text: lowercase, remove extra spaces
        normalized = " ".join(text.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _extract_pattern_signature(self, text: str, channel: str) -> str:
        """
        Extract a pattern signature from the message using channel-specific patterns.

        This identifies the "type" of alert (e.g., "LOAD alert in cslog-alertas-mc")
        regardless of specific details.
        """
        text_lower = text.lower()
        patterns = []

        # If config is available, use channel-specific patterns
        if self.config:
            # Check for channel-specific pattern matches
            pattern_match = self.config.get_pattern_match(channel, text)
            if pattern_match['matched']:
                # Use the specific pattern name
                patterns.append(pattern_match['pattern_name'].lower().replace(' ', '-'))

            # Also check channel's patterns_to_watch
            channel_rule = self.config.get_channel_rule(channel)
            patterns_to_watch = channel_rule.get('patterns_to_watch', [])
            for pattern in patterns_to_watch:
                if pattern.lower() in text_lower:
                    patterns.append(pattern.lower())

        # Fallback to generic patterns if no specific patterns found
        if not patterns:
            if "error" in text_lower or "erro" in text_lower:
                patterns.append("error")
            if "timeout" in text_lower:
                patterns.append("timeout")
            if "failed" in text_lower or "falha" in text_lower:
                patterns.append("failed")
            if "down" in text_lower or "offline" in text_lower:
                patterns.append("down")
            if "load" in text_lower:
                patterns.append("load")
            if "memory" in text_lower or "memória" in text_lower:
                patterns.append("memory")
            if "database" in text_lower or "db" in text_lower:
                patterns.append("database")
            if "lock" in text_lower:
                patterns.append("lock")

        signature = f"{channel}:{'-'.join(sorted(patterns)) if patterns else 'general'}"
        return signature

    def _is_duplicate(self, content_hash: str) -> bool:
        """Check if we've seen this exact message recently"""
        return self._is_duplicate_within_hours(content_hash, self.duplicate_window_hours)

    def _is_duplicate_within_hours(self, content_hash: str, hours: int) -> bool:
        """Check if we've seen this exact message within specific hours"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE content_hash = ?
            AND created_at > datetime('now', '-' || ? || ' hours')
        """, (content_hash, hours))

        count = cursor.fetchone()[0]
        conn.close()

        return count > 0

    def _update_pattern_tracking(self, pattern_signature: str) -> Dict[str, Any]:
        """Update pattern occurrence tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if pattern exists
        cursor.execute("""
            SELECT id, first_seen, last_seen, occurrence_count, last_sent
            FROM patterns
            WHERE pattern_signature = ?
        """, (pattern_signature,))

        result = cursor.fetchone()

        if result:
            # Update existing pattern
            pattern_id, first_seen, last_seen, count, last_sent = result
            new_count = count + 1
            now_utc = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                UPDATE patterns
                SET last_seen = CURRENT_TIMESTAMP,
                    occurrence_count = ?
                WHERE id = ?
            """, (new_count, pattern_id))

            pattern_info = {
                "is_new": False,
                "occurrence_count": new_count,
                "first_seen": first_seen,
                "last_seen": now_utc,
                "last_sent": last_sent
            }
        else:
            now_utc = datetime.now(timezone.utc).isoformat()
            # New pattern
            cursor.execute("""
                INSERT INTO patterns (pattern_signature, first_seen, last_seen)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (pattern_signature,))

            pattern_info = {
                "is_new": True,
                "occurrence_count": 1,
                "first_seen": now_utc,
                "last_seen": now_utc,
                "last_sent": None
            }

        conn.commit()
        conn.close()

        return pattern_info

    def _mark_pattern_sent(self, pattern_signature: str):
        """Mark that we've sent an alert for this pattern"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE patterns
            SET last_sent = CURRENT_TIMESTAMP
            WHERE pattern_signature = ?
        """, (pattern_signature,))

        conn.commit()
        conn.close()

    def _save_alert(self, alert: Alert, sent: bool = False):
        """Save alert to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO alerts
                (message_id, channel, user, text, timestamp, importance, reason,
                 content_hash, pattern_signature, sent_to_slack)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.message_id,
                alert.channel,
                alert.user,
                alert.text,
                alert.timestamp,
                alert.importance,
                alert.reason,
                alert.content_hash,
                alert.pattern_signature,
                sent
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            # Already exists, skip
            pass
        finally:
            conn.close()

    def _log_decision(self, alert: Alert, decision: str, reason: str):
        """Log why we decided to send or skip an alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get alert ID
        cursor.execute("SELECT id FROM alerts WHERE message_id = ?", (alert.message_id,))
        result = cursor.fetchone()

        if result:
            alert_id = result[0]
            cursor.execute("""
                INSERT INTO decision_log (alert_id, decision, reason)
                VALUES (?, ?, ?)
            """, (alert_id, decision, reason))
            conn.commit()

        conn.close()

    async def _should_send_alert(self, alert: Alert, pattern_info: Dict[str, Any]) -> tuple[bool, str]:
        """
        Intelligently decide if this alert should be sent to Slack using channel-specific rules.

        Returns: (should_send, reason)
        """
        pattern_match_info: Dict[str, Any] = {'matched': False}

        # Rule 0: Check ignore patterns first (channel-specific)
        if self.config:
            should_ignore, ignore_reason = self.config.should_ignore_pattern(alert.channel, alert.text)
            if should_ignore:
                return False, f"🚫 Ignored: {ignore_reason}"

        # Rule 0.5: Capture pattern metadata (importance overrides, custom thresholds)
        if self.config:
            pattern_match_info = self.config.get_pattern_match(alert.channel, alert.text)
            if pattern_match_info['matched'] and pattern_match_info.get('min_importance'):
                required_importance = pattern_match_info['min_importance']
                if alert.importance != required_importance:
                    return False, f"Pattern requires {required_importance} but alert is {alert.importance}"

        # Determine recurrence threshold (channel and pattern specific)
        required_threshold = self.recurrence_threshold  # Default fallback
        if self.config:
            # Prefer the explicit pattern name for threshold lookup when available
            pattern_key = None
            if pattern_match_info.get('matched'):
                pattern_key = pattern_match_info.get('pattern_name')
            required_threshold = self.config.get_recurrence_threshold(
                alert.channel,
                pattern_match=pattern_key or alert.pattern_signature
            )

        # Track whether recurrence should override normal filtering
        recurrence_triggered = False
        recurrence_reason = ""
        recurrence_block_reason = ""

        if pattern_info["occurrence_count"] >= required_threshold:
            recurrence_reason = f"Recurrent issue ({pattern_info['occurrence_count']} occurrences)"

            if pattern_info["last_sent"]:
                try:
                    last_sent = datetime.fromisoformat(pattern_info["last_sent"])
                    hours_since = (datetime.now() - last_sent).total_seconds() / 3600
                except ValueError:
                    last_sent = None

                if last_sent:
                    if hours_since < self.duplicate_window_hours:
                        recurrence_block_reason = f"Pattern already sent {hours_since:.1f}h ago"
                    else:
                        recurrence_triggered = True
                else:
                    recurrence_triggered = True
            else:
                recurrence_triggered = True

        # Rule 1: Only send if meets minimum urgency
        if alert.importance in {"NORMAL", "IGNORE"}:
            if recurrence_triggered and self.min_urgency_level != "CRITICAL":
                escalation_note = f"(escalated from {alert.importance})"
                return True, f"{recurrence_reason} {escalation_note}".strip()
            return False, f"Below minimum urgency ({self.min_urgency_level})"

        if self.min_urgency_level == "CRITICAL" and alert.importance != "CRITICAL":
            return False, f"Not critical (only sending CRITICAL alerts)"

        # Rule 2: CRITICAL alerts - shorter dedup window (more aggressive)
        if alert.importance == "CRITICAL":
            # Check for emergency escalation keywords
            emergency_keywords = [
                "catastrophic", "catastrófico",
                "urgent action required", "ação urgente",
                "immediate", "imediato",
                "emergency", "emergência",
                "top priority", "prioridade máxima",
                "rapid", "rápido",
                "runaway", "descontrolado",
                "explosion", "explosão"
            ]

            text_lower = alert.text.lower() if alert.text else ""
            reason_lower = alert.reason.lower() if alert.reason else ""
            combined = text_lower + " " + reason_lower

            is_emergency = any(keyword in combined for keyword in emergency_keywords)

            # Emergency override: send immediately regardless of duplicates
            if is_emergency:
                return True, "⚠️ EMERGENCY OVERRIDE - Catastrophic/urgent situation detected!"

            # For non-emergency CRITICAL, check dedup if configured
            if self.critical_dedup_hours > 0:
                is_recent_duplicate = self._is_duplicate_within_hours(alert.content_hash, hours=self.critical_dedup_hours)
                if is_recent_duplicate:
                    return False, f"Critical alert duplicate within {self.critical_dedup_hours}h (still being worked on)"
                else:
                    return True, f"Critical alert - sending (no duplicate in last {self.critical_dedup_hours}h)"
            else:
                # Dedup disabled for CRITICAL - always send
                return True, "Critical alert - sending (dedup disabled for CRITICAL)"

        # Rule 3: Skip if duplicate within full time window (for IMPORTANT and below)
        if alert.importance != "CRITICAL" and not recurrence_triggered:
            if self._is_duplicate(alert.content_hash):
                return False, f"Duplicate alert within {self.duplicate_window_hours}h window"

        # Rule 4: If recurrence triggered, allow escalation (deduplicated above)
        if recurrence_triggered:
            return True, recurrence_reason

        # Rule 5: For new important issues - ask Claude for final decision
        if pattern_info["is_new"]:
            # Use Claude to make final decision based on context
            should_send = await self._ask_claude_for_decision(alert, pattern_info)
            if should_send:
                return True, "Claude determined this is worth sending"
            else:
                return False, "Claude determined this is not urgent enough"

        if recurrence_block_reason:
            return False, recurrence_block_reason

        return False, f"Not recurrent enough ({pattern_info['occurrence_count']}/{required_threshold} occurrences)"

    async def _ask_claude_for_decision(self, alert: Alert, pattern_info: Dict[str, Any]) -> bool:
        """
        Ask Claude if this alert is worth sending to the summary channel.

        This adds an extra layer of intelligence - Claude can understand context
        that simple rules might miss.
        """
        if not self.client:
            # Default to being conservative
            return False

        query = f"""Analyze this Slack alert and decide if it's worth sending to our monitoring channel.

Alert Details:
- Channel: #{alert.channel}
- User: @{alert.user}
- Message: "{alert.text}"
- Importance: {alert.importance}
- Reason: {alert.reason}
- Pattern: This is a {"NEW" if pattern_info["is_new"] else "KNOWN"} type of alert
- Occurrences: {pattern_info["occurrence_count"]} time(s)

Context:
We want to avoid channel pollution. Only send alerts that:
1. Indicate real problems requiring human attention
2. Are not routine/automated notifications
3. Contain actionable information
4. Are not duplicates of what we already know

Should we send this to the monitoring channel? Answer ONLY with "YES" or "NO" and a brief reason."""

        try:
            await self._log_prompt("claude_decision", query)
            await self.client.query(query)
            response, _ = await self._collect_response_text(timeout=self.response_timeout)

            if not response.strip():
                return False

            response_upper = response.upper().strip()
            if response_upper.startswith("YES"):
                return True
            return False
        except Exception as e:
            print(f"⚠️  Error asking Claude for decision: {e}")
            # Default to not sending if there's an error
            return False

    async def _check_for_interactions(self):
        """Check if anyone is asking questions in the summary channel - optimized to only query when new messages exist"""
        # Check if interactive mode is enabled
        if not getattr(self, 'interactive_mode', False):
            return

        if not self.summary_channel or not self.client:
            return

        if self._active_hours and not self._is_within_active_hours(datetime.now(self._local_timezone).time()):
            return

        # Try to acquire lock, but don't wait if alerts are being checked
        if self._client_lock.locked():
            # Skip this check if alert monitoring is running (silent - no print spam)
            return

        # Use lock to prevent concurrent Claude queries
        async with self._client_lock:
            # Use cached channel ID if available (much faster!)
            channel_ref = self._get_summary_channel_reference()
            if not channel_ref:
                return

            # OPTIMIZATION: Use last seen message timestamp to avoid unnecessary LLM calls
            # Only query Claude if there might be messages newer than what we've seen

            # Initialize timestamp to current time if this is the first check (skip old history)
            if self._last_message_timestamp == 0.0:
                self._last_message_timestamp = datetime.now().timestamp()
                print(f"   Initialized interaction tracking (will only check for new messages from now on)")
                self.last_interaction_check = datetime.now()
                return

            oldest_timestamp = self._last_message_timestamp

            # Quick lightweight check: are there any messages newer than our last seen timestamp?
            quick_check_query = (
                f"Use mcp__slack__conversations_history to fetch messages from \"{channel_ref}\" "
                f"newer than ts {oldest_timestamp}. "
                "Count only HUMAN messages (ignore bot messages). "
                "Reply with ONLY a number: the count of human messages found."
            )

            try:
                # Step 1: Quick count check (lightweight - just get message count)
                await self.client.query(quick_check_query)
                count_response, _ = await self._collect_response_text(timeout=15)

                # Extract number from response
                import re
                match = re.search(r'\d+', count_response)
                message_count = int(match.group()) if match else 0

                if message_count == 0:
                    # No new messages - skip expensive processing (silent)
                    self.last_interaction_check = datetime.now()
                    return

                # Step 2: There ARE new messages - fetch and process them
                print(f"💬 Found {message_count} new message(s) in #{self.summary_channel}")

                fetch_query = (
                    f"Use mcp__slack__conversations_history to fetch messages from \"{channel_ref}\" "
                    f"newer than ts {oldest_timestamp}. Return human messages only."
                    "\nFor each message, output:"
                    "\n---INTERACTION---"
                    "\nUser: <username>"
                    "\nText: <message text>"
                    "\nTimestamp: <ts value>"
                    "\n---END INTERACTION---"
                )

                await self.client.query(fetch_query)
                response_text, _ = await self._collect_response_text(timeout=self.response_timeout)

                # Check if there are interactions
                if "---INTERACTION---" in response_text:
                    await self._handle_interaction(response_text)

                    # Update last seen timestamp to newest message
                    # Extract all timestamps and use the max
                    timestamps = re.findall(r'Timestamp:\s*([\d.]+)', response_text)
                    if timestamps:
                        self._last_message_timestamp = max(float(ts) for ts in timestamps)

                # Update last interaction check time
                self.last_interaction_check = datetime.now()

            except Exception as e:
                print(f"⚠️ Error checking interactions: {e}")
                # Still update check time to avoid getting stuck
                self.last_interaction_check = datetime.now()

    async def _handle_interaction(self, interaction_text: str):
        """Respond to user questions with context from alert history"""
        # Extract user, question, and timestamp
        lines = interaction_text.split('\n')
        user = ""
        question = ""
        timestamp = ""

        for line in lines:
            if line.startswith("User:"):
                user = line.replace("User:", "").strip()
            elif line.startswith("Text:"):
                question = line.replace("Text:", "").strip()
            elif line.startswith("Timestamp:"):
                timestamp = line.replace("Timestamp:", "").strip()

        if not question:
            return

        # Create unique ID using timestamp if available, otherwise use user:question
        if timestamp:
            message_id = hashlib.md5(f"{timestamp}:{user}:{question}".encode()).hexdigest()
        else:
            message_id = hashlib.md5(f"{user}:{question}".encode()).hexdigest()

        # Check if we already responded to this message
        if message_id in self._responded_messages:
            print(f"   Already responded to this message, skipping")
            return

        print(f"   Question from @{user}: {question[:60]}...")

        # Get recent alert context from database (COMPACT - only last 6 hours, top 5 alerts)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT channel, text, importance, created_at
            FROM alerts
            WHERE created_at > datetime('now', '-6 hours')
              AND importance IN ('CRITICAL', 'IMPORTANT')
            ORDER BY created_at DESC
            LIMIT 5
        """)

        recent_alerts = cursor.fetchall()
        conn.close()

        # Build COMPACT context for Claude (no repetition, short previews)
        context_parts = []
        for channel, text, importance, created_at in recent_alerts:
            # Very short preview (40 chars max)
            preview = text[:40] if text else "sem texto"
            context_parts.append(f"[{importance[0]}] #{channel}: {preview}")

        context = "\n".join(context_parts) if context_parts else "Nenhum alerta recente"

        # Ask Claude to respond with context (COMPACT prompt)
        response_query = f"""Pergunta: "{question}"

Contexto (últimas 6h):
{context}

Responda em 1-2 frases curtas em PT-BR."""

        try:
            await self._log_prompt("interaction_response", response_query)
            await self.client.query(response_query)
            response_text, _ = await self._collect_response_text(timeout=self.response_timeout)

            # Send response to Slack
            if response_text.strip():
                reply = f"💬 @{user}: {response_text.strip()}"
                success = await self._send_to_slack(reply)
                if success:
                    print(f"   ✅ Responded to @{user}")
                    # Mark this message as responded to avoid duplicates
                    self._responded_messages.add(message_id)
                    # Keep set size manageable (max 100 recent messages)
                    if len(self._responded_messages) > 100:
                        self._responded_messages.pop()
                else:
                    print(f"   ❌ Failed to send response")

        except Exception as e:
            print(f"❌ Error generating response: {e}")

    async def check_messages(self) -> List[SlackMessage]:
        """
        Override check_messages to add intelligent filtering.

        This method:
        1. Gets messages from Slack (via parent class)
        2. Analyzes each message
        3. Checks for duplicates and patterns
        4. Only sends truly urgent/recurrent alerts to Slack
        5. Checks for user interactions in summary channel
        """
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        now_local = datetime.now(self._local_timezone)
        if self._active_hours:
            if not self._is_within_active_hours(now_local.time()):
                if not self._outside_hours_logged:
                    next_start = self._get_next_active_start(now_local)
                    next_start_str = next_start.strftime('%d/%m %H:%M') if next_start else "horário configurado"
                    label = self._active_hours_label or "janela configurada"
                    print(f"⏸️  Fora da janela ativa ({label}); aguardando até {next_start_str}")
                    self._outside_hours_logged = True
                self.last_check_time = now_local
                return []
            if self._outside_hours_logged:
                label = f" ({self._active_hours_label})" if self._active_hours_label else ""
                print(f"▶️  Janela ativa retomada{label}")
            self._outside_hours_logged = False

        # Use lock to prevent concurrent Claude queries
        async with self._client_lock:
            # Get base analysis from parent class
            print("\n🔍 Fetching and analyzing messages...")

            # Calculate time window
            minutes_ago = int((datetime.now() - self.last_check_time).total_seconds() / 60)

            # Build query
            if self.channels_to_monitor:
                channel_list = ", ".join(self.channels_to_monitor)
                query = f"""USE Slack tools to check messages from: {channel_list}

Look at messages from the last {minutes_ago} minutes.

For EACH message you find, analyze it and provide in this EXACT format:

---MESSAGE---
Channel: [channel name]
User: [username]
Timestamp: [exact Slack message ts value]
Text: [full message text]
Importance: [CRITICAL/IMPORTANT/NORMAL/IGNORE]
Reason: [why this matters or doesn't]
---END MESSAGE---

IMPORTANT: Always include the Slack message timestamp EXACTLY as returned by the tool (the ts field). Do not guess or reformat it.
Responda em Português do Brasil e mantenha os títulos exatamente como especificado.
Seja minucioso - preciso de TODOS os campos para cada mensagem."""
            else:
                query = f"""USE Slack tools to search for messages with keywords: {", ".join(self.keywords)}

From the last {minutes_ago} minutes.

For EACH message found, provide in this EXACT format:

---MESSAGE---
Channel: [channel name]
User: [username]
Timestamp: [exact Slack message ts value]
Text: [full message text]
Importance: [CRITICAL/IMPORTANT/NORMAL/IGNORE]
Reason: [why this matters]
---END MESSAGE---

IMPORTANT: Always include the Slack message timestamp EXACTLY as returned by the tool (the ts field). Do not guess or reformat it.
Responda em Português do Brasil e mantenha os títulos exatamente como especificado.
Seja minucioso - preciso de TODOS os campos para cada mensagem."""

            await self._log_prompt("check_messages", query)
            await self.client.query(query)

            raw_analysis, _ = await self._collect_response_text(timeout=self.response_timeout)

            if not raw_analysis.strip():
                print("⚠️ No analysis response received from Claude; skipping this cycle")
                self.last_check_time = datetime.now()
                return []

            print(f"\n📊 Raw Analysis:\n{raw_analysis}\n")

            # Parse Claude's response into alerts
            alerts = self._parse_analysis(raw_analysis)

            print(f"\n📋 Found {len(alerts)} messages to analyze")

            # Process each alert
            alerts_to_send = []
            previous_check_time = self.last_check_time
            now_utc = datetime.now(timezone.utc)

            if previous_check_time.tzinfo is None:
                window_start_utc = previous_check_time.replace(tzinfo=self._local_timezone).astimezone(timezone.utc)
            else:
                window_start_utc = previous_check_time.astimezone(timezone.utc)

            initial_cutoff_utc = now_utc - timedelta(minutes=60)

            for alert in alerts:
                alert_dt = self._timestamp_to_datetime(alert.timestamp)
                alert_dt_utc = alert_dt.astimezone(timezone.utc) if alert_dt else None

                if alert_dt_utc:
                    if self._initial_cycle_completed:
                        if alert_dt_utc <= window_start_utc:
                            print(f"⏭️  Skipping stale alert from {alert_dt_utc.isoformat()} (before last check window)")
                            continue
                    else:
                        if alert_dt_utc < initial_cutoff_utc:
                            print(f"⏭️  Skipping startup alert from {alert_dt_utc.isoformat()} (>60m old)")
                            continue
                else:
                    print("⏭️  Skipping alert without valid timestamp information")
                    continue

                if self._message_already_processed(alert.message_id):
                    print(f"⏭️  Already processed Slack ts {alert.slack_ts or alert.timestamp}")
                    continue

                self.seen_messages.add(alert.message_id)
                if len(self.seen_messages) > 2000:
                    self.seen_messages.pop()

                # Compute signatures
                alert.content_hash = self._compute_content_hash(alert.text)
                alert.pattern_signature = self._extract_pattern_signature(alert.text, alert.channel)

                # Update pattern tracking
                pattern_info = self._update_pattern_tracking(alert.pattern_signature)

                # Decide if we should send this alert
                should_send, reason = await self._should_send_alert(alert, pattern_info)
                alert.escalation_reason = reason

                # Save to database
                self._save_alert(alert, sent=should_send)
                self._log_decision(alert, "SEND" if should_send else "SKIP", reason)

                # Log decision with preview
                status_icon = "✅" if should_send else "⏭️"
                msg_preview = alert.text[:60] + "..." if len(alert.text) > 60 else alert.text
                channel_label = self._format_channel_for_summary(alert.channel)
                print(f"{status_icon} [{alert.importance}] {channel_label} - {reason}")
                if should_send:
                    print(f"   📝 Message: \"{msg_preview}\"")

                if should_send:
                    try:
                        await self._enrich_alert(alert, pattern_info)
                    except Exception as enrich_error:
                        print(f"⚠️  Erro ao enriquecer alerta: {enrich_error}")
                    alerts_to_send.append(alert)
                    self._mark_pattern_sent(alert.pattern_signature)

            # Update last check time
            self.last_check_time = datetime.now()
            self._initial_cycle_completed = True

            # Check if we should send full analysis instead
            send_full_analysis = getattr(self, 'send_full_analysis', False)

            if self.summary_channel:
                if send_full_analysis:
                    # Send Claude's complete raw analysis
                    await self._send_full_analysis(raw_analysis, len(alerts))
                elif alerts_to_send:
                    # Send filtered summary
                    await self._send_smart_summary(alerts_to_send)
                else:
                    print(f"\n✅ No alerts met sending criteria - keeping channel clean")

            # Don't check interactions here - they're checked on a separate faster schedule
            # in monitor_continuously()

            return []  # Return empty for compatibility

    def _normalize_alert_timestamp(self, raw_timestamp: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Normalize timestamps coming back from Claude into ISO strings and Slack ts values."""
        if not raw_timestamp:
            return None, None

        value = str(raw_timestamp).strip().strip('"').strip()
        if not value or value.lower() in {"n/a", "none", "unknown"}:
            return None, None

        # First try Slack ts floating-point format (e.g. 1728300952.000200)
        try:
            slack_ts_float = float(value)
            if slack_ts_float > 1_000_000_000:  # Rough sanity check (seconds since epoch)
                dt = datetime.fromtimestamp(slack_ts_float, tz=timezone.utc)
                slack_ts = f"{slack_ts_float:.6f}".rstrip("0").rstrip(".")
                return dt.isoformat(), slack_ts
        except ValueError:
            pass

        sanitized = value.replace("Z", "+00:00")
        if sanitized.upper().endswith(" UTC"):
            sanitized = sanitized[:-4].strip() + "+00:00"

        timestamp_dt: Optional[datetime] = None

        try:
            timestamp_dt = datetime.fromisoformat(sanitized)
        except ValueError:
            pass

        if timestamp_dt is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
                try:
                    timestamp_dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue

        if timestamp_dt is None:
            return None, None

        if timestamp_dt.tzinfo is None:
            timestamp_dt = timestamp_dt.replace(tzinfo=self._local_timezone)

        return timestamp_dt.astimezone(timezone.utc).isoformat(), None

    @staticmethod
    def _timestamp_to_datetime(timestamp_str: Optional[str]) -> Optional[datetime]:
        """Convert stored ISO timestamp into aware datetime."""
        if not timestamp_str:
            return None
        try:
            dt = datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    def _message_already_processed(self, message_id: str) -> bool:
        """Check if we've already processed this Slack message."""
        if not message_id:
            return False

        if message_id in self.seen_messages:
            return True

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM alerts WHERE message_id = ? LIMIT 1",
            (message_id,)
        )
        exists = cursor.fetchone() is not None
        conn.close()

        if exists:
            self.seen_messages.add(message_id)
            if len(self.seen_messages) > 2000:
                self.seen_messages.pop()

        return exists

    @staticmethod
    def _parse_db_timestamp(value: Optional[str]) -> Optional[datetime]:
        """Convert timestamps stored in SQLite (UTC) into aware datetimes."""
        if not value:
            return None

        candidate = value.strip()
        if not candidate:
            return None

        # Try ISO format first
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError:
            dt = None

        if dt is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    dt = datetime.strptime(candidate, fmt)
                    break
                except ValueError:
                    continue

        if dt is None:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    def _format_local_time(self, dt: Optional[datetime], include_date: bool = True) -> Optional[str]:
        """Format datetime in local timezone."""
        if not dt:
            return None

        fmt = "%d/%m %H:%M" if include_date else "%H:%M"
        return dt.astimezone(self._local_timezone).strftime(fmt)

    @staticmethod
    def _humanize_timedelta(delta: timedelta) -> str:
        """Turn timedelta into a compact human readable string."""
        total_seconds = int(abs(delta.total_seconds()))
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60

        parts: List[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")

        return " ".join(parts)

    def _collect_alert_history(
        self,
        pattern_signature: str,
        limit: int = 5,
        window_hours: int = 48,
    ) -> List[Dict[str, Any]]:
        """Fetch recent alert history for the given pattern."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT text, importance, reason, created_at, sent_to_slack
            FROM alerts
            WHERE pattern_signature = ?
              AND created_at > datetime('now', '-' || ? || ' hours')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (pattern_signature, window_hours, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        now_utc = datetime.now(timezone.utc)
        entries: List[Dict[str, Any]] = []

        for row in rows:
            created_raw = row["created_at"]
            created_dt = self._parse_db_timestamp(created_raw)
            local_full = self._format_local_time(created_dt)
            local_short = self._format_local_time(created_dt, include_date=False)
            age = self._humanize_timedelta(now_utc - created_dt) if created_dt else "?"

            entries.append(
                {
                    "text": row["text"],
                    "importance": row["importance"],
                    "reason": row["reason"],
                    "created_at": created_raw,
                    "created_dt": created_dt,
                    "local_time": local_full,
                    "local_time_short": local_short,
                    "age": age,
                    "sent_to_slack": bool(row["sent_to_slack"]),
                }
            )

        return entries

    def _format_channel_label(self, identifier: str) -> str:
        if not identifier:
            return identifier
        alias = self._channel_aliases.get(identifier)
        if not alias and isinstance(identifier, str):
            alias = self._channel_aliases.get(identifier.lstrip('#'))
        if alias:
            return f"{alias} ({identifier})" if identifier.startswith('C') else alias
        return identifier

    def _format_channel_for_summary(self, channel: str) -> str:
        if not channel:
            return channel
        alias = self._channel_aliases.get(channel)
        if not alias and isinstance(channel, str):
            alias = self._channel_aliases.get(channel.lstrip('#'))
        label = alias or channel
        if not label.startswith('#'):
            label = f"#{label}"
        return label


    def _normalize_label_key(self, label: str) -> str:
        """Normalize keys returned by Claude to compare irrespective of accents."""
        decomposed = unicodedata.normalize("NFKD", label)
        no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
        return no_accents.upper().strip()

    def _parse_insight_response(self, response: str) -> Dict[str, str]:
        """
        Parse structured response from Claude produced by _generate_alert_insights.
        Returns lowercase keys: impact, cause, action, confidence
        """
        if not response.strip():
            return {}

        mapping = {
            "IMPACTO": "impact",
            "IMPACT": "impact",
            "CAUSA": "cause",
            "CAUSE": "cause",
            "ACAO": "action",
            "ACCION": "action",
            "ACCIÓN": "action",
            "ACTION": "action",
            "CONFIANCA": "confidence",
            "CONFIDENCE": "confidence",
        }

        insights: Dict[str, str] = {}
        current_key: Optional[str] = None

        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if ":" in line:
                label, value = line.split(":", 1)
                normalized = self._normalize_label_key(label)
                mapped_key = mapping.get(normalized)

                if mapped_key:
                    insights[mapped_key] = value.strip()
                    current_key = mapped_key
                else:
                    current_key = None
            elif current_key:
                # Continuation of previous value
                insights[current_key] = f"{insights[current_key]} {line}".strip()

        return insights

    async def _generate_alert_insights(
        self,
        alert: Alert,
        pattern_info: Dict[str, Any],
        history_entries: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Ask Claude for a concise operational insight about the alert."""
        if not self.client:
            return {}

        first_seen_dt = alert.first_seen_dt
        last_seen_dt = alert.last_seen_dt or self._timestamp_to_datetime(alert.timestamp)
        now_dt = datetime.now(timezone.utc)
        now_local = self._format_local_time(now_dt) or now_dt.astimezone(self._local_timezone).strftime("%d/%m %H:%M")

        history_lines: List[str] = []
        for entry in history_entries[:5]:
            snippet = (entry["text"] or "").strip().replace("\n", " ")
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."
            decision = "enviado" if entry["sent_to_slack"] else "filtrado"
            line = (
                f"- {entry['local_time'] or entry['created_at']} "
                f"({entry['age']} atrás, {decision}) — {entry['importance']} — {snippet}"
            )
            history_lines.append(line)

        if not history_lines:
            history_lines.append("- (Sem histórico adicional além deste evento.)")

        first_seen_text = "indefinido"
        if first_seen_dt:
            first_seen_text = (
                f"{self._format_local_time(first_seen_dt)} "
                f"({self._humanize_timedelta(now_dt - first_seen_dt)} atrás)"
            )

        last_seen_text = "indefinido"
        if last_seen_dt:
            last_seen_text = (
                f"{self._format_local_time(last_seen_dt)} "
                f"({self._humanize_timedelta(now_dt - last_seen_dt)} atrás)"
            )

        prompt = f"""
Você é um analista SRE acompanhando alertas recorrentes vindos do Slack.

Alerta atual:
- Canal: #{alert.channel}
- Importância classificada: {alert.importance}
- Texto: {alert.text.strip()}
- Razão original: {alert.reason or 'não informado'}
- Timestamp: {alert.timestamp}
- Decisão de envio: {alert.escalation_reason or 'não informado'}

Estatísticas do padrão:
- Ocorrências rastreadas: {alert.occurrence_count}
- Detectado inicialmente em: {first_seen_text}
- Último evento registrado: {last_seen_text}
- Horário atual: {now_local}

Histórico recente (mais novos primeiro):
{chr(10).join(history_lines)}

Instruções:
1. Resuma o impacto observado ou provável em 1 frase curta.
2. Cite a causa provável ou informe que é desconhecida.
3. Recomende a próxima ação objetiva (reiniciar serviço, acionar time, monitorar, etc).
4. Informe o nível de confiança (BAIXA, MÉDIA ou ALTA) com justificativa breve.

Responda STRICTAMENTE em quatro linhas neste formato:
IMPACTO: ...
CAUSA: ...
AÇÃO: ...
CONFIANÇA: ...
"""

        await self._log_prompt("insight_generation", prompt)
        await self.client.query(prompt)
        response, _ = await self._collect_response_text(timeout=self.response_timeout)
        insights = self._parse_insight_response(response)

        return insights

    async def _enrich_alert(self, alert: Alert, pattern_info: Dict[str, Any]):
        """Populate alert with historical context and LLM insight."""
        alert.first_seen = pattern_info.get("first_seen")
        alert.last_seen = pattern_info.get("last_seen")
        alert.occurrence_count = pattern_info.get("occurrence_count", 1)
        alert.first_seen_dt = self._parse_db_timestamp(alert.first_seen)
        alert.last_seen_dt = self._parse_db_timestamp(alert.last_seen) or self._timestamp_to_datetime(alert.timestamp)

        history_entries = self._collect_alert_history(
            alert.pattern_signature,
            limit=5,
            window_hours=max(self.duplicate_window_hours, 48),
        )
        alert.history_entries = history_entries

        if history_entries:
            formatted_history = []
            for entry in history_entries[:5]:
                snippet = (entry["text"] or "").strip().replace("\n", " ")
                if len(snippet) > 160:
                    snippet = snippet[:160] + "..."
                formatted_history.append(
                    f"{entry['local_time'] or entry['created_at']} ({entry['age']} atrás) — {entry['importance']} — {snippet}"
                )
            alert.history_context = "\n".join(formatted_history)
        else:
            alert.history_context = "Sem histórico adicional."

        try:
            insights = await self._generate_alert_insights(alert, pattern_info, history_entries)
            alert.insights = insights or None
        except Exception as error:
            print(f"⚠️  Falha ao gerar análise inteligente para {alert.pattern_signature}: {error}")
            alert.insights = None

    def _parse_analysis(self, raw_text: str) -> List[Alert]:
        """Parse Claude's analysis into Alert objects"""
        alerts = []

        # Split by message markers
        messages = raw_text.split("---MESSAGE---")

        for msg_text in messages:
            if "---END MESSAGE---" not in msg_text:
                continue

            # Extract fields
            lines = msg_text.strip().split("\n")
            alert_data = {}

            for line in lines:
                line = line.strip()
                if ":" in line and not line.startswith("---"):
                    key, value = line.split(":", 1)
                    alert_data[key.strip().lower()] = value.strip()

            # Create alert if we have minimum required fields
            if "channel" in alert_data and "text" in alert_data:
                normalized_timestamp, slack_ts = self._normalize_alert_timestamp(
                    alert_data.get("timestamp") or alert_data.get("ts")
                )

                if not normalized_timestamp:
                    print(f"⏭️  Skipping message without usable timestamp: {alert_data.get('text', '')[:60]}")
                    continue

                dedupe_key = slack_ts if slack_ts else normalized_timestamp
                channel_name = alert_data.get("channel", "unknown")

                message_id = hashlib.md5(
                    f"{channel_name.lower()}::{dedupe_key}".encode()
                ).hexdigest()

                alert = Alert(
                    message_id=message_id,
                    channel=channel_name,
                    user=alert_data.get("user", "unknown"),
                    text=alert_data.get("text", ""),
                    timestamp=normalized_timestamp,
                    importance=alert_data.get("importance", "NORMAL").upper(),
                    reason=alert_data.get("reason", ""),
                    content_hash="",
                    pattern_signature="",
                    slack_ts=slack_ts
                )
                alerts.append(alert)

        return alerts

    async def _send_full_analysis(self, raw_analysis: str, alert_count: int):
        """Send Claude's complete raw analysis to Slack"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Format the full analysis for Slack
        message = f"""📊 *Complete Alert Analysis - {timestamp}*

{raw_analysis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *Analysis Summary:* Found {alert_count} message(s)
_Full report mode - showing Claude's complete analysis_"""

        print(f"\n📤 Sending FULL analysis to #{self.summary_channel}")
        print("=" * 70)

        try:
            method = "webhook" if self.slack_webhook_url else "MCP"
            success = await self._send_to_slack(message)

            if success:
                print(f"✅ Full analysis sent to #{self.summary_channel} via {method}")
            else:
                print(f"❌ Failed to send full analysis to #{self.summary_channel}")
        except Exception as e:
            print(f"❌ Error sending full analysis: {e}")

    async def _send_smart_summary(self, alerts: List[Alert]):
        """Send a smart summary of only the important alerts"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Group by importance
        critical = [a for a in alerts if a.importance == "CRITICAL"]
        important = [a for a in alerts if a.importance == "IMPORTANT"]

        def _format_alert_entry(idx: int, alert: Alert) -> List[str]:
            msg_text = (alert.text or "").strip() or "[sem texto]"
            msg_text = " ".join(msg_text.split())
            if len(msg_text) > 90:
                msg_text = msg_text[:90] + "..."

            channel_label = self._format_channel_for_summary(alert.channel)
            header = f"{idx}. {channel_label} - {msg_text}"

            details: List[str] = []

            first_seen_fmt = self._format_local_time(alert.first_seen_dt) if alert.first_seen_dt else None
            occurrence_info = f"{alert.occurrence_count}"
            if alert.occurrence_count > 1 and first_seen_fmt:
                occurrence_info = f"{alert.occurrence_count} desde {first_seen_fmt}"
            elif first_seen_fmt:
                occurrence_info = f"1 às {first_seen_fmt}"

            last_entry = alert.history_entries[0] if alert.history_entries else None
            last_info = None
            if last_entry:
                last_time = last_entry.get("local_time_short") or last_entry.get("local_time")
                last_age = last_entry.get("age")
                if last_time and last_age:
                    last_info = f"{last_time} ({last_age} atrás)"

            meta_parts = [f"Ocorrências: {occurrence_info}"]
            if last_info:
                meta_parts.append(f"Último: {last_info}")
            if alert.escalation_reason and (alert.reason or "").strip() != alert.escalation_reason.strip():
                meta_parts.append(f"Critério: {alert.escalation_reason}")

            details.append(" | ".join(meta_parts))

            if alert.insights:
                impact = alert.insights.get("impact")
                cause = alert.insights.get("cause")
                action = alert.insights.get("action")
                confidence = alert.insights.get("confidence")

                if impact or cause:
                    impact_text = impact or "sem impacto declarado"
                    cause_text = cause or "causa não identificada"
                    details.append(f"Impacto: {impact_text} | Causa: {cause_text}")
                if action:
                    action_line = f"Ação: {action}"
                    if confidence:
                        action_line += f" (Confiança: {confidence})"
                    details.append(action_line)
                elif confidence:
                    details.append(f"Confiança: {confidence}")
            else:
                if alert.reason:
                    details.append(f"Motivo Claude: {alert.reason}")
                if alert.escalation_reason and alert.escalation_reason != alert.reason:
                    details.append(f"Critério de envio: {alert.escalation_reason}")

            if alert.occurrence_count > 1 and len(alert.history_entries) > 1:
                samples: List[str] = []
                for entry in alert.history_entries[1:3]:
                    sample_time = entry.get("local_time_short") or entry.get("local_time")
                    age = entry.get("age")
                    if sample_time and age:
                        samples.append(f"{sample_time} ({age})")
                if samples:
                    details.append(f"Recorrências recentes: {', '.join(samples)}")

            lines = [header]
            if details:
                lines.extend(f"   • {detail}" for detail in details)

            return lines

        summary_lines: List[str] = [f"🔔 *Alertas - {timestamp}*"]

        if critical:
            summary_lines.append("")
            label = "CRÍTICO" if len(critical) == 1 else "CRÍTICOS"
            summary_lines.append(f"🚨 *{len(critical)} {label}:*")
            for idx, alert in enumerate(critical, 1):
                summary_lines.extend(_format_alert_entry(idx, alert))

        if important:
            summary_lines.append("")
            label = "IMPORTANTE" if len(important) == 1 else "IMPORTANTES"
            summary_lines.append(f"⚠️ *{len(important)} {label}:*")
            for idx, alert in enumerate(important, 1):
                summary_lines.extend(_format_alert_entry(idx, alert))

        summary_lines.append("")
        summary_lines.append("_Monitor inteligente - somente alertas urgentes/recorrentes_")

        summary = "\n".join(summary_lines)

        # Debug: Show what we're sending
        print(f"\n📤 Sending summary to #{self.summary_channel}:")
        print("─" * 60)
        print(summary)
        print("─" * 60)

        # Send to Slack
        try:
            method = "webhook" if self.slack_webhook_url else "MCP"
            success = await self._send_to_slack(summary)

            if success:
                print(f"\n✅ Sent {len(alerts)} filtered alert(s) to #{self.summary_channel} via {method}")
            else:
                print(f"\n❌ Failed to send to #{self.summary_channel} via {method}")
        except Exception as e:
            print(f"❌ Failed to send summary: {e}")


    def _split_message_smart(self, message: str, max_length: int = 1500) -> List[str]:
        """Split message into chunks at natural breakpoints (newlines)."""
        if len(message) <= max_length:
            return [message]

        chunks = []
        lines = message.split('\n')
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            if current_length + line_length > max_length:
                # Save current chunk
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # If single line is too long, split it
                if line_length > max_length:
                    for i in range(0, len(line), max_length - 3):
                        chunks.append(line[i:i+max_length-3] + "...")
                else:
                    current_chunk = [line]
                    current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    async def _send_whatsapp_digest(self, message: str):
        """Send digest message via WhatsApp using Twilio API (split if needed)."""
        whatsapp_cfg = self._summary_schedule.get("whatsapp", {})
        if not whatsapp_cfg.get("enabled"):
            return

        service_file = whatsapp_cfg.get("service_file")
        account_sid = whatsapp_cfg.get("account_sid")
        from_number = whatsapp_cfg.get("from_number")
        to_number = whatsapp_cfg.get("to_number")
        auth_token = whatsapp_cfg.get("auth_token")
        auth_token_env = whatsapp_cfg.get("auth_token_env", "TWILIO_AUTH_TOKEN")
        use_template = whatsapp_cfg.get("use_template", False)
        content_sid = whatsapp_cfg.get("content_sid")

        if service_file and os.path.exists(service_file):
            parsed = self._parse_whatsapp_service_file(service_file)
            account_sid = account_sid or parsed.get("account_sid")
            from_number = from_number or parsed.get("from")
            to_number = to_number or parsed.get("to")
            content_sid = content_sid or parsed.get("content_sid")
            auth_token = auth_token or parsed.get("auth_token")

        if not account_sid or not from_number or not to_number:
            print("⚠️  Configuração WhatsApp incompleta; resumo não enviado por WhatsApp.")
            return

        if not auth_token:
            auth_token = os.getenv(auth_token_env)

        if not auth_token:
            print("⚠️  Token de autenticação Twilio não encontrado; defina a variável de ambiente correspondente.")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        # Split message into chunks if needed (max 1500 chars per message)
        chunks = self._split_message_smart(message, max_length=1500)

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                sent_count = 0
                for i, chunk in enumerate(chunks):
                    # Add part indicator if multiple chunks
                    if len(chunks) > 1:
                        chunk_message = f"[{i+1}/{len(chunks)}]\n{chunk}"
                    else:
                        chunk_message = chunk

                    payload: Dict[str, Any]
                    if use_template and content_sid:
                        payload = {
                            "To": to_number,
                            "From": from_number,
                            "ContentSid": content_sid,
                            "ContentVariables": json.dumps({"1": chunk_message}),
                        }
                    else:
                        payload = {
                            "To": to_number,
                            "From": from_number,
                            "Body": chunk_message,
                        }

                    response = await client.post(url, data=payload, auth=(account_sid, auth_token))

                    if response.status_code in (200, 201):
                        sent_count += 1
                    else:
                        print(f"⚠️  Falha ao enviar parte {i+1}/{len(chunks)}: {response.status_code} - {response.text[:200]}")
                        break

                    # Small delay between messages to avoid rate limiting
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)

                if sent_count == len(chunks):
                    if len(chunks) > 1:
                        print(f"📨 Resumo enviado via WhatsApp ({len(chunks)} mensagens, {len(message)} chars total)")
                    else:
                        print(f"📨 Resumo enviado via WhatsApp ({len(message)} chars)")
                else:
                    print(f"⚠️  Enviadas apenas {sent_count}/{len(chunks)} mensagens")

        except Exception as error:
            print(f"⚠️  Erro ao enviar WhatsApp: {error}")

    @staticmethod
    def _parse_whatsapp_service_file(path: str) -> Dict[str, Optional[str]]:
        """Parse helper script (curl) to extract Twilio parameters."""
        result = {"account_sid": None, "from": None, "to": None, "content_sid": None}

        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
        except OSError:
            return result

        account_match = re.search(r"Accounts/([A-Za-z0-9]+)/Messages", content)
        if account_match:
            result["account_sid"] = account_match.group(1)

        to_match = re.search(r"--data-urlencode 'To=([^']+)'", content)
        if to_match:
            to_value = to_match.group(1).strip()
            result["to"] = to_value if to_value.startswith("whatsapp:") else f"whatsapp:{to_value}"

        from_match = re.search(r"--data-urlencode 'From=([^']+)'", content)
        if from_match:
            from_value = from_match.group(1).strip()
            result["from"] = from_value if from_value.startswith("whatsapp:") else f"whatsapp:{from_value}"

        content_sid_match = re.search(r"--data-urlencode 'ContentSid=([^']+)'", content)
        if content_sid_match:
            result["content_sid"] = content_sid_match.group(1).strip()

        credential_match = re.search(r"-u\s+([A-Za-z0-9]+):([^\\s]+)", content)
        if credential_match:
            result["account_sid"] = credential_match.group(1)
            token = credential_match.group(2)
            if token and not token.startswith("["):
                result["auth_token"] = token

        return result
    async def _summary_loop(self):
        """Background loop that posts periodic digests."""
        if not self.summary_channel:
            print("⚠️  Digest mode habilitado, mas summary_channel não está configurado.")
            return

        schedule = self._summary_schedule
        interval = schedule["interval_seconds"]
        first_cycle = True

        while True:
            delay = 0 if first_cycle and schedule.get("send_initial") else interval
            first_cycle = False

            if delay > 0:
                await asyncio.sleep(delay)

            try:
                now_local = datetime.now(self._local_timezone)
                if not self._active_hours or self._is_within_active_hours(now_local.time()):
                    await self._send_digest_summary(now_local)
                    schedule["send_initial"] = False
                else:
                    next_start = self._get_next_active_start(now_local)
                    if next_start:
                        wait_seconds = max(60, (next_start - now_local).total_seconds())
                        print(f"⏸️  Resumo periódico aguardando próxima janela ativa ({self._active_hours_label}) em {wait_seconds/60:.1f} min")
                        await asyncio.sleep(wait_seconds)
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(f"⚠️  Erro no resumo periódico: {error}")

    async def _send_digest_summary(self, reference_time: Optional[datetime] = None):
        """Send a digest of alerts observed within the configured lookback window."""
        if not self.summary_channel:
            return

        schedule = self._summary_schedule
        if not schedule.get("enabled"):
            return

        lookback_minutes = schedule["lookback_minutes"]
        max_alerts = schedule["max_alerts"]
        include_filtered = schedule["include_filtered"]
        lookback_clause = f"-{lookback_minutes} minutes"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT channel, text, importance, reason, created_at, sent_to_slack
            FROM alerts
            WHERE created_at >= datetime('now', ?)
            ORDER BY created_at DESC
            """,
            (lookback_clause,)
        )

        rows = cursor.fetchall()
        conn.close()

        now_local = reference_time or datetime.now(self._local_timezone)
        header_time = now_local.strftime('%d/%m %H:%M')

        total_alerts = len(rows)
        sent_count = sum(1 for row in rows if row[5])
        filtered_count = total_alerts - sent_count
        critical_count = sum(1 for row in rows if row[2] == "CRITICAL")
        important_count = sum(1 for row in rows if row[2] == "IMPORTANT")

        message_lines: List[str] = [
            f"🕒 *Resumo automático - {header_time}*",
            f"Período analisado: últimas {lookback_minutes} minutos",
            f"Total de alertas processados: {total_alerts} (enviados: {sent_count} | filtrados: {filtered_count})",
        ]

        if critical_count or important_count:
            counts = []
            if critical_count:
                counts.append(f"🚨 {critical_count} crítico(s)")
            if important_count:
                counts.append(f"⚠️ {important_count} importante(s)")
            message_lines.append("Classificação: " + ", ".join(counts))
        else:
            message_lines.append("Classificação: Nenhum alerta CRÍTICO/IMPORTANTE no período.")

        if total_alerts == 0:
            message_lines.append("\n✅ Nenhum novo alerta registrado no período.")
        else:
            message_lines.append("\n📌 Destaques recentes:")
            listed = 0
            for channel, text, importance, reason, created_at, sent_to_slack in rows:
                if listed >= max_alerts:
                    break
                if not include_filtered and not sent_to_slack:
                    continue

                created_dt = self._parse_db_timestamp(created_at)
                time_str = self._format_local_time(created_dt, include_date=False) or created_at
                clean_text = " ".join((text or "").split())
                if len(clean_text) > 90:
                    clean_text = clean_text[:90] + "..."

                status = "enviado" if sent_to_slack else "filtrado"
                status_icon = "✅" if sent_to_slack else "⏳"
                channel_display = self._format_channel_for_summary(channel)
                message_lines.append(f"{status_icon} {time_str} · {channel_display} · [{importance}] · {clean_text} ({status})")
                if reason:
                    message_lines.append(f"   • Motivo Claude: {reason}")
                listed += 1

            if listed == 0:
                message_lines.append("Nenhum alerta enviado no período.")

        message_lines.append("\n_Modo resumo periódico ativo_")

        digest_message = "\n".join(message_lines)

        try:
            if await self._send_to_slack(digest_message):
                print(f"📨 Resumo automático enviado ({lookback_minutes}min, {total_alerts} alertas)")
            else:
                print("❌ Falha ao enviar resumo automático")
            await self._send_whatsapp_digest(digest_message)
        except Exception as error:
            print(f"❌ Erro ao enviar resumo automático: {error}")

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics about alerts and filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sent_to_slack = 1 THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN importance = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN importance = 'IMPORTANT' THEN 1 ELSE 0 END) as important
            FROM alerts
            WHERE created_at > datetime('now', '-' || ? || ' hours')
        """, (hours,))

        total, sent, critical, important = cursor.fetchone()

        # Pattern stats
        cursor.execute("""
            SELECT COUNT(*) FROM patterns
            WHERE last_seen > datetime('now', '-' || ? || ' hours')
        """, (hours,))

        active_patterns = cursor.fetchone()[0]

        # Top patterns
        cursor.execute("""
            SELECT pattern_signature, occurrence_count
            FROM patterns
            ORDER BY occurrence_count DESC
            LIMIT 5
        """)

        top_patterns = cursor.fetchall()

        conn.close()

        # Calculate filtering effectiveness
        filter_rate = ((total - sent) / total * 100) if total > 0 else 0

        return {
            "hours": hours,
            "total_alerts": total or 0,
            "sent_to_slack": sent or 0,
            "filtered_out": (total - sent) if total else 0,
            "filter_rate_percent": round(filter_rate, 1),
            "critical_count": critical or 0,
            "important_count": important or 0,
            "active_patterns": active_patterns or 0,
            "top_patterns": [{"pattern": p, "count": c} for p, c in top_patterns]
        }

    async def _send_to_slack(self, message: str) -> bool:
        """Send message to Slack via webhook or MCP"""

        # Option 1: Use webhook (more reliable, no channel lookup needed)
        if self.slack_webhook_url:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.slack_webhook_url,
                        json={"text": message},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return True
                    else:
                        print(f"❌ Webhook failed: {response.status_code} - {response.text}")
                        return False
            except Exception as e:
                print(f"❌ Webhook error: {e}")
                return False

        # Option 2: Use MCP (requires channel lookup)
        if not self.client or not self.summary_channel:
            return False

        # Escape for safer transmission
        safe_message = message.replace('"', "'").replace('`', "'")

        channel_ref = self._get_summary_channel_reference()
        if not channel_ref:
            return False

        query = f"""Use the mcp__slack__conversations_add_message tool with these parameters:

channel: "{channel_ref}"
text: The complete alert message below

IMPORTANT: Send the COMPLETE message including ALL lines. Do not truncate or summarize.

Message (send exactly as shown):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{safe_message}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        try:
            await self._log_prompt("mcp_add_message", query)
            await self.client.query(query)

            response, _ = await self._collect_response_text(timeout=self.response_timeout)

            if not response.strip():
                print("   MCP response was empty or timed out")
                return False

            # Verify if it actually worked
            response_lower = response.lower()
            if "error" in response_lower or "failed" in response_lower or "not found" in response_lower:
                print(f"   MCP error: {response[:300]}")
                return False
            else:
                # Try to extract channel ID from response for caching
                if not self._summary_channel_id and "channel" in response_lower:
                    # Look for channel ID pattern (C followed by alphanumerics)
                    import re
                    match = re.search(r'C[A-Z0-9]{10,}', response)
                    if match:
                        self._summary_channel_id = match.group(0)
                        print(f"   📌 Cached channel ID: {self._summary_channel_id}")
                return True
        except Exception as e:
            print(f"   MCP exception: {e}")
            return False

    async def _send_startup_notification(self):
        """Send notification that the monitor has started"""
        # Check if startup notification is enabled
        if not getattr(self, 'send_startup_notification', True):
            return

        if not self.summary_channel:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get recent alerts summary
        summary_hours = getattr(self, 'startup_summary_hours', 1)
        recent_summary = self._get_recent_alerts_summary(summary_hours)

        message = f"""🤖 *Smart Slack Monitor Started*

📅 Started at: {timestamp}
⏱️  Check interval: {self.check_interval}s
🎯 Min urgency: {self.min_urgency_level}
🔄 Dedup window: {self.duplicate_window_hours}h
📊 Recurrence threshold: {self.recurrence_threshold}x

{recent_summary}

_Monitor is now active and filtering alerts intelligently..._"""

        try:
            method = "webhook" if self.slack_webhook_url else "MCP"
            print(f"Sending startup notification via {method}...")

            success = await self._send_to_slack(message)

            if success:
                print(f"✅ Startup notification sent to #{self.summary_channel} via {method}")
            else:
                print(f"❌ Startup notification FAILED to #{self.summary_channel} via {method}")
        except Exception as e:
            print(f"❌ Could not send startup notification: {e}")

    def _get_recent_alerts_summary(self, hours: int) -> str:
        """Build a richer snapshot for the startup notification."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT channel, text, importance, created_at, reason, pattern_signature
                FROM alerts
                WHERE created_at > datetime('now', '-' || ? || ' hours')
                ORDER BY created_at DESC
                """,
                (hours,),
            )

            alerts = cursor.fetchall()

            if not alerts:
                conn.close()
                return f"📭 *Resumo das últimas {hours}h:* Nenhum alerta registrado"

            critical = sum(1 for a in alerts if a[2] == "CRITICAL")
            important = sum(1 for a in alerts if a[2] == "IMPORTANT")

            summary_lines: List[str] = [f"📊 *Resumo das últimas {hours}h:*"]
            if critical > 0:
                summary_lines.append(f"   🚨 {critical} CRÍTICO(S)")
            if important > 0:
                summary_lines.append(f"   ⚠️ {important} IMPORTANTE(S)")

            important_alerts = [a for a in alerts if a[2] in {"CRITICAL", "IMPORTANT"}][:3]

            pattern_signatures = [row[5] for row in important_alerts if row[5]]
            pattern_metadata: Dict[str, Dict[str, Any]] = {}

            if pattern_signatures:
                placeholders = ",".join("?" for _ in pattern_signatures)
                cursor.execute(
                    f"""
                    SELECT pattern_signature, first_seen, last_seen, occurrence_count, last_sent
                    FROM patterns
                    WHERE pattern_signature IN ({placeholders})
                    """,
                    pattern_signatures,
                )

                for pattern_signature, first_seen, last_seen, occurrence_count, last_sent in cursor.fetchall():
                    pattern_metadata[pattern_signature] = {
                        "first_seen": self._parse_db_timestamp(first_seen),
                        "last_seen": self._parse_db_timestamp(last_seen),
                        "occurrence_count": occurrence_count,
                        "last_sent": self._parse_db_timestamp(last_sent),
                    }

            conn.close()

            if important_alerts:
                summary_lines.append("")
                summary_lines.append("*Últimos alertas importantes:*")

                for channel, text, importance, created_at, reason, pattern_signature in important_alerts:
                    created_dt = self._parse_db_timestamp(created_at)
                    time_str = self._format_local_time(created_dt) or created_at
                    icon = "🚨" if importance == "CRITICAL" else "⚠️"
                    clean_text = " ".join((text or "").split())
                    if len(clean_text) > 80:
                        clean_text = clean_text[:80] + "..."
                    summary_lines.append(f"{icon} {time_str} - #{channel}: {clean_text}")

                    detail_lines: List[str] = []
                    pattern_info = pattern_metadata.get(pattern_signature)

                    if pattern_info:
                        occ = pattern_info.get("occurrence_count") or 1
                        first_seen_dt = pattern_info.get("first_seen")
                        occ_text = f"{occ}"
                        if first_seen_dt:
                            first_seen_local = self._format_local_time(first_seen_dt)
                            if first_seen_local:
                                occ_text += f" desde {first_seen_local}"
                        detail_lines.append(f"Ocorrências rastreadas: {occ_text}")

                        last_seen_dt = pattern_info.get("last_seen")
                        if last_seen_dt and created_dt and created_dt >= last_seen_dt:
                            age = self._humanize_timedelta(created_dt - last_seen_dt)
                            if age and age != "0m":
                                detail_lines.append(f"Última variação registrada há {age}")

                    if reason:
                        detail_lines.append(f"Motivo Claude: {reason}")

                    if pattern_signature:
                        history_entries = self._collect_alert_history(
                            pattern_signature,
                            limit=3,
                            window_hours=max(self.duplicate_window_hours, 24),
                        )
                        if history_entries:
                            samples: List[str] = []
                            for entry in history_entries[:2]:
                                time_label = entry.get("local_time_short") or entry.get("local_time")
                                age = entry.get("age")
                                if time_label and age:
                                    samples.append(f"{time_label} ({age})")
                            if samples:
                                detail_lines.append(f"Ocorrências recentes: {', '.join(samples)}")

                    summary_lines.extend(f"   • {line}" for line in detail_lines)

            return "\n".join(summary_lines)

        except Exception as error:
            return f"⚠️ Não foi possível carregar resumo: {error}"

    async def _interaction_loop(self):
        """Separate loop for checking interactions at faster interval"""
        try:
            while True:
                try:
                    if getattr(self, 'interactive_mode', False):
                        await self._check_for_interactions()
                    await asyncio.sleep(self.interaction_check_interval)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error in interaction loop: {e}")
                    await asyncio.sleep(self.interaction_check_interval)
        except asyncio.CancelledError:
            # Loop cancelled, exit gracefully
            pass

    async def monitor_continuously(self):
        """Override to add startup notification and separate interaction checking"""
        digest_only_mode = self._summary_schedule.get("digest_only_mode", False)

        print(f"🔍 Starting Smart Slack Monitor...")
        if digest_only_mode:
            print(f"   Mode: DIGEST ONLY (continuous checking disabled)")
        else:
            print(f"   Checking alerts every {self.check_interval} seconds")
        if getattr(self, 'interactive_mode', False):
            print(f"   Checking interactions every {self.interaction_check_interval} seconds")
        print(f"   Keywords: {', '.join(self.keywords)}")
        if self.channels_to_monitor:
            display_channels = ", ".join(self._format_channel_label(ch) for ch in self.channels_to_monitor)
            print(f"   Channels: {display_channels}")
        else:
            print(f"   Monitoring: All channels with keywords")
        if self.summary_channel:
            print(f"   📤 Sending filtered alerts to: #{self.summary_channel}")
        if self._active_hours_label:
            print(f"   Active hours: {self._active_hours_label} (horário local)")
        else:
            print(f"   Active hours: 24h (monitoramento contínuo)")
        if self._summary_schedule.get("enabled"):
            print(f"   Resumo periódico: {self._summary_schedule_label}")
        else:
            print(f"   Resumo periódico: desabilitado")
        print()

        await self.connect()

        # Send startup notification
        await self._send_startup_notification()

        # Start interaction loop as a separate task (if enabled)
        interaction_task = None
        if getattr(self, 'interactive_mode', False):
            interaction_task = asyncio.create_task(self._interaction_loop())

        summary_task = None
        if self._summary_schedule.get("enabled"):
            if self.summary_channel:
                summary_task = asyncio.create_task(self._summary_loop())
            else:
                print("⚠️  Resumo periódico habilitado, mas summary_channel não está definido; recurso ignorado.")

        try:
            if digest_only_mode:
                # Digest-only mode: Just wait for summary loop, no continuous checking
                print("⏸️  Continuous alert checking disabled (digest_only_mode=true)")
                print("   Monitor will only send periodic digests\n")

                if not summary_task:
                    print("⚠️  WARNING: digest_only_mode enabled but periodic summary is not enabled!")
                    print("   Enable smart_summary.enabled in config.yaml to receive digests.\n")

                # Keep process alive and wait for summary loop
                while True:
                    await asyncio.sleep(60)  # Check every minute to keep process responsive
            else:
                # Normal mode: Continuous alert checking
                while True:
                    try:
                        await self.check_messages()
                        await asyncio.sleep(self.check_interval)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        print(f"❌ Error checking messages: {e}")
                        await asyncio.sleep(self.check_interval)
        finally:
            # Cancel interaction task if running
            if interaction_task:
                interaction_task.cancel()
                try:
                    await interaction_task
                except asyncio.CancelledError:
                    pass
            if summary_task:
                summary_task.cancel()
                try:
                    await summary_task
                except asyncio.CancelledError:
                    pass
            await self.disconnect()


async def main():
    """Example usage of Smart Slack Monitor"""
    import os

    # Try to load config
    try:
        from config import (
            MONITORED_CHANNELS,
            IMPORTANCE_KEYWORDS,
            CHECK_INTERVAL,
            SUMMARY_CHANNEL
        )
    except ImportError:
        print("Using default configuration")
        MONITORED_CHANNELS = []
        IMPORTANCE_KEYWORDS = ["urgent", "critical", "error", "down"]
        CHECK_INTERVAL = 300
        SUMMARY_CHANNEL = None

    # Create smart monitor
    monitor = SmartSlackMonitor(
        channels_to_monitor=MONITORED_CHANNELS,
        keywords=IMPORTANCE_KEYWORDS,
        check_interval=CHECK_INTERVAL,
        summary_channel=SUMMARY_CHANNEL,
        min_urgency_level="IMPORTANT",  # Only send IMPORTANT or CRITICAL
        duplicate_window_hours=24,  # Don't resend within 24h
        recurrence_threshold=3,  # Alert if happens 3+ times
    )

    print("🧠 Smart Slack Monitor")
    print("=" * 60)
    print(f"📊 Configuration:")
    print(f"   Minimum urgency: {monitor.min_urgency_level}")
    print(f"   Dedup window: {monitor.duplicate_window_hours}h")
    print(f"   Recurrence threshold: {monitor.recurrence_threshold}x")
    print(f"   Summary channel: #{SUMMARY_CHANNEL if SUMMARY_CHANNEL else 'None'}")
    print()

    # Run monitor
    await monitor.monitor_continuously()


if __name__ == "__main__":
    asyncio.run(main())
