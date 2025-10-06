#!/usr/bin/env python3
"""
Test Slack MCP tools - Simple step-by-step testing
"""

import asyncio
import os
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def test_list_channels():
    """Test 1: List all Slack channels"""

    print("=" * 70)
    print("TEST 1: Listing Slack Channels")
    print("=" * 70)
    print()

    # Configure Slack MCP
    slack_mcp_config = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@korotovsky/slack-mcp-server"],
        "env": {
            "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN", ""),
            "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN", ""),
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers={"slack": slack_mcp_config},
        allowed_tools=["mcp__slack__channels_list"],
        system_prompt="You are a helpful assistant with access to Slack via MCP tools. When asked about channels, USE the mcp__slack__channels_list tool.",
        permission_mode="bypassPermissions"
    )

    print("🔌 Connecting to Slack...")
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Use the channels_list tool to show me all my Slack channels. List them clearly.")

        print("📡 Waiting for response...\n")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"✅ Tool used: {block.name}")
                    elif isinstance(block, TextBlock):
                        print(f"\n📋 Response:\n{block.text}")

    print("\n" + "=" * 70 + "\n")


async def test_find_cslog_channels():
    """Test 2: Find channels starting with cslog-alertas"""

    print("=" * 70)
    print("TEST 2: Finding cslog-alertas* Channels")
    print("=" * 70)
    print()

    slack_mcp_config = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@korotovsky/slack-mcp-server"],
        "env": {
            "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN", ""),
            "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN", ""),
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers={"slack": slack_mcp_config},
        allowed_tools=["mcp__slack__channels_list"],
        system_prompt="You are a helpful assistant with access to Slack. USE the MCP tools to get real data.",
        permission_mode="bypassPermissions"
    )

    print("🔌 Connecting to Slack...")
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "Use the channels_list tool to find all channels that start with 'cslog-alertas'. "
            "Show me their names clearly."
        )

        print("📡 Waiting for response...\n")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"✅ Tool used: {block.name}")
                    elif isinstance(block, TextBlock):
                        print(f"\n📋 Channels found:\n{block.text}")

    print("\n" + "=" * 70 + "\n")


async def test_get_messages():
    """Test 3: Get recent messages from a channel"""

    print("=" * 70)
    print("TEST 3: Getting Recent Messages")
    print("=" * 70)
    print()

    channel_name = input("Enter a channel name to check (or press Enter to skip): ").strip()

    if not channel_name:
        print("⏭️  Skipped")
        return

    slack_mcp_config = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@korotovsky/slack-mcp-server"],
        "env": {
            "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN", ""),
            "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN", ""),
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers={"slack": slack_mcp_config},
        allowed_tools=[
            "mcp__slack__conversations_history",
            "mcp__slack__channels_list"
        ],
        system_prompt="You have access to Slack via MCP tools. USE these tools to get real messages.",
        permission_mode="bypassPermissions"
    )

    print(f"\n🔌 Connecting to Slack...")
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            f"Use the conversations_history tool to get the most recent messages from #{channel_name}. "
            f"Show me the last 5 messages with their text and authors."
        )

        print("📡 Waiting for response...\n")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"✅ Tool used: {block.name}")
                    elif isinstance(block, TextBlock):
                        print(f"\n📬 Messages:\n{block.text}")

    print("\n" + "=" * 70 + "\n")


async def main():
    """Run all tests"""

    # Check tokens
    if not os.getenv("SLACK_MCP_XOXC_TOKEN") or not os.getenv("SLACK_MCP_XOXD_TOKEN"):
        print("❌ Slack tokens not set!")
        print()
        print("Please set:")
        print("  export SLACK_MCP_XOXC_TOKEN='xoxc-...'")
        print("  export SLACK_MCP_XOXD_TOKEN='xoxd-...'")
        print()
        return

    print("\n🧪 Testing Slack MCP Tools\n")

    try:
        # Test 1: List all channels
        await test_list_channels()

        # Test 2: Find cslog-alertas channels
        await test_find_cslog_channels()

        # Test 3: Get messages (optional)
        await test_get_messages()

        print("✅ All tests completed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
