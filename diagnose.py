#!/usr/bin/env python3
"""
Diagnostic script to check Slack Monitor setup
"""

import os
import sys
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_requirement(name, check_func, fix_hint):
    """Check a requirement and print status"""
    print(f"Checking {name}...", end=" ")
    try:
        result = check_func()
        if result:
            print(f"✅ OK")
            if isinstance(result, str):
                print(f"   → {result}")
            return True
        else:
            print(f"❌ FAIL")
            print(f"   Fix: {fix_hint}")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print(f"   Fix: {fix_hint}")
        return False


def check_python():
    """Check Python version"""
    version = sys.version.split()[0]
    if sys.version_info >= (3, 8):
        return f"Python {version}"
    return False


def check_venv():
    """Check if in virtual environment"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return "Virtual environment active"
    return False


def check_nodejs():
    """Check Node.js installation"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"Node.js {result.stdout.strip()}"
    except:
        pass
    return False


def check_npm():
    """Check npm installation"""
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"npm {result.stdout.strip()}"
    except:
        pass
    return False


def check_npx():
    """Check npx availability"""
    try:
        result = subprocess.run(['npx', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"npx {result.stdout.strip()}"
    except:
        pass
    return False


def check_claude_code():
    """Check Claude Code CLI"""
    try:
        result = subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"Claude Code {result.stdout.strip()}"
    except:
        pass
    return False


def check_claude_sdk():
    """Check Claude Agent SDK"""
    try:
        import claude_agent_sdk
        return f"claude-agent-sdk installed"
    except ImportError:
        return False


def check_slack_tokens():
    """Check Slack tokens"""
    xoxc = os.getenv('SLACK_MCP_XOXC_TOKEN')
    xoxd = os.getenv('SLACK_MCP_XOXD_TOKEN')

    if xoxc and xoxd:
        xoxc_preview = xoxc[:10] + "..." if len(xoxc) > 10 else xoxc
        xoxd_preview = xoxd[:10] + "..." if len(xoxd) > 10 else xoxd
        return f"XOXC: {xoxc_preview}, XOXD: {xoxd_preview}"
    elif xoxc:
        return False  # Missing XOXD
    elif xoxd:
        return False  # Missing XOXC
    else:
        return False  # Both missing


def check_slack_mcp_server():
    """Check if Slack MCP server binary exists"""
    binary_path = Path(__file__).parent / "slack-mcp-server" / "slack-mcp-server"

    if binary_path.exists() and binary_path.is_file():
        # Check if executable
        if os.access(binary_path, os.X_OK):
            # Try to run --help to verify it works
            try:
                result = subprocess.run(
                    [str(binary_path), '--help'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                size_mb = binary_path.stat().st_size / (1024 * 1024)
                return f"Slack MCP server binary ({size_mb:.1f}MB)"
            except:
                return "Binary exists but may have issues"
        else:
            return False  # Not executable
    else:
        return False  # Doesn't exist


def test_mcp_connection():
    """Test actual MCP connection"""
    print("\n" + "="*70)
    print("Testing MCP Connection...")
    print("="*70)

    try:
        import asyncio
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

        async def test():
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
                permission_mode="bypassPermissions",
                stderr=lambda msg: print(f"   [MCP stderr] {msg}")
            )

            print("Connecting to Claude SDK...")
            async with ClaudeSDKClient(options=options) as client:
                print("✅ Connected!")
                print("\nSending test query...")

                await client.query("List available MCP tools. What tools do you have access to?")

                print("Response:")
                async for message in client.receive_response():
                    print(f"   {message}")

                return True

        result = asyncio.run(test())
        return result

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all diagnostics"""

    print("\n" + "="*70)
    print("🔍 Slack Monitor Diagnostic Tool")
    print("="*70 + "\n")

    checks = [
        ("Python version (≥3.8)", check_python, "Install Python 3.8+"),
        ("Virtual environment", check_venv, "Run: source venv/bin/activate"),
        ("Node.js", check_nodejs, "Install Node.js: https://nodejs.org/"),
        ("npm", check_npm, "Install npm (comes with Node.js)"),
        ("npx", check_npx, "Install npx (comes with npm)"),
        ("Claude Code CLI", check_claude_code, "npm install -g @anthropic-ai/claude-code"),
        ("Claude Agent SDK", check_claude_sdk, "pip install claude-agent-sdk"),
        ("Slack tokens", check_slack_tokens, "Set SLACK_MCP_XOXC_TOKEN and SLACK_MCP_XOXD_TOKEN"),
        ("Slack MCP server binary", check_slack_mcp_server, "Run: cd slack-mcp-server && go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server"),
    ]

    results = []
    for name, check_func, fix_hint in checks:
        result = check_requirement(name, check_func, fix_hint)
        results.append((name, result))
        print()

    # Summary
    print("="*70)
    print("Summary")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✅ All checks passed! Your environment is ready.")
        print("\nWould you like to test the MCP connection? (y/n): ", end="")
        response = input().strip().lower()
        if response == 'y':
            test_mcp_connection()
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        print("\nMost common fixes:")
        print("  1. Activate venv: source venv/bin/activate")
        print("  2. Install Node.js: https://nodejs.org/")
        print("  3. Set Slack tokens:")
        print("     export SLACK_MCP_XOXC_TOKEN='xoxc-...'")
        print("     export SLACK_MCP_XOXD_TOKEN='xoxd-...'")

    print()


if __name__ == "__main__":
    main()
