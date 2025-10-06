#!/usr/bin/env python3
"""
Advanced Slack Monitor Example

Shows how to extend the basic monitor with:
- Desktop notifications
- Message persistence (SQLite)
- Custom filtering logic
- Multi-workspace support
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from slack_monitor import SlackMonitor, SlackMessage


class AdvancedSlackMonitor(SlackMonitor):
    """Extended monitor with notifications and persistence"""

    def __init__(
        self,
        db_path: str = "slack_messages.db",
        enable_notifications: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.enable_notifications = enable_notifications
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for message history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                user TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                importance TEXT,
                reason TEXT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT FALSE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                messages_found INTEGER,
                critical_count INTEGER,
                important_count INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def _save_message(self, message: SlackMessage):
        """Save message to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO messages
            (channel, user, text, timestamp, importance, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message.channel,
            message.user,
            message.text,
            message.timestamp,
            message.importance,
            message.reason
        ))

        conn.commit()
        conn.close()

    def _send_desktop_notification(self, title: str, message: str):
        """Send desktop notification (platform-specific)"""
        if not self.enable_notifications:
            return

        try:
            # Try using notify-send (Linux)
            import subprocess
            subprocess.run([
                "notify-send",
                "--icon=dialog-information",
                "--urgency=critical",
                title,
                message
            ], check=False)
        except Exception:
            # Fallback: just print
            print(f"\n🔔 {title}\n   {message}\n")

    async def check_messages(self) -> List[SlackMessage]:
        """Override to add notifications and persistence"""
        messages = await super().check_messages()

        # Count by importance
        critical = [m for m in messages if m.importance == "CRITICAL"]
        important = [m for m in messages if m.importance == "IMPORTANT"]

        # Save to database
        for msg in messages:
            self._save_message(msg)

        # Save check history
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO check_history
            (messages_found, critical_count, important_count)
            VALUES (?, ?, ?)
        """, (len(messages), len(critical), len(important)))
        conn.commit()
        conn.close()

        # Send notifications for critical messages
        if critical:
            self._send_desktop_notification(
                "🚨 Critical Slack Messages",
                f"{len(critical)} critical messages need immediate attention!"
            )

        return messages

    def get_recent_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics for recent messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN importance = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN importance = 'IMPORTANT' THEN 1 ELSE 0 END) as important,
                SUM(CASE WHEN importance = 'NORMAL' THEN 1 ELSE 0 END) as normal
            FROM messages
            WHERE checked_at > datetime('now', '-' || ? || ' hours')
        """, (hours,))

        result = cursor.fetchone()
        conn.close()

        return {
            "total": result[0] or 0,
            "critical": result[1] or 0,
            "important": result[2] or 0,
            "normal": result[3] or 0,
            "hours": hours
        }


class MultiWorkspaceMonitor:
    """Monitor multiple Slack workspaces"""

    def __init__(self, workspaces: Dict[str, Dict[str, Any]]):
        """
        Args:
            workspaces: Dict of workspace configs, e.g.:
                {
                    "work": {
                        "xoxc_token": "...",
                        "xoxd_token": "...",
                        "channels": ["general", "alerts"],
                        "keywords": ["urgent", "critical"]
                    },
                    "community": {
                        "xoxc_token": "...",
                        "xoxd_token": "...",
                        "channels": ["announcements"],
                        "keywords": ["important"]
                    }
                }
        """
        self.workspaces = workspaces
        self.monitors: Dict[str, AdvancedSlackMonitor] = {}

    async def start_all(self):
        """Start monitoring all workspaces"""
        tasks = []

        for name, config in self.workspaces.items():
            # Create MCP config for this workspace
            mcp_config = {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@korotovsky/slack-mcp-server"],
                "env": {
                    "SLACK_MCP_XOXC_TOKEN": config["xoxc_token"],
                    "SLACK_MCP_XOXD_TOKEN": config["xoxd_token"]
                }
            }

            monitor = AdvancedSlackMonitor(
                channels_to_monitor=config.get("channels", []),
                keywords=config.get("keywords", []),
                check_interval=config.get("check_interval", 300),
                mcp_server_config=mcp_config,
                db_path=f"slack_{name}.db"
            )

            self.monitors[name] = monitor

            # Create monitoring task
            task = asyncio.create_task(
                self._monitor_workspace(name, monitor)
            )
            tasks.append(task)

        # Run all workspace monitors concurrently
        await asyncio.gather(*tasks)

    async def _monitor_workspace(self, name: str, monitor: AdvancedSlackMonitor):
        """Monitor a single workspace"""
        print(f"🚀 Starting monitor for workspace: {name}")
        try:
            await monitor.monitor_continuously()
        except Exception as e:
            print(f"❌ Error monitoring {name}: {e}")


# Example usage

async def example_advanced_monitor():
    """Example: Advanced monitor with persistence"""

    monitor = AdvancedSlackMonitor(
        channels_to_monitor=["alerts", "incidents"],
        keywords=["urgent", "critical", "down", "error"],
        check_interval=60,  # Check every minute
        db_path="important_messages.db",
        enable_notifications=True
    )

    print("🔍 Starting advanced Slack monitor...")
    print("   - Desktop notifications enabled")
    print("   - Message persistence to SQLite")
    print()

    await monitor.connect()

    try:
        # Check messages once
        messages = await monitor.check_messages()

        # Get statistics
        stats = monitor.get_recent_stats(hours=24)
        print(f"\n📊 Last 24 hours:")
        print(f"   Total messages: {stats['total']}")
        print(f"   Critical: {stats['critical']}")
        print(f"   Important: {stats['important']}")
        print(f"   Normal: {stats['normal']}")

        # Or run continuously
        # await monitor.monitor_continuously()

    finally:
        await monitor.disconnect()


async def example_multi_workspace():
    """Example: Monitor multiple Slack workspaces"""

    import os

    multi_monitor = MultiWorkspaceMonitor({
        "work": {
            "xoxc_token": os.getenv("WORK_SLACK_XOXC_TOKEN"),
            "xoxd_token": os.getenv("WORK_SLACK_XOXD_TOKEN"),
            "channels": ["general", "alerts", "incidents"],
            "keywords": ["urgent", "critical", "production"],
            "check_interval": 120
        },
        "community": {
            "xoxc_token": os.getenv("COMMUNITY_SLACK_XOXC_TOKEN"),
            "xoxd_token": os.getenv("COMMUNITY_SLACK_XOXD_TOKEN"),
            "channels": ["announcements"],
            "keywords": ["important", "breaking"],
            "check_interval": 600
        }
    })

    await multi_monitor.start_all()


async def example_custom_filter():
    """Example: Custom message filtering"""

    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

    # Create a custom system prompt for very specific filtering
    custom_prompt = """You are analyzing Slack messages for a DevOps engineer.

    CRITICAL - Immediate attention needed:
    - Production outages or errors
    - Security incidents
    - Customer-impacting issues
    - Messages from your manager or CEO
    - On-call alerts

    IMPORTANT - Review within 1 hour:
    - Build/deployment failures
    - Code review requests on your PRs
    - Meeting reminders in next 2 hours
    - Team announcements

    NORMAL - Review when convenient:
    - General team chat
    - Non-urgent questions
    - FYI messages

    IGNORE:
    - Bot spam
    - Off-topic chat
    - Automated reports
    """

    monitor = AdvancedSlackMonitor(
        channels_to_monitor=["team", "alerts", "deploys"],
        keywords=["deploy", "error", "failed", "review"],
        check_interval=180
    )

    # Override system prompt
    monitor.options.system_prompt = custom_prompt

    await monitor.check_once()


if __name__ == "__main__":
    # Choose which example to run:

    # Example 1: Advanced monitor with notifications
    asyncio.run(example_advanced_monitor())

    # Example 2: Multi-workspace monitoring
    # asyncio.run(example_multi_workspace())

    # Example 3: Custom filtering
    # asyncio.run(example_custom_filter())
