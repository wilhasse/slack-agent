#!/usr/bin/env python3
"""
Direct script to list all Slack channels using the local slack-mcp-server
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def list_channels():
    """List all Slack channels"""

    print("🔍 Fetching Slack Channels...")
    print("=" * 60)

    # Get the path to the slack-mcp-server binary
    slack_mcp_path = str(Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server")

    # Configure MCP server for Slack using local binary
    mcp_server_config = {
        "type": "stdio",
        "command": slack_mcp_path,
        "args": [],
        "env": {
            "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN", ""),
            "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN", ""),
        }
    }

    # Set up Claude options with Slack MCP server
    options = ClaudeAgentOptions(
        mcp_servers={"slack": mcp_server_config},
        allowed_tools=[
            "mcp__slack__channels_list",
            "mcp__slack__conversations_history",
            "mcp__slack__conversations_replies",
            "mcp__slack__conversations_search_messages"
        ],
        system_prompt="You are a helpful assistant with access to Slack via MCP tools. Use the tools to answer questions.",
        permission_mode="bypassPermissions"
    )

    # Create client and connect
    client = ClaudeSDKClient(options=options)
    await client.connect()
    print("✅ Connected to Slack MCP server")

    try:
        # Query to list channels
        await client.query(
            "Use the mcp__slack__channels_list tool to list all my Slack channels. "
            "Show me the channel names and IDs in a clear, formatted list."
        )

        print("\n📋 Your Slack Channels:\n")
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print()

    finally:
        await client.disconnect()
        print("👋 Disconnected from Slack MCP server")


if __name__ == "__main__":
    asyncio.run(list_channels())
