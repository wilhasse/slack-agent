# Slack Monitor - Final Setup Guide

## ✅ Everything is Ready!

All components are installed and configured correctly.

## 🚀 Quick Start

### Interactive Chat (Talk to Your Slack)

```bash
# Option 1: Use the helper script
./test_connection.sh

# Option 2: Manual
source venv/bin/activate
python slack_chat.py
```

### Example Commands to Try:

```
List all my channels
Show me channels that start with cslog-alertas
Get recent messages from #cslog-alertas-prod
Search for messages with 'erro' in the last 24 hours
exit
```

## 📋 What's Installed

| Component | Status | Details |
|-----------|--------|---------|
| Python | ✅ 3.11.2 | Virtual environment active |
| Node.js | ✅ v18.19.0 | For npm/npx |
| Go | ✅ 1.24.5 | For building MCP server |
| Claude Code CLI | ✅ 2.0.8 | SDK backend |
| Claude Agent SDK | ✅ Installed | Python package |
| Slack Tokens | ✅ Set | XOXC and XOXD configured |
| Slack MCP Server | ✅ Built | Go binary (20.5MB) |

## 📁 Key Files

### Main Scripts:
- **`slack_chat.py`** - Interactive chat with Slack (UPDATED ✨)
- **`slack_monitor.py`** - Automated monitoring
- **`slack_monitor_yaml.py`** - Monitoring with config.yaml
- **`test_connection.sh`** - Quick test script

### Configuration:
- **`config.yaml`** - Main configuration
  - Channels: `cslog-alertas*`
  - Keywords: Portuguese (urgente, crítico, erro, etc.)
  - Check interval: 10 seconds

### Utilities:
- **`diagnose.py`** - System diagnostic (9/9 checks pass!)
- **`test_slack_tools.py`** - Test individual MCP tools

### MCP Server:
- **`slack-mcp-server/slack-mcp-server`** - Compiled Go binary

## 🔧 How It Works

```
Your Question
    ↓
slack_chat.py (Python)
    ↓
Claude SDK Client
    ↓
    ├─→ Slack MCP Server (Go binary)
    │   └─→ Slack API (via browser tokens)
    │
    └─→ Claude AI (Sonnet 4.5)
        └─→ Analyzes messages & returns insights
```

## 💬 Interactive Chat Examples

### List All Channels
```
You: List all my channels
Claude: [uses channels_list tool]
        Found 47 channels:
        - #general
        - #cslog-alertas-prod
        - #cslog-alertas-dev
        ...
```

### Find Specific Channels
```
You: Show channels starting with cslog-alertas
Claude: [uses channels_list tool]
        Found 3 channels:
        1. #cslog-alertas-prod
        2. #cslog-alertas-dev
        3. #cslog-alertas-test
```

### Get Recent Messages
```
You: Get recent messages from #cslog-alertas-prod
Claude: [uses conversations_history tool]
        Latest messages:

        @joao (2 min ago): "Deploy completed"
        @maria (15 min ago): "⚠️ ERROR: API timeout"
        @bot (1 hour ago): "Build #1234 failed"
```

### Search Messages
```
You: Search for "erro" in last 24 hours
Claude: [uses search_messages tool]
        Found 5 messages with "erro":

        CRÍTICO - #cslog-alertas-prod
        @maria: "⚠️ ERRO: Timeout na API"
```

## 🤖 Automated Monitoring

### Using config.yaml (Portuguese keywords)

```bash
source venv/bin/activate

# Check once
python slack_monitor_yaml.py --once

# Monitor continuously
python slack_monitor_yaml.py
```

The monitor will:
1. Check channels matching `cslog-alertas*`
2. Look for Portuguese keywords (urgente, crítico, erro, etc.)
3. Use Claude to classify messages (CRÍTICO, IMPORTANTE, NORMAL, IGNORAR)
4. Show analysis every 10 seconds (configurable in config.yaml)

### Using Python script directly

```python
from slack_monitor import SlackMonitor

monitor = SlackMonitor(
    channels_to_monitor=["cslog-alertas-prod", "cslog-alertas-dev"],
    keywords=["erro", "falha", "crítico"],
    check_interval=60  # 1 minute
)

await monitor.check_once()
```

## 🔍 What Changed

### Original Issue:
```python
# OLD (didn't work)
slack_mcp_config = {
    "command": "npx",
    "args": ["-y", "@korotovsky/slack-mcp-server"]  # ❌ Doesn't exist
}
```

### Fixed:
```python
# NEW (works!)
slack_mcp_config = {
    "command": "/path/to/slack-mcp-server/slack-mcp-server",  # ✅ Compiled Go binary
    "args": ["--transport", "stdio"]
}
```

The Slack MCP server is a **Go application**, not an npm package!

## 🛠️ Troubleshooting

### Check System Status
```bash
python diagnose.py
```
Should show: **Passed: 9/9**

### Test MCP Server Directly
```bash
./slack-mcp-server/slack-mcp-server --help
```

### Refresh Slack Tokens
If tokens expire (when you log out of Slack):
1. Open Slack in browser
2. F12 → Application → Cookies → https://app.slack.com
3. Copy `d` → SLACK_MCP_XOXD_TOKEN
4. Copy `d-s` → SLACK_MCP_XOXC_TOKEN
5. Export them again

### Debug Mode
```bash
export SLACK_DEBUG="--debug"
python slack_chat.py
```

## 📚 Documentation Files

- **`QUICKSTART.md`** - Getting started guide
- **`README.md`** - English documentation
- **`README_PT.md`** - Portuguese documentation
- **`HOW_IT_WORKS.md`** - Detailed architecture explanation
- **`SETUP_COMPLETE.md`** - Installation summary
- **`README_FINAL.md`** - This file (final guide)

## 🎯 Common Use Cases

### 1. Explore Your Slack Workspace
```bash
./test_connection.sh
# Then: "List all my channels"
```

### 2. Monitor Production Alerts
```bash
python slack_monitor_yaml.py
# Configured in config.yaml for cslog-alertas* channels
```

### 3. Search for Issues
```bash
./test_connection.sh
# Then: "Search for 'erro' in cslog-alertas-prod from last hour"
```

### 4. Get Message History
```bash
./test_connection.sh
# Then: "Show me the last 10 messages from #cslog-alertas-prod"
```

## 🔐 Security Notes

- Browser tokens (xoxc/xoxd) are session-based
- They expire when you log out of Slack
- Messages are sent to Claude API for analysis
- The MCP server runs locally on your machine
- No data is stored unless using advanced mode with SQLite

## ✨ Next Steps

### Start Using:
```bash
# Interactive exploration
./test_connection.sh

# Automated monitoring
python slack_monitor_yaml.py
```

### Customize:
1. Edit `config.yaml` to add more channels/keywords
2. Adjust check interval (currently 10 seconds)
3. Add custom importance rules in Portuguese

### Extend:
- Add desktop notifications (already coded in advanced_example.py)
- Store messages in SQLite database
- Create custom filtering logic
- Monitor multiple workspaces

## 📞 Quick Commands Reference

```bash
# Diagnostic
python diagnose.py

# Interactive chat
./test_connection.sh
python slack_chat.py

# Test tools
python test_slack_tools.py

# Monitor once (test)
python slack_monitor_yaml.py --once

# Monitor continuously
python slack_monitor_yaml.py

# Advanced with notifications
python advanced_example.py
```

---

## 🎉 You're All Set!

Everything is configured and ready to use.

**Start with:**
```bash
./test_connection.sh
```

Then ask: **"Show me channels starting with cslog-alertas"**

Enjoy your AI-powered Slack monitoring! 🚀
