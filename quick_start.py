#!/usr/bin/env python3
"""
Quick start script for Slack Monitor
Tests the connection and does a one-time message check
"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from slack_monitor import SlackMonitor
except ImportError:
    print("❌ Error: claude-agent-sdk not installed")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("💡 Tip: Install python-dotenv to load .env files automatically")
    print("   pip install python-dotenv")


async def test_connection():
    """Test connection to Slack MCP server"""

    print("🔧 Slack Monitor - Quick Start Test")
    print("=" * 60)

    # Check for required environment variables
    xoxc_token = os.getenv("SLACK_MCP_XOXC_TOKEN")
    xoxd_token = os.getenv("SLACK_MCP_XOXD_TOKEN")

    if not xoxc_token or not xoxd_token:
        print("❌ Missing Slack tokens!")
        print()
        print("Please set the following environment variables:")
        print("  SLACK_MCP_XOXC_TOKEN")
        print("  SLACK_MCP_XOXD_TOKEN")
        print()
        print("To get these tokens:")
        print("1. Open Slack in your browser")
        print("2. Press F12 to open Developer Tools")
        print("3. Go to: Application → Cookies → https://app.slack.com")
        print("4. Find 'd' cookie → copy as SLACK_MCP_XOXD_TOKEN")
        print("5. Find 'd-s' cookie → copy as SLACK_MCP_XOXC_TOKEN")
        print()
        print("Then set them:")
        print("  export SLACK_MCP_XOXC_TOKEN='xoxc-...'")
        print("  export SLACK_MCP_XOXD_TOKEN='xoxd-...'")
        print()
        print("Or create a .env file (see .env.example)")
        return False

    print("✅ Slack tokens found")
    print()

    # Test basic configuration
    print("📋 Configuration:")
    print(f"   Check interval: 5 minutes")
    print(f"   Keywords: urgent, critical, emergency, help, alert")
    print(f"   Channels: All (using keyword search)")
    print()

    # Create monitor
    monitor = SlackMonitor(
        keywords=[
            "urgent", "critical", "emergency", "help", "alert",
            "incident", "down", "error", "failed"
        ],
        check_interval=300
    )

    print("🔌 Connecting to Slack via MCP server...")
    print("   (This may take a few seconds)")
    print()

    try:
        await monitor.connect()

        print("✅ Connection successful!")
        print()
        print("🔍 Checking for recent important messages...")
        print()

        # Do a one-time check
        await monitor.check_messages()

        print()
        print("✅ Test completed successfully!")
        print()
        print("Next steps:")
        print("  1. Customize channels in config_example.py")
        print("  2. Add your own keywords")
        print("  3. Run the full monitor:")
        print()
        print("     python slack_monitor.py")
        print()

        await monitor.disconnect()
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check your tokens are valid and not expired")
        print("  2. Ensure you're still logged into Slack in your browser")
        print("  3. Try logging out and back into Slack, then get new tokens")
        print("  4. Check if claude-code CLI is installed: npm install -g @anthropic-ai/claude-code")
        print()
        return False


async def interactive_setup():
    """Interactive setup wizard"""

    print()
    print("🚀 Slack Monitor Setup Wizard")
    print("=" * 60)
    print()

    # Check if .env exists
    env_file = Path(__file__).parent / ".env"

    if env_file.exists():
        print("✅ Found existing .env file")
        print()
        response = input("Do you want to test the connection? [Y/n]: ").strip().lower()
        if response in ["", "y", "yes"]:
            await test_connection()
        return

    print("No .env file found. Let's create one!")
    print()
    print("First, get your Slack tokens:")
    print("1. Open Slack in your browser: https://app.slack.com")
    print("2. Press F12 to open Developer Tools")
    print("3. Go to: Application → Cookies → https://app.slack.com")
    print("4. Copy the token values")
    print()

    xoxd = input("Enter SLACK_MCP_XOXD_TOKEN (the 'd' cookie): ").strip()
    xoxc = input("Enter SLACK_MCP_XOXC_TOKEN (the 'd-s' cookie): ").strip()

    if xoxd and xoxc:
        # Create .env file
        with open(env_file, "w") as f:
            f.write(f"# Slack MCP Server Tokens\n")
            f.write(f"SLACK_MCP_XOXD_TOKEN={xoxd}\n")
            f.write(f"SLACK_MCP_XOXC_TOKEN={xoxc}\n")

        print()
        print("✅ Created .env file")
        print()

        # Reload environment
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except:
            pass

        response = input("Test the connection now? [Y/n]: ").strip().lower()
        if response in ["", "y", "yes"]:
            await test_connection()
    else:
        print()
        print("❌ Invalid tokens. Setup cancelled.")
        print()


def main():
    """Main entry point"""

    # Check if running with --setup flag
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        asyncio.run(interactive_setup())
    else:
        asyncio.run(test_connection())


if __name__ == "__main__":
    main()
