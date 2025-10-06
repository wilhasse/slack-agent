# Slack OAuth Token Setup

## ✅ OAuth Token Configured!

You're now using a **Slack Bot OAuth token** instead of browser tokens. This is better because:

- ✅ **Doesn't expire** when you log out of Slack
- ✅ **More secure** - designed for programmatic access
- ✅ **Specific permissions** - you control what the bot can access
- ✅ **Proper API usage** - official Slack API method

## 🎯 What You Have

**Token Type:** Bot Token (xoxb-)
**Token:** `xoxb-YOUR-SLACK-BOT-TOKEN-HERE`

## 🚀 How to Use

### In Claude Code (Main Usage)

1. **Restart Claude Code** (completely exit and restart)
2. Run: `/mcp`
3. You should see: `slack` server with tools
4. Ask directly:
   ```
   List my Slack channels
   Show channels starting with cslog-alertas
   Get recent messages from #cslog-alertas-prod
   ```

### In Python Scripts

```bash
# Option 1: Test with OAuth
./test_with_oauth.sh

# Option 2: Use in your scripts
source .env.oauth
source venv/bin/activate
python slack_chat.py
```

## 📋 Configuration Files

### Claude Code: `~/.claude/settings.local.json`
```json
{
  "mcpServers": {
    "slack": {
      "command": "/path/to/slack-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_MCP_XOXP_TOKEN": "xoxb-..."
      }
    }
  }
}
```

### Python Scripts: `.env.oauth`
```bash
SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN-HERE
SLACK_MCP_XOXP_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN-HERE
```

## 🔑 Bot Permissions

Make sure your Slack app has these OAuth scopes:
- `channels:read` - List public channels
- `channels:history` - Read messages from public channels
- `groups:read` - List private channels (if needed)
- `groups:history` - Read private channel messages (if needed)
- `im:read` - Read DMs (if needed)
- `im:history` - Read DM history (if needed)
- `mpim:read` - Read group DMs (if needed)
- `mpim:history` - Read group DM history (if needed)

To add permissions:
1. Go to: https://api.slack.com/apps
2. Select your app
3. Go to: **OAuth & Permissions**
4. Scroll to: **Scopes** → **Bot Token Scopes**
5. Add the scopes you need
6. **Reinstall the app** to your workspace

## 🔄 Comparison: OAuth vs Browser Tokens

| Feature | OAuth Token (xoxb-) | Browser Tokens (xoxc-/xoxd-) |
|---------|---------------------|------------------------------|
| **Expires** | No | Yes (on logout) |
| **Setup** | Create Slack app | Copy browser cookies |
| **Permissions** | Configurable scopes | Full user access |
| **Security** | Better | Less secure |
| **Recommended** | ✅ Yes | ❌ No (unless OAuth not possible) |

## 🧪 Testing

### Quick Test
```bash
./test_with_oauth.sh
```

### Test in Claude Code
After restarting Claude Code:
```
/mcp
```

Should show:
```
MCP Servers:
  slack
    - mcp__slack__channels_list
    - mcp__slack__conversations_history
    - mcp__slack__conversations_replies
    - mcp__slack__conversations_search_messages
```

Then ask:
```
List my Slack channels
```

## 🐛 Troubleshooting

### "No MCP servers configured"
- Make sure you **completely restarted** Claude Code (exit and start again)
- Check `~/.claude/settings.local.json` has the config
- Verify binary path is correct

### "Permission denied" or missing channels
- Check your bot has the right OAuth scopes
- Reinstall the app to workspace after adding scopes
- Make sure bot is added to the channels you want to read

### "Invalid authentication"
- Token might be revoked
- Generate a new token from: https://api.slack.com/apps → Your App → OAuth & Permissions

## 📚 Managing Your Slack App

**Your App Dashboard:**
https://api.slack.com/apps

**Useful sections:**
- **OAuth & Permissions** - Manage token and scopes
- **Event Subscriptions** - Set up webhooks (optional)
- **Install App** - Reinstall after scope changes

## 🎉 Next Steps

1. **Restart Claude Code now**
2. Run `/mcp` to verify
3. Try: `"List my Slack channels"`
4. Set up monitoring:
   ```bash
   source .env.oauth
   python slack_monitor_yaml.py
   ```

Your Slack integration is ready! 🚀
