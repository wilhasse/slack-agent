#!/usr/bin/env python3
"""
Test posting a message to Slack channel
"""

import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
import os
from pathlib import Path

async def test_post():
    # Configure MCP server
    mcp_binary = Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server"

    oauth_token = os.getenv("SLACK_BOT_TOKEN") or "xoxb-YOUR-SLACK-BOT-TOKEN-HERE"

    mcp_config = {
        "type": "stdio",
        "command": str(mcp_binary),
        "args": ["--transport", "stdio"],
        "env": {
            "SLACK_BOT_TOKEN": oauth_token,
            "SLACK_MCP_XOXP_TOKEN": oauth_token,
            "SLACK_MCP_ADD_MESSAGE_TOOL": "true",  # Enable posting
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers={"slack": mcp_config},
        allowed_tools=["mcp__slack__conversations_add_message", "mcp__slack__channels_list"],
        permission_mode="bypassPermissions"
    )

    print("🔄 Connecting to Claude...")
    client = ClaudeSDKClient(options=options)
    await client.connect()
    print("✅ Connected!")

    print("\n📋 First, let's check if we can see #cslog-alertas-resumo...")

    await client.query("""
USE the mcp__slack__channels_list tool to list all channels.
Look specifically for a channel named 'cslog-alertas-resumo'.
If you find it, tell me the channel ID and name.
""")

    response_text = ""
    async for message in client.receive_response():
        if hasattr(message, 'content'):
            for block in message.content:
                if hasattr(block, 'text'):
                    print(block.text)

    print("\n📤 Now trying to post to #cslog-alertas-resumo...")

    await client.query("""
USE the mcp__slack__conversations_add_message tool to send a test message.

Post this message to the channel 'cslog-alertas-resumo':
"🤖 Teste do Monitor de Slack - Mensagem de teste automática"

If you get an error, please show me the EXACT error message.
""")

    response_text = ""
    async for message in client.receive_response():
        if hasattr(message, 'content'):
            for block in message.content:
                if hasattr(block, 'text'):
                    response_text += block.text
                    print(block.text)

    await client.disconnect()
    print("\n" + "="*80)
    print("Full response:")
    print(response_text)
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_post())
