#!/usr/bin/env python3
"""
Test Claude SDK without Slack - just to verify SDK setup works
"""

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def test_basic_sdk():
    """Test basic SDK functionality without MCP servers"""

    print("Testing Claude SDK Client (no Slack required)...\n")

    options = ClaudeAgentOptions(
        allowed_tools=["Bash"],
        permission_mode="bypassPermissions"
    )

    print("Sending test query to Claude...\n")

    async for message in query(
        prompt="What is 2+2? Just give me the number.",
        options=options
    ):
        print(f"Response: {message}")

    print("\n✅ SDK is working!")

if __name__ == "__main__":
    asyncio.run(test_basic_sdk())
