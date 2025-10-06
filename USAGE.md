# Slack Monitor - Complete Usage Guide

## 🎯 Two Ways to Use

### 1. Claude Code (Interactive)
Talk to Slack directly in Claude Code conversations.

### 2. Python Scripts (Automated & Interactive)
Run monitoring scripts or interactive chat from terminal.

---

## 🔑 Token Setup

You have **OAuth token** configured (recommended):
```
xoxb-YOUR-SLACK-BOT-TOKEN-HERE
```

### Loading OAuth Token

```bash
# Load from .env.oauth file
source .env.oauth

# Or set manually
export SLACK_BOT_TOKEN='xoxb-YOUR-SLACK-BOT-TOKEN-HERE'
```

---

## 📋 Usage Options

### Option 1: Claude Code (After Restart)

**Setup:**
1. ✅ Already configured in `~/.claude/settings.local.json`
2. **Restart Claude Code** completely
3. Run: `/mcp`

**Usage:**
```
List my Slack channels
Show channels starting with cslog-alertas
Get recent messages from #cslog-alertas-prod
Search for "erro" in last 24 hours
```

---

### Option 2: Interactive Chat (Python)

**Quick Start:**
```bash
./run_with_oauth.sh
```

Or manually:
```bash
source .env.oauth
source venv/bin/activate
python slack_chat.py
```

**Example Commands:**
```
List all my channels
Show me channels that start with cslog-alertas
Get recent messages from #cslog-alertas-prod
Search for messages with 'erro' in the last hour
exit
```

---

### Option 3: Automated Monitor (YAML Config)

**Check once:**
```bash
./run_with_oauth.sh slack_monitor_yaml.py --once
```

**Monitor continuously:**
```bash
./run_with_oauth.sh slack_monitor_yaml.py
```

**Configuration:** Edit `config.yaml`
- Channels: `cslog-alertas*`
- Keywords: Portuguese (urgente, crítico, erro, etc.)
- Interval: 10 seconds

---

### Option 4: Direct Python Script

**Basic monitor:**
```bash
source .env.oauth
source venv/bin/activate
python slack_monitor.py
```

**Advanced monitor (with notifications & database):**
```bash
source .env.oauth
source venv/bin/activate
python advanced_example.py
```

---

## 🛠️ All Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `slack_chat.py` | Interactive chat | `./run_with_oauth.sh` |
| `slack_monitor.py` | Basic monitoring | `./run_with_oauth.sh slack_monitor.py` |
| `slack_monitor_yaml.py` | Monitor with config.yaml | `./run_with_oauth.sh slack_monitor_yaml.py` |
| `advanced_example.py` | Notifications + DB | `./run_with_oauth.sh advanced_example.py` |
| `test_slack_tools.py` | Test MCP tools | `./run_with_oauth.sh test_slack_tools.py` |
| `diagnose.py` | System check | `python diagnose.py` |

---

## 📁 Quick Commands Cheatsheet

### Interactive Exploration
```bash
# Start chat
./run_with_oauth.sh

# Test connection
./run_with_oauth.sh test_slack_tools.py

# System check
python diagnose.py
```

### Monitoring
```bash
# One-time check
./run_with_oauth.sh slack_monitor_yaml.py --once

# Continuous monitoring
./run_with_oauth.sh slack_monitor_yaml.py

# Advanced (notifications)
./run_with_oauth.sh advanced_example.py
```

### Configuration
```bash
# Edit channels & keywords
nano config.yaml

# View current config
python config_loader.py

# Update Claude Code MCP
./setup_oauth_token.sh xoxb-your-token
```

---

## 🔄 What Changed

All Python scripts now:
1. ✅ **Check for OAuth token first** (`SLACK_BOT_TOKEN`)
2. ✅ **Fall back to browser tokens** if OAuth not available
3. ✅ **Use compiled binary** instead of npx
4. ✅ **Support .env.oauth** file

### Before:
```python
# Only browser tokens
env: {
    "SLACK_MCP_XOXC_TOKEN": "...",
    "SLACK_MCP_XOXD_TOKEN": "..."
}
```

### Now:
```python
# OAuth preferred, browser tokens as fallback
if oauth_token:
    env: {
        "SLACK_BOT_TOKEN": oauth_token,
        "SLACK_MCP_XOXP_TOKEN": oauth_token
    }
else:
    env: {
        "SLACK_MCP_XOXC_TOKEN": "...",
        "SLACK_MCP_XOXD_TOKEN": "..."
    }
```

---

## 🎯 Common Workflows

### Explore Your Workspace
```bash
./run_with_oauth.sh
# Then: "List all my channels"
```

### Monitor Production Alerts
```bash
# Edit config.yaml to set channels
# Then run:
./run_with_oauth.sh slack_monitor_yaml.py
```

### Search for Issues
```bash
./run_with_oauth.sh
# Then: "Search for 'erro' in cslog-alertas-prod from last hour"
```

### Get Notifications
```bash
./run_with_oauth.sh advanced_example.py
# Desktop notifications for critical messages
```

---

## 🐛 Troubleshooting

### "No OAuth token found"
```bash
source .env.oauth
./run_with_oauth.sh
```

### "Slack MCP server binary not found"
```bash
cd slack-mcp-server
go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server
```

### "Permission denied"
```bash
# Check bot has required scopes in Slack app:
# - channels:read
# - channels:history
```

### Claude Code: "No MCP servers configured"
```bash
# Make sure you completely restarted Claude Code
# Then check:
cat ~/.claude/settings.local.json | grep slack
```

---

## 📚 Documentation Files

- `USAGE.md` - This file (complete usage guide)
- `OAUTH_SETUP.md` - OAuth token setup
- `README_FINAL.md` - Final setup summary
- `README_PT.md` - Portuguese documentation
- `HOW_IT_WORKS.md` - Architecture explanation
- `CLAUDE_CODE_MCP_SETUP.md` - Claude Code integration

---

## 🎉 Quick Start Summary

**For Claude Code:**
1. Restart Claude Code
2. Run: `/mcp`
3. Ask: "List my Slack channels"

**For Python Scripts:**
```bash
./run_with_oauth.sh
```

That's it! 🚀
