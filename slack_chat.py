#!/usr/bin/env python3
"""
Interactive Slack Chat - With OAuth token support
Supports both OAuth tokens (xoxb-) and browser tokens (xoxc-/xoxd-)
"""

import asyncio
import os
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock
)

try:
    from dotenv import load_dotenv
    # Try to load .env.oauth first, then .env
    if Path(".env.oauth").exists():
        load_dotenv(".env.oauth")
    load_dotenv()
except ImportError:
    pass


class SlackChat:
    """Interactive chat session with Claude about Slack"""

    def __init__(self):
        # Find the Slack MCP server binary
        mcp_binary = Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server"

        if not mcp_binary.exists():
            print("❌ Slack MCP server binary not found!")
            print(f"   Expected at: {mcp_binary}")
            print()
            print("Please run: cd slack-mcp-server && go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server")
            raise FileNotFoundError("Slack MCP server not installed")

        # Check for OAuth token first (preferred), then fall back to browser tokens
        oauth_token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_MCP_XOXP_TOKEN")
        xoxc_token = os.getenv("SLACK_MCP_XOXC_TOKEN", "")
        xoxd_token = os.getenv("SLACK_MCP_XOXD_TOKEN", "")

        # Configure Slack MCP server
        if oauth_token:
            # Use OAuth token (preferred)
            print(f"🔑 Using OAuth token: {oauth_token[:20]}...{oauth_token[-10:]}")
            slack_mcp_config = {
                "type": "stdio",
                "command": str(mcp_binary),
                "args": ["--transport", "stdio"],
                "env": {
                    "SLACK_BOT_TOKEN": oauth_token,
                    "SLACK_MCP_XOXP_TOKEN": oauth_token,
                }
            }
        elif xoxc_token and xoxd_token:
            # Fall back to browser tokens
            print("🔑 Using browser tokens (xoxc/xoxd)")
            slack_mcp_config = {
                "type": "stdio",
                "command": str(mcp_binary),
                "args": ["--transport", "stdio"],
                "env": {
                    "SLACK_MCP_XOXC_TOKEN": xoxc_token,
                    "SLACK_MCP_XOXD_TOKEN": xoxd_token,
                }
            }
        else:
            print("❌ No Slack tokens found!")
            print()
            print("Option 1 (Recommended): OAuth token")
            print("  source .env.oauth")
            print("  # or")
            print("  export SLACK_BOT_TOKEN='xoxb-...'")
            print()
            print("Option 2: Browser tokens")
            print("  export SLACK_MCP_XOXC_TOKEN='xoxc-...'")
            print("  export SLACK_MCP_XOXD_TOKEN='xoxd-...'")
            raise ValueError("No Slack tokens configured")

        # Set up Claude options with Slack MCP server
        self.options = ClaudeAgentOptions(
            mcp_servers={"slack": slack_mcp_config},
            allowed_tools=[
                "mcp__slack__channels_list",
                "mcp__slack__conversations_history",
                "mcp__slack__conversations_replies",
                "mcp__slack__conversations_search_messages",
            ],
            system_prompt="""You are a helpful assistant with access to Slack via MCP tools.

You have access to these Slack tools:
- mcp__slack__channels_list: List all Slack channels
- mcp__slack__conversations_history: Get message history from a channel
- mcp__slack__conversations_replies: Get replies in a thread
- mcp__slack__conversations_search_messages: Search for messages

IMPORTANT: When the user asks about Slack channels or messages, USE THESE TOOLS to fetch the actual data.

For example:
- User: "Show me my channels" → Use channels_list tool
- User: "What are the latest messages in #alerts?" → Use conversations_history tool
- User: "Search for messages with 'error'" → Use conversations_search_messages tool

Always use the tools to get real data from Slack, don't just say you can't access it.

When analyzing messages, classify them as:
- CRÍTICO (CRITICAL): Needs immediate attention
- IMPORTANTE (IMPORTANT): Should be reviewed soon
- NORMAL: Can be reviewed later
- IGNORAR (IGNORE): Not relevant

Be concise and helpful.""",
            permission_mode="bypassPermissions",
            stderr=lambda msg: print(f"[DEBUG] {msg}") if "--debug" in os.environ.get("SLACK_DEBUG", "") else None
        )

        self.client = None
        self.turn_count = 0

    async def start(self):
        """Start interactive chat session"""

        print("🔌 Connecting to Slack via Claude SDK...")
        self.client = ClaudeSDKClient(options=self.options)
        await self.client.connect()

        print("✅ Connected!")
        print()
        print("=" * 70)
        print("💬 Slack Interactive Chat")
        print("=" * 70)
        print()
        print("You can now talk to Claude about your Slack channels!")
        print()
        print("Try:")
        print('  - "List all my channels"')
        print('  - "Show me channels that start with cslog-alertas"')
        print('  - "Get recent messages from #cslog-alertas-prod"')
        print('  - "Search for messages with \'erro\' in the last 24 hours"')
        print()
        print("Commands: 'exit' to quit, 'clear' for new session")
        print("=" * 70)
        print()

        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input(f"\n[{self.turn_count + 1}] 💬 You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("\n👋 Até logo!")
                    break

                if user_input.lower() == 'clear':
                    # Start new session
                    await self.client.disconnect()
                    await self.client.connect()
                    self.turn_count = 0
                    print("\n✨ Nova sessão iniciada!")
                    continue

                # Send query to Claude
                await self.client.query(user_input)
                self.turn_count += 1

                # Print response
                print(f"\n[{self.turn_count}] 🤖 Claude: ", end="", flush=True)

                response_text = ""
                tool_calls = []

                async for message in self.client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                print(block.text, end="", flush=True)
                                response_text += block.text
                            elif isinstance(block, ToolUseBlock):
                                # Show when tools are being used
                                tool_calls.append(block.name)
                                print(f"\n   [🔧 Using tool: {block.name}]", flush=True)

                if tool_calls:
                    print(f"\n   [✅ Used {len(tool_calls)} tool(s)]", end="")

                print()  # New line after response

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Type 'exit' to quit or continue chatting.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Cleanup
        await self.client.disconnect()
        print("\n✅ Disconnected from Slack")


async def main():
    """Main entry point"""
    try:
        chat = SlackChat()
        await chat.start()
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}")
        return
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
