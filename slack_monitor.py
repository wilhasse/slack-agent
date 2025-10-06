#!/usr/bin/env python3
"""
Slack Alert Monitor using Claude Agent SDK
Monitors Slack channels and filters messages that deserve attention
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set
from dataclasses import dataclass
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock
)


@dataclass
class SlackMessage:
    """Represents a Slack message"""
    channel: str
    user: str
    text: str
    timestamp: str
    thread_ts: str | None = None
    importance: str | None = None
    reason: str | None = None


class SlackMonitor:
    """Monitors Slack channels and filters important messages"""

    def __init__(
        self,
        channels_to_monitor: List[str] = None,
        keywords: List[str] = None,
        check_interval: int = 300,  # 5 minutes
        mcp_server_config: Dict[str, Any] = None,
        summary_channel: str = None
    ):
        """
        Initialize Slack Monitor

        Args:
            channels_to_monitor: List of channel names/IDs to monitor (None = all channels)
            keywords: Keywords that indicate importance (e.g., ["urgent", "critical", "help"])
            check_interval: How often to check for new messages (seconds)
            mcp_server_config: Configuration for the Slack MCP server
            summary_channel: Channel to send analysis summaries to (None = don't send)
        """
        self.channels_to_monitor = channels_to_monitor or []
        self.keywords = keywords or ["urgent", "critical", "emergency", "help", "alert"]
        self.check_interval = check_interval
        self.summary_channel = summary_channel
        self.seen_messages: Set[str] = set()
        self.last_check_time = datetime.now()

        # Configure MCP server for Slack
        if not mcp_server_config:
            # Default stdio configuration using compiled binary
            mcp_binary = Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server"

            # Check for OAuth token first (preferred)
            oauth_token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_MCP_XOXP_TOKEN")

            if oauth_token:
                mcp_server_config = {
                    "type": "stdio",
                    "command": str(mcp_binary),
                    "args": ["--transport", "stdio"],
                    "env": {
                        "SLACK_BOT_TOKEN": oauth_token,
                        "SLACK_MCP_XOXP_TOKEN": oauth_token,
                        "SLACK_MCP_ADD_MESSAGE_TOOL": "true",  # Enable posting messages
                    }
                }
            else:
                # Fallback to browser tokens
                mcp_server_config = {
                    "type": "stdio",
                    "command": str(mcp_binary),
                    "args": ["--transport", "stdio"],
                    "env": {
                        "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN", ""),
                        "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN", ""),
                        "SLACK_MCP_ADD_MESSAGE_TOOL": "true",  # Enable posting messages
                    }
                }

        # Set up Claude options with Slack MCP server
        # Note: Only include tools we actually need
        allowed_tools = [
            "mcp__slack__conversations_history",
            "mcp__slack__conversations_replies",
            "mcp__slack__conversations_search_messages",
        ]

        # Add posting tool if summary channel is configured
        if self.summary_channel:
            allowed_tools.append("mcp__slack__chat_postMessage")

        self.options = ClaudeAgentOptions(
            mcp_servers={"slack": mcp_server_config},
            allowed_tools=allowed_tools,
            system_prompt=self._create_system_prompt(),
            permission_mode="bypassPermissions"
        )

        self.client: ClaudeSDKClient | None = None

    def _create_system_prompt(self) -> str:
        """Create a system prompt for Claude to analyze Slack messages"""
        keywords_str = ", ".join(self.keywords)
        return f"""You are a Slack message analyzer helping filter important messages.

You have access to Slack via MCP tools. USE these tools to fetch real messages from Slack:
- mcp__slack__channels_list: List all channels
- mcp__slack__conversations_history: Get message history from channels
- mcp__slack__conversations_search_messages: Search for messages

Your job is to USE these tools to fetch messages and analyze which ones deserve immediate attention.

Consider a message important if it:
1. Contains urgent keywords: {keywords_str}
2. Asks direct questions to the user
3. Reports errors, incidents, or system failures
4. Requests immediate action or approval
5. Contains mentions or direct messages
6. Reports critical business metrics or alerts

For each message, classify it as:
- CRITICAL: Needs immediate attention
- IMPORTANT: Should be reviewed soon
- NORMAL: Can be reviewed later
- IGNORE: Not relevant or spam

Be concise and focus on actionable insights."""

    async def connect(self):
        """Connect to Claude with Slack MCP server"""
        self.client = ClaudeSDKClient(options=self.options)
        await self.client.connect()
        print("✅ Connected to Claude with Slack MCP server")

    async def disconnect(self):
        """Disconnect from Claude"""
        if self.client:
            await self.client.disconnect()
            print("👋 Disconnected from Claude")

    async def get_channels(self) -> List[Dict[str, Any]]:
        """Get list of Slack channels"""
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        await self.client.query(
            "List all Slack channels. Return the raw data from the tool."
        )

        channels = []
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        # Parse channel data from tool result
                        # This is a simplified version - actual parsing may vary
                        pass

        return channels

    async def check_messages(self) -> List[SlackMessage]:
        """Check for new messages in monitored channels"""
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Calculate time window
        minutes_ago = int((datetime.now() - self.last_check_time).total_seconds() / 60)

        # Build query based on channels to monitor
        if self.channels_to_monitor:
            channel_list = ", ".join(self.channels_to_monitor)
            query = f"""USE the Slack MCP tools to check messages from the following channels: {channel_list}

IMPORTANT: You must use the mcp__slack__conversations_history tool to fetch actual messages from each channel.

Look for messages from the last {minutes_ago} minutes.

For each important message you find, analyze and provide:
1. Channel name
2. User who sent it
3. Message text
4. Importance level (CRITICAL, IMPORTANT, NORMAL, IGNORE)
5. Brief reason why it's important or can be ignored

If no important messages are found, say so clearly."""
        else:
            query = f"""USE the Slack MCP tools to search for messages.

IMPORTANT: You must use the mcp__slack__conversations_search_messages tool to search for messages.

Search for messages from the last {minutes_ago} minutes containing these keywords:
{", ".join(self.keywords)}

For each important message you find, provide:
1. Channel name
2. User who sent it
3. Message text
4. Importance level (CRITICAL, IMPORTANT, NORMAL, IGNORE)
5. Brief reason

If no messages are found, say so clearly."""

        await self.client.query(query)

        messages = []
        current_analysis = ""

        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        current_analysis += block.text

        # Update last check time
        self.last_check_time = datetime.now()

        # Parse Claude's analysis into SlackMessage objects
        # This is simplified - you may want more robust parsing
        print("\n" + "="*80)
        print(f"📊 Slack Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*80)
        print(current_analysis)
        print("="*80 + "\n")

        # Send summary to Slack if configured
        if self.summary_channel and current_analysis.strip():
            await self._send_summary_to_slack(current_analysis)

        return messages

    async def _send_summary_to_slack(self, analysis: str):
        """Send analysis summary to configured Slack channel"""
        if not self.client:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"""📊 *Análise de Alertas - {timestamp}*

{analysis}

_Gerado automaticamente pelo Monitor de Slack_"""

        query = f"""USE the mcp__slack__chat_postMessage tool RIGHT NOW to send a message to the channel '{self.summary_channel}'.

IMPORTANT: Do NOT check if the channel exists first. Just send the message directly.

Send this exact message:
{message}

Use the channel name '{self.summary_channel}'. If you get an error, show me the EXACT error message."""

        try:
            await self.client.query(query)

            # Consume the response and show full output for debugging
            full_response = ""
            async for msg in self.client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            full_response += block.text

            # Debug: show what Claude actually said
            print(f"\n🔍 Claude's response to posting summary:")
            print(full_response)
            print("="*80)

            if "error" in full_response.lower() or "failed" in full_response.lower() or "not found" in full_response.lower():
                print(f"⚠️  Error detected in response!")
            elif "success" in full_response.lower() or "sent" in full_response.lower() or "posted" in full_response.lower():
                print(f"✅ Summary sent to #{self.summary_channel}")
            else:
                print(f"⚠️  Unclear response - check above")
        except Exception as e:
            print(f"❌ Failed to send summary to Slack: {e}")

    async def monitor_continuously(self):
        """Continuously monitor Slack channels"""
        print(f"🔍 Starting Slack monitor...")
        print(f"   Checking every {self.check_interval} seconds")
        print(f"   Keywords: {', '.join(self.keywords)}")
        if self.channels_to_monitor:
            print(f"   Channels: {', '.join(self.channels_to_monitor)}")
        else:
            print(f"   Monitoring: All channels with keywords")
        if self.summary_channel:
            print(f"   📤 Sending summaries to: #{self.summary_channel}")
        print()

        await self.connect()

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
            await self.disconnect()

    async def check_once(self):
        """Check messages once and exit"""
        await self.connect()
        try:
            messages = await self.check_messages()
            return messages
        finally:
            await self.disconnect()


async def main():
    """Example usage"""

    # Try to import configuration
    try:
        from config import (
            MONITORED_CHANNELS,
            IMPORTANCE_KEYWORDS,
            CHECK_INTERVAL,
            SLACK_MCP_CONFIG,
            SUMMARY_CHANNEL
        )
        print("✅ Loaded configuration from config.py")
    except ImportError:
        print("⚠️  Warning: config.py not found, using defaults")
        print("   Copy config_example.py to config.py and customize")
        MONITORED_CHANNELS = []
        IMPORTANCE_KEYWORDS = ["urgent", "critical", "emergency", "help", "alert"]
        CHECK_INTERVAL = 300
        SLACK_MCP_CONFIG = None
        SUMMARY_CHANNEL = None

    # Configure monitor
    monitor = SlackMonitor(
        channels_to_monitor=MONITORED_CHANNELS,
        keywords=IMPORTANCE_KEYWORDS,
        check_interval=CHECK_INTERVAL,
        mcp_server_config=SLACK_MCP_CONFIG,
        summary_channel=SUMMARY_CHANNEL
    )

    # Run continuously
    await monitor.monitor_continuously()

    # Or check once:
    # await monitor.check_once()


if __name__ == "__main__":
    asyncio.run(main())
