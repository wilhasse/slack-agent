# Setting Up Slack MCP in Claude Code

This guide shows you how to add the Slack MCP server directly to Claude Code, so you can talk to Slack in any conversation!

## 🎯 What This Does

Instead of running Python scripts, you'll be able to ask Claude directly in any conversation:
- "List my Slack channels"
- "Show channels starting with cslog-alertas"
- "Get recent messages from #cslog-alertas-prod"
- "Search for 'erro' in the last hour"

## 📋 Prerequisites

1. ✅ Slack MCP server binary built
2. ✅ Slack tokens (XOXC and XOXD)

## 🚀 Setup Steps

### Option 1: Automatic Setup (Recommended)

```bash
# 1. Set your Slack tokens
export SLACK_MCP_XOXC_TOKEN='xoxc-your-token-here'
export SLACK_MCP_XOXD_TOKEN='xoxd-your-token-here'

# 2. Run setup script
./setup_claude_code_mcp.sh

# 3. Restart Claude Code
# Exit and start again

# 4. Test it
# Run: /mcp
# You should see: slack
```

### Option 2: Manual Setup

1. **Edit `~/.claude/settings.json`:**

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "alwaysThinkingEnabled": true,
  "mcpServers": {
    "slack": {
      "command": "/home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "SLACK_MCP_XOXC_TOKEN": "xoxc-your-actual-token-here",
        "SLACK_MCP_XOXD_TOKEN": "xoxd-your-actual-token-here"
      }
    }
  }
}
```

2. **Restart Claude Code** (exit and start again)

3. **Test it:** Run `/mcp`

## ✅ Verification

After restarting Claude Code, run:
```
/mcp
```

You should see:
```
MCP Servers:
  slack
    - mcp__slack__channels_list
    - mcp__slack__conversations_history
    - mcp__slack__conversations_replies
    - mcp__slack__conversations_search_messages
```

## 🎮 Usage Examples

Once configured, you can ask Claude directly:

### List All Channels
```
List all my Slack channels
```

### Find Specific Channels
```
Show me channels that start with cslog-alertas
```

### Get Recent Messages
```
Get the last 10 messages from #cslog-alertas-prod
```

### Search Messages
```
Search for messages containing "erro" in cslog-alertas channels from the last 24 hours
```

### Analyze Important Messages
```
Check cslog-alertas-prod for critical messages in the last hour.
Classify them by importance.
```

## 🔧 How It Works

```
Your Question in Claude Code
           ↓
   Claude Code + Slack MCP
           ↓
   ├─→ Slack MCP Server (Go binary)
   │   └─→ Your Slack Workspace
   │
   └─→ Claude AI
       └─→ Analyzes & Returns Results
```

## 🔍 Troubleshooting

### /mcp shows "No MCP servers configured"

**Possible causes:**
1. Claude Code not restarted after config change
2. settings.json has syntax errors
3. Tokens not set correctly

**Solution:**
```bash
# Check settings.json is valid
cat ~/.claude/settings.json | python3 -m json.tool

# Restart Claude Code completely
# Then run: /mcp
```

### MCP server shows but tools don't work

**Possible causes:**
1. Tokens expired (logged out of Slack)
2. Binary path incorrect
3. Binary not executable

**Solution:**
```bash
# Test binary directly
/home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server --help

# Check it's executable
ls -lh /home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server

# Refresh tokens (get new ones from Slack browser cookies)
```

### "Permission denied" errors

**Solution:**
```bash
chmod +x /home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server
```

## 🔄 Updating Tokens

If your Slack tokens expire:

### Automatic Method:
```bash
# Set new tokens
export SLACK_MCP_XOXC_TOKEN='xoxc-new-token'
export SLACK_MCP_XOXD_TOKEN='xoxd-new-token'

# Re-run setup
./setup_claude_code_mcp.sh

# Restart Claude Code
```

### Manual Method:
1. Edit `~/.claude/settings.json`
2. Update the token values in the `env` section
3. Restart Claude Code

## 🆚 Comparison: Python Scripts vs Claude Code MCP

| Feature | Python Scripts | Claude Code MCP |
|---------|---------------|-----------------|
| **Setup** | Run scripts manually | One-time config |
| **Usage** | `python slack_chat.py` | Ask Claude directly |
| **Convenience** | Separate terminal | In conversation |
| **Context** | Isolated | Part of main conversation |
| **Best for** | Automation, monitoring | Interactive exploration |

## 💡 Use Both!

You can use both approaches:
- **Claude Code MCP**: For interactive Slack exploration
- **Python Scripts**: For automated monitoring with config.yaml

## 📚 Related Files

- `setup_claude_code_mcp.sh` - Automatic setup script
- `~/.claude/settings.json` - Claude Code configuration
- `slack-mcp-server/slack-mcp-server` - MCP server binary

## 🎯 Next Steps After Setup

1. **Explore your workspace:**
   ```
   List all my Slack channels
   ```

2. **Find alert channels:**
   ```
   Show me channels starting with cslog-alertas
   ```

3. **Check for issues:**
   ```
   Search for "erro" in cslog-alertas channels from today
   ```

4. **Set up monitoring:**
   Use the Python scripts for continuous monitoring:
   ```bash
   python slack_monitor_yaml.py
   ```

## 🔐 Security Notes

- Tokens are stored in `~/.claude/settings.json` (local file)
- Only accessible by your user account
- Tokens are session-based (expire when you log out of Slack)
- MCP server runs locally on your machine

## 📞 Quick Commands

```bash
# Setup
./setup_claude_code_mcp.sh

# Check config
cat ~/.claude/settings.json

# Test binary
./slack-mcp-server/slack-mcp-server --help

# Backup settings
cp ~/.claude/settings.json ~/.claude/settings.json.backup

# Restore backup
cp ~/.claude/settings.json.backup ~/.claude/settings.json
```

---

**After setup, restart Claude Code and try:**
```
/mcp
```

Then ask: **"List my Slack channels"** 🚀
