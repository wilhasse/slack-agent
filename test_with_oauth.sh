#!/bin/bash
# Test Slack chat with OAuth token

echo "🧪 Testing Slack MCP with OAuth token..."
echo ""

# Load OAuth token
source .env.oauth

# Activate venv
source venv/bin/activate

# Override the MCP config to use OAuth token
export SLACK_BOT_TOKEN
export SLACK_MCP_XOXP_TOKEN

echo "✅ OAuth token loaded"
echo "   Token: ${SLACK_BOT_TOKEN:0:20}...${SLACK_BOT_TOKEN: -10}"
echo ""

echo "🚀 Starting interactive chat..."
echo ""

# Update slack_chat.py to use OAuth token
python3 << 'EOFPYTHON'
import asyncio
import os
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock
)

async def test_oauth():
    binary = Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server"

    oauth_token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_MCP_XOXP_TOKEN")

    if not oauth_token:
        print("❌ OAuth token not set!")
        return

    print(f"Using token: {oauth_token[:20]}...{oauth_token[-10:]}")

    slack_mcp_config = {
        "type": "stdio",
        "command": str(binary),
        "args": ["--transport", "stdio"],
        "env": {
            "SLACK_BOT_TOKEN": oauth_token,
            "SLACK_MCP_XOXP_TOKEN": oauth_token
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers={"slack": slack_mcp_config},
        allowed_tools=[
            "mcp__slack__channels_list",
            "mcp__slack__conversations_history",
        ],
        system_prompt="You have access to Slack via MCP tools. Use them to answer questions.",
        permission_mode="bypassPermissions"
    )

    print("\n🔌 Connecting to Slack with OAuth token...")

    async with ClaudeSDKClient(options=options) as client:
        print("✅ Connected!")
        print("\nAsking: 'List my Slack channels'\n")

        await client.query("Use the channels_list tool to list all my Slack channels")

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"[Tool: {block.name}]")
                    elif isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(test_oauth())
EOFPYTHON

echo ""
echo "✅ Test complete!"
