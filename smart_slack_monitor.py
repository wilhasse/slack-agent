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
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict

from slack_monitor import SlackMonitor, SlackMessage


@dataclass
class Alert:
    """Represents a processed alert"""
    message_id: str
    channel: str
    user: str
    text: str
    timestamp: str
    importance: str
    reason: str
    content_hash: str
    pattern_signature: str
    sent_to_slack: bool = False
    first_seen: str = None
    last_seen: str = None
    occurrence_count: int = 1


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
        recurrence_threshold: int = 3,  # Alert if same issue happens 3+ times
        slack_webhook_url: str = None,  # Alternative to MCP for sending messages
        interaction_check_interval: int = 5,  # Check for interactions every 5 seconds
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.min_urgency_level = min_urgency_level
        self.duplicate_window_hours = duplicate_window_hours
        self.critical_dedup_hours = critical_dedup_hours
        self.recurrence_threshold = recurrence_threshold
        self.slack_webhook_url = slack_webhook_url
        self.interaction_check_interval = interaction_check_interval
        self.last_interaction_check = datetime.now()
        self._client_lock = asyncio.Lock()  # Prevent concurrent Claude queries

        self._init_database()

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
        Extract a pattern signature from the message.

        This identifies the "type" of alert (e.g., "API timeout in prod-alerts")
        regardless of specific details.
        """
        # Extract key terms (you can make this smarter)
        text_lower = text.lower()

        # Common error patterns
        patterns = []
        if "error" in text_lower or "erro" in text_lower:
            patterns.append("error")
        if "timeout" in text_lower:
            patterns.append("timeout")
        if "failed" in text_lower or "falha" in text_lower:
            patterns.append("failed")
        if "down" in text_lower or "offline" in text_lower:
            patterns.append("down")
        if "api" in text_lower:
            patterns.append("api")
        if "database" in text_lower or "db" in text_lower:
            patterns.append("database")
        if "deploy" in text_lower:
            patterns.append("deploy")

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
            SELECT id, first_seen, occurrence_count, last_sent
            FROM patterns
            WHERE pattern_signature = ?
        """, (pattern_signature,))

        result = cursor.fetchone()

        if result:
            # Update existing pattern
            pattern_id, first_seen, count, last_sent = result
            new_count = count + 1

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
                "last_sent": last_sent
            }
        else:
            # New pattern
            cursor.execute("""
                INSERT INTO patterns (pattern_signature, first_seen, last_seen)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (pattern_signature,))

            pattern_info = {
                "is_new": True,
                "occurrence_count": 1,
                "first_seen": datetime.now().isoformat(),
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
        Intelligently decide if this alert should be sent to Slack.

        Returns: (should_send, reason)
        """
        # Rule 1: Only send if meets minimum urgency
        if alert.importance == "NORMAL" or alert.importance == "IGNORE":
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
        if self._is_duplicate(alert.content_hash):
            return False, f"Duplicate alert within {self.duplicate_window_hours}h window"

        # Rule 4: For IMPORTANT - check if it's a recurrent pattern
        if pattern_info["occurrence_count"] >= self.recurrence_threshold:
            # Check if we recently sent this pattern
            if pattern_info["last_sent"]:
                last_sent = datetime.fromisoformat(pattern_info["last_sent"])
                hours_since = (datetime.now() - last_sent).total_seconds() / 3600

                if hours_since < self.duplicate_window_hours:
                    return False, f"Pattern already sent {hours_since:.1f}h ago"

            return True, f"Recurrent issue ({pattern_info['occurrence_count']} occurrences)"

        # Rule 5: For new important issues - ask Claude for final decision
        if pattern_info["is_new"]:
            # Use Claude to make final decision based on context
            should_send = await self._ask_claude_for_decision(alert, pattern_info)
            if should_send:
                return True, "Claude determined this is worth sending"
            else:
                return False, "Claude determined this is not urgent enough"

        return False, f"Not recurrent enough ({pattern_info['occurrence_count']} occurrences)"

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
            await self.client.query(query)

            response = ""
            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            response += block.text

            # Parse response
            response_upper = response.upper()
            if "YES" in response_upper[:10]:
                return True
            else:
                return False
        except Exception as e:
            print(f"⚠️  Error asking Claude for decision: {e}")
            # Default to not sending if there's an error
            return False

    async def _check_for_interactions(self):
        """Check if anyone is asking questions in the summary channel"""
        # Check if interactive mode is enabled
        if not getattr(self, 'interactive_mode', False):
            return

        if not self.summary_channel or not self.client:
            return

        # Use lock to prevent concurrent Claude queries
        async with self._client_lock:
            # Use separate time tracking for interactions
            seconds_ago = int((datetime.now() - self.last_interaction_check).total_seconds())

            query = f"""USE Slack tools to check messages from #{self.summary_channel} in the last {seconds_ago} seconds.

Look for ANY messages from human users (NOT from bots or automated systems).

IMPORTANT:
- Include ALL user messages, even simple statements
- Ignore messages from bots (bot_id present or subtype: bot_message)
- Ignore messages from yourself (the monitoring system)

For EACH human user message found, respond with:
---INTERACTION---
User: [username]
Text: [message text]
---END INTERACTION---

If no human messages found, say "No interactions found"."""

            try:
                await self.client.query(query)

                response_text = ""
                async for msg in self.client.receive_response():
                    if hasattr(msg, 'content'):
                        for block in msg.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

                # Debug: Show what Claude said
                if response_text and "No interactions found" not in response_text:
                    print(f"🔍 Interaction check response: {response_text[:200]}")

                # Check if there are interactions
                if "---INTERACTION---" in response_text:
                    print(f"💬 Found user interaction in #{self.summary_channel}")
                    await self._handle_interaction(response_text)

                # Update last interaction check time
                self.last_interaction_check = datetime.now()

            except Exception as e:
                print(f"⚠️ Error checking interactions: {e}")
                # Still update check time to avoid getting stuck
                self.last_interaction_check = datetime.now()

    async def _handle_interaction(self, interaction_text: str):
        """Respond to user questions with context from alert history"""
        # Extract user and question
        lines = interaction_text.split('\n')
        user = ""
        question = ""

        for line in lines:
            if line.startswith("User:"):
                user = line.replace("User:", "").strip()
            elif line.startswith("Text:"):
                question = line.replace("Text:", "").strip()

        if not question:
            return

        print(f"   Question from @{user}: {question[:60]}...")

        # Get recent alert context from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT channel, text, importance, reason, created_at
            FROM alerts
            WHERE created_at > datetime('now', '-24 hours')
            ORDER BY created_at DESC
            LIMIT 20
        """)

        recent_alerts = cursor.fetchall()
        conn.close()

        # Build context for Claude
        context_parts = ["Recent alerts (last 24h):"]
        for channel, text, importance, reason, created_at in recent_alerts:
            preview = text[:100] if text else ""
            context_parts.append(f"- [{importance}] #{channel}: {preview}")

        context = "\n".join(context_parts)

        # Ask Claude to respond with context
        response_query = f"""You are monitoring Slack alerts. A user asked you a question in the monitoring channel.

USER QUESTION: "{question}"

RECENT ALERTS CONTEXT:
{context}

Please provide a helpful, concise response (2-3 sentences max) that:
1. Answers their question using the alert context
2. Is friendly and professional
3. Uses Portuguese if the question was in Portuguese

Your response will be posted directly to Slack."""

        try:
            await self.client.query(response_query)

            response_text = ""
            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            response_text += block.text

            # Send response to Slack
            if response_text.strip():
                reply = f"💬 @{user}: {response_text.strip()}"
                success = await self._send_to_slack(reply)
                if success:
                    print(f"   ✅ Responded to @{user}")
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
Text: [full message text]
Importance: [CRITICAL/IMPORTANT/NORMAL/IGNORE]
Reason: [why this matters or doesn't]
---END MESSAGE---

Be thorough - I need ALL fields for each message."""
            else:
                query = f"""USE Slack tools to search for messages with keywords: {", ".join(self.keywords)}

From the last {minutes_ago} minutes.

For EACH message found, provide in this EXACT format:

---MESSAGE---
Channel: [channel name]
User: [username]
Text: [full message text]
Importance: [CRITICAL/IMPORTANT/NORMAL/IGNORE]
Reason: [why this matters]
---END MESSAGE---"""

            await self.client.query(query)

            raw_analysis = ""
            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            raw_analysis += block.text

            print(f"\n📊 Raw Analysis:\n{raw_analysis}\n")

            # Parse Claude's response into alerts
            alerts = self._parse_analysis(raw_analysis)

            print(f"\n📋 Found {len(alerts)} messages to analyze")

            # Process each alert
            alerts_to_send = []

            for alert in alerts:
                # Compute signatures
                alert.content_hash = self._compute_content_hash(alert.text)
                alert.pattern_signature = self._extract_pattern_signature(alert.text, alert.channel)

                # Update pattern tracking
                pattern_info = self._update_pattern_tracking(alert.pattern_signature)

                # Decide if we should send this alert
                should_send, reason = await self._should_send_alert(alert, pattern_info)

                # Save to database
                self._save_alert(alert, sent=should_send)
                self._log_decision(alert, "SEND" if should_send else "SKIP", reason)

                # Log decision with preview
                status_icon = "✅" if should_send else "⏭️"
                msg_preview = alert.text[:60] + "..." if len(alert.text) > 60 else alert.text
                print(f"{status_icon} [{alert.importance}] #{alert.channel} - {reason}")
                if should_send:
                    print(f"   📝 Message: \"{msg_preview}\"")

                if should_send:
                    alerts_to_send.append(alert)
                    self._mark_pattern_sent(alert.pattern_signature)

            # Update last check time
            self.last_check_time = datetime.now()

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
                alert = Alert(
                    message_id=hashlib.md5(f"{alert_data.get('channel', '')}{alert_data.get('text', '')}{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                    channel=alert_data.get("channel", "unknown"),
                    user=alert_data.get("user", "unknown"),
                    text=alert_data.get("text", ""),
                    timestamp=datetime.now().isoformat(),
                    importance=alert_data.get("importance", "NORMAL").upper(),
                    reason=alert_data.get("reason", ""),
                    content_hash="",
                    pattern_signature=""
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

        summary_parts = [f"🔔 *Alertas - {timestamp}*\n"]

        if critical:
            summary_parts.append(f"🚨 *{len(critical)} CRÍTICO:*")
            for i, alert in enumerate(critical, 1):
                # Very compact format - one line per alert
                msg_text = alert.text.strip() if alert.text else "[No text]"
                if len(msg_text) > 80:
                    msg_text = msg_text[:80] + "..."

                # Single line format
                summary_parts.append(f"{i}. #{alert.channel} - {msg_text}")

        if important:
            summary_parts.append(f"\n⚠️ *{len(important)} IMPORTANTE:*")
            for i, alert in enumerate(important, 1):
                msg_text = alert.text.strip() if alert.text else "[No text]"
                if len(msg_text) > 80:
                    msg_text = msg_text[:80] + "..."

                # Single line format
                summary_parts.append(f"{i}. #{alert.channel} - {msg_text}")

        summary_parts.append("\n_Monitor inteligente - somente alertas urgentes/recorrentes_")

        summary = "\n".join(summary_parts)

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

        query = f"""Use the mcp__slack__conversations_add_message tool with these parameters:

channel: "{self.summary_channel}"
text: The complete alert message below

IMPORTANT: Send the COMPLETE message including ALL lines. Do not truncate or summarize.

Message (send exactly as shown):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{safe_message}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        try:
            await self.client.query(query)

            # Consume and check response
            response = ""
            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            response += block.text

            # Verify if it actually worked
            response_lower = response.lower()
            if "error" in response_lower or "failed" in response_lower or "not found" in response_lower:
                print(f"   MCP error: {response[:300]}")
                return False
            else:
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
        message = f"""🤖 *Smart Slack Monitor Started*

📅 Started at: {timestamp}
⏱️  Check interval: {self.check_interval}s
🎯 Min urgency: {self.min_urgency_level}
🔄 Dedup window: {self.duplicate_window_hours}h
📊 Recurrence threshold: {self.recurrence_threshold}x

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
        print(f"🔍 Starting Smart Slack Monitor...")
        print(f"   Checking alerts every {self.check_interval} seconds")
        if getattr(self, 'interactive_mode', False):
            print(f"   Checking interactions every {self.interaction_check_interval} seconds")
        print(f"   Keywords: {', '.join(self.keywords)}")
        if self.channels_to_monitor:
            print(f"   Channels: {', '.join(self.channels_to_monitor)}")
        else:
            print(f"   Monitoring: All channels with keywords")
        if self.summary_channel:
            print(f"   📤 Sending filtered alerts to: #{self.summary_channel}")
        print()

        await self.connect()

        # Send startup notification
        await self._send_startup_notification()

        # Start interaction loop as a separate task (if enabled)
        interaction_task = None
        if getattr(self, 'interactive_mode', False):
            interaction_task = asyncio.create_task(self._interaction_loop())

        try:
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
