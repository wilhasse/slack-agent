"""SQLite persistence layer shared by realtime and digest monitors."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .models import AlertRecord, SeverityLevel


class AlertStore:
    """Repository for alert records, recurrence tracking, and monitor state."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    channel TEXT NOT NULL,
                    channel_label TEXT,
                    user TEXT,
                    text TEXT NOT NULL,
                    slack_ts TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    reason TEXT,
                    content_hash TEXT,
                    pattern_signature TEXT,
                    detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    event_ts DATETIME,
                    sent_to_slack BOOLEAN DEFAULT FALSE
                )
                """
            )
            self._ensure_column(cursor, "alerts", "channel_label", "TEXT", update_sql="UPDATE alerts SET channel_label = channel WHERE channel_label IS NULL OR channel_label = ''")
            self._ensure_column(cursor, "alerts", "detected_at", "DATETIME DEFAULT CURRENT_TIMESTAMP", update_sql="UPDATE alerts SET detected_at = COALESCE(detected_at, created_at, CURRENT_TIMESTAMP)")
            self._ensure_column(cursor, "alerts", "event_ts", "DATETIME")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_channel ON alerts(channel)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_detected_at ON alerts(detected_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_content_hash ON alerts(content_hash)")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_log_message ON decision_log(message_id)")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def record_alert(self, alert: AlertRecord) -> bool:
        """Insert alert and return True if stored (False if duplicate)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO alerts (
                        message_id,
                        channel,
                        channel_label,
                        user,
                        text,
                        slack_ts,
                        importance,
                        reason,
                        content_hash,
                        pattern_signature,
                        detected_at,
                        event_ts,
                        sent_to_slack
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert.message_id,
                        alert.channel_id,
                        alert.channel_label,
                        alert.user,
                        alert.text,
                        alert.slack_ts,
                        alert.importance.value,
                        alert.decision_reason,
                        alert.content_hash,
                        alert.pattern_signature,
                        alert.detected_at.isoformat(),
                        alert.event_ts.isoformat() if alert.event_ts else None,
                        1 if alert.sent_to_slack else 0,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO decision_log (message_id, decision, reason)
                    VALUES (?, ?, ?)
                    """,
                    (
                        alert.message_id,
                        alert.importance.value,
                        alert.decision_reason,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_sent(self, message_id: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE alerts SET sent_to_slack = 1 WHERE message_id = ?",
                (message_id,),
            )
            conn.commit()

    def has_message(self, message_id: str) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM alerts WHERE message_id = ? LIMIT 1", (message_id,))
            return cursor.fetchone() is not None

    def count_recent_occurrences(self, content_hash: str, window_minutes: int) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE content_hash = ?
                  AND detected_at >= datetime('now', ?)
                """,
                (content_hash, f"-{window_minutes} minutes"),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def fetch_recent_alerts(
        self,
        lookback_minutes: int,
        include_filtered: bool = True,
        min_severity: SeverityLevel = SeverityLevel.IGNORE,
    ) -> List[AlertRecord]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    message_id,
                    channel,
                    channel_label,
                    user,
                    text,
                    slack_ts,
                    importance,
                    reason,
                    detected_at,
                    sent_to_slack,
                    content_hash,
                    pattern_signature,
                    event_ts
                FROM alerts
                WHERE detected_at >= datetime('now', ?)
                ORDER BY detected_at DESC
                """,
                (f"-{lookback_minutes} minutes",),
            )
            rows = cursor.fetchall()

        severity_min_index = {level: index for index, level in enumerate(SeverityLevel.ordered())}[
            min_severity
        ]

        alerts: List[AlertRecord] = []
        for row in rows:
            severity = SeverityLevel(row[6])
            sent_to_slack = bool(row[9])
            if not include_filtered and not sent_to_slack:
                continue
            if severity_min_index > {level: index for index, level in enumerate(SeverityLevel.ordered())}[severity]:
                continue
            detected_at = datetime.fromisoformat(row[8])
            event_ts = datetime.fromisoformat(row[12]) if row[12] else None
            alerts.append(
                AlertRecord(
                    message_id=row[0],
                    channel_id=row[1],
                    channel_label=row[2] or row[1],
                    user=row[3],
                    text=row[4],
                    slack_ts=row[5],
                    importance=severity,
                    decision_reason=row[7] or "",
                    detected_at=detected_at,
                    sent_to_slack=sent_to_slack,
                    content_hash=row[10],
                    pattern_signature=row[11],
                    event_ts=event_ts,
                )
            )
        return alerts

    def iter_recent_alerts(self, since_minutes: int) -> Iterable[AlertRecord]:
        return self.fetch_recent_alerts(lookback_minutes=since_minutes, include_filtered=True)

    def get_state(self, key: str) -> Optional[str]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM monitor_state WHERE key = ? LIMIT 1", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO monitor_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
            conn.commit()

    def purge_old_alerts(self, older_than_days: int = 30) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM alerts WHERE detected_at < datetime('now', ?)",
                (f"-{older_than_days} days",),
            )
            deleted = cursor.rowcount or 0
            cursor.execute(
                "DELETE FROM decision_log WHERE created_at < datetime('now', ?)",
                (f"-{older_than_days} days",),
            )
            conn.commit()
            return deleted

    @staticmethod
    def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str, update_sql: Optional[str] = None) -> None:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        if column not in columns:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError as error:
                if "non-constant default" in str(error).lower():
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
                else:
                    raise
            if update_sql:
                try:
                    cursor.execute(update_sql)
                except sqlite3.OperationalError:
                    # best effort; ignore if legacy column missing
                    pass

    def get_statistics(self, hours: int = 24) -> Dict[str, int]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN sent_to_slack = 1 THEN 1 ELSE 0 END) AS sent,
                    SUM(CASE WHEN importance = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
                    SUM(CASE WHEN importance = 'IMPORTANT' THEN 1 ELSE 0 END) AS important
                FROM alerts
                WHERE detected_at >= datetime('now', ?)
                """,
                (f"-{hours} hours",),
            )
            total, sent, critical, important = cursor.fetchone()

            cursor.execute(
                """
                SELECT channel, COUNT(*)
                FROM alerts
                WHERE detected_at >= datetime('now', ?)
                GROUP BY channel
                ORDER BY COUNT(*) DESC
                LIMIT 5
                """,
                (f"-{hours} hours",),
            )
            top_channels = cursor.fetchall()

        return {
            "total": total or 0,
            "sent": sent or 0,
            "critical": critical or 0,
            "important": important or 0,
            "top_channels": top_channels,
        }
