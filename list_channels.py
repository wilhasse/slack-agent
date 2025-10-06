#!/usr/bin/env python3
"""
Simple script to list all Slack channels
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from slack_monitor import SlackMonitor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def list_channels():
    """List all Slack channels"""

    print("🔍 Fetching Slack Channels...")
    print("=" * 60)

    # Create monitor
    monitor = SlackMonitor(
        keywords=["urgent"],  # Doesn't matter for listing channels
        check_interval=300
    )

    # Connect
    await monitor.connect()

    try:
        # Query Claude to list channels
        await monitor.client.query(
            "List all Slack channels using the mcp__slack__channels_list tool. "
            "Show me the channel names and IDs in a clear format."
        )

        print()
        async for msg in monitor.client.receive_response():
            # Import here to avoid issues
            from claude_agent_sdk import AssistantMessage, TextBlock

            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print()

    finally:
        await monitor.disconnect()


if __name__ == "__main__":
    asyncio.run(list_channels())
