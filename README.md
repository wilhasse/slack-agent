# Slack Alert Monitor

An intelligent Slack monitoring system that uses Claude AI to filter and prioritize messages that deserve your attention.

## 🎯 What This Does

Monitor your Slack workspace with AI-powered message analysis:
- **Automatically filters** important messages from noise
- **Classifies by priority**: CRITICAL, IMPORTANT, NORMAL, or IGNORE
- **Works in two modes**: Interactive chat or automated monitoring
- **Integrates with Claude Code**: Talk to Slack directly in conversations

## 🧠 NEW: Smart Monitor (Intelligent Alert Filtering)

**Avoid channel pollution!** The Smart Monitor adds intelligent filtering to only send truly urgent and recurrent alerts:

- 🎯 **Deduplication**: Never sends the same alert twice within configurable time window
- 🔍 **Pattern Detection**: Identifies recurring issues and alerts after threshold is met
- ⚡ **Urgency Filtering**: Only sends CRITICAL or IMPORTANT alerts (configurable)
- 📊 **Historical Analysis**: Compares with previous alerts to reduce noise
- 🤖 **Claude Decision**: AI-powered final decisions on borderline cases
- 📈 **Statistics**: Track filtering efficiency (typically 90%+ filter rate)

**Example**: 100 "API timeout" errors → Smart Monitor sends **1 alert** when it becomes recurrent, filters out the duplicates.

**Quick Start**:
```bash
cp smart_config_example.yaml smart_config.yaml
nano smart_config.yaml  # Configure your channels and thresholds
./run_smart_monitor.sh  # Run with intelligent filtering
```

📖 **[Read the Smart Monitor Guide →](docs/SMART_MONITOR.md)**

---

## ✨ Features

- 🤖 **AI-Powered Analysis**: Claude analyzes message content and context
- ⚡ **Real-time Monitoring**: Continuously checks channels at configurable intervals
- 🎯 **Priority Classification**: Automatically categorizes message importance
- 🔑 **Keyword Detection**: Matches urgent keywords in multiple languages
- 💬 **Channel Patterns**: Monitor channels with wildcards (e.g., `cslog-alertas*`)
- 🔌 **MCP Integration**: Uses Model Context Protocol for Slack access
- 🔐 **OAuth Support**: Works with Slack OAuth tokens (recommended) or browser tokens
- 🌍 **Multilingual**: Supports Portuguese and English keywords

## 🚀 Quick Start

### 1. Setup

```bash
# Run the setup script (creates venv, installs dependencies, builds MCP server)
./setup.sh

# Load OAuth token
source .env.oauth

# Run interactive chat
./run_with_oauth.sh
```

### 2. Try It Out

The chat will start. Try asking:
```
List all my channels
Show me channels that start with cslog-alertas
Get recent messages from #cslog-alertas-prod
Search for "erro" in the last hour
```

That's it! 🎉

---

## 📋 Installation (Detailed)

### Prerequisites

- Python 3.8+
- Node.js 16+ (for npm)
- Go 1.18+ (for building Slack MCP server)
- Claude Code CLI (optional, for Claude Code integration)

### Step-by-Step Setup

#### 1. Install Python Dependencies

```bash
# Create virtual environment and install packages
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Build Slack MCP Server

The Slack MCP server is a Go application that provides the connection to Slack:

```bash
# Clone and build (if not already done by setup.sh)
cd slack-mcp-server
go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server
cd ..
```

#### 3. Get Slack Credentials

**Option 1: OAuth Token (Recommended)**

Create a Slack App and get an OAuth token:

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "Slack Monitor")
4. Select your workspace
5. Go to **OAuth & Permissions**
6. Add these **Bot Token Scopes**:
   - `channels:read` - List public channels
   - `channels:history` - Read public channel messages
   - `groups:read` - List private channels (optional)
   - `groups:history` - Read private messages (optional)
7. Click "Install to Workspace"
8. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

Save it to `.env.oauth`:
```bash
echo "SLACK_BOT_TOKEN=xoxb-your-token-here" > .env.oauth
```

**Option 2: Browser Tokens (Alternative)**

If you can't create a Slack app:

1. Open Slack in browser: https://app.slack.com
2. Press F12 (Developer Tools)
3. Go to: Application → Cookies → `https://app.slack.com`
4. Copy two cookies:
   - `d` → `SLACK_MCP_XOXD_TOKEN`
   - `d-s` → `SLACK_MCP_XOXC_TOKEN`

```bash
export SLACK_MCP_XOXD_TOKEN='xoxd-...'
export SLACK_MCP_XOXC_TOKEN='xoxc-...'
```

⚠️ **Note**: Browser tokens expire when you log out of Slack.

#### 4. Verify Installation

```bash
# Run diagnostic
source venv/bin/activate
python diagnose.py
```

Should show: **Passed: 9/9** ✅

---

## 🎮 Usage

### Interactive Chat (Recommended)

Talk to Claude about your Slack workspace:

```bash
./run_with_oauth.sh
```

**Example conversation:**
```
You: List all my channels
Claude: [uses channels_list tool] Found 47 channels...

You: Show channels starting with cslog-alertas
Claude: Found 3 channels:
       1. cslog-alertas-prod
       2. cslog-alertas-dev
       3. cslog-alertas-test

You: Get recent messages from cslog-alertas-prod
Claude: [fetches messages] Latest messages:
       @user1: "Deploy completed successfully"
       @user2: "⚠️ ERROR: API timeout detected"
```

### Automated Monitoring

Monitor channels continuously with a YAML configuration:

```bash
# Check once
./run_with_oauth.sh slack_monitor_yaml.py --once

# Monitor continuously
./run_with_oauth.sh slack_monitor_yaml.py
```

**Configuration:** Edit `config.yaml`

```yaml
channels:
  - "cslog-alertas*"    # All channels starting with cslog-alertas
  - "prod-incidents"    # Specific channel

keywords:
  - "urgente"
  - "crítico"
  - "erro"
  - "falha"
  - "urgent"
  - "critical"
  - "error"

check_interval: 300  # Seconds (5 minutes)

advanced:
  notifications: true
  database: "slack_messages.db"
```

### Claude Code Integration

Use Slack MCP directly in Claude Code conversations:

**Setup:**
1. Configure OAuth token:
   ```bash
   ./setup_oauth_token.sh xoxb-your-token-here
   ```

2. **Restart Claude Code** completely

3. Verify:
   ```
   /mcp
   ```
   Should show: `slack` server with tools

**Usage in Claude Code:**
```
List my Slack channels
Show channels starting with cslog-alertas
Get recent messages from #alerts
Search for "error" in the last 24 hours
```

---

## 📁 Project Structure

```
slack_agent/
├── slack_chat.py              # Interactive Slack chat
├── slack_monitor.py           # Basic monitoring
├── slack_monitor_yaml.py      # Monitor with YAML config
├── advanced_example.py        # Advanced features (notifications, DB)
├── config.yaml                # Main configuration file
├── .env.oauth                 # OAuth token (gitignored)
├── run_with_oauth.sh          # Easy launcher script
├── setup.sh                   # Initial setup script
├── diagnose.py                # System diagnostic
├── slack-mcp-server/          # Go-based MCP server
│   └── slack-mcp-server       # Compiled binary
└── venv/                      # Python virtual environment
```

### Key Files

| File | Purpose |
|------|---------|
| `slack_chat.py` | Interactive chat interface |
| `config.yaml` | Main configuration (channels, keywords) |
| `.env.oauth` | OAuth token storage |
| `run_with_oauth.sh` | Quick launcher |
| `README.md` | This file |
| `USAGE.md` | Detailed usage guide |
| `OAUTH_SETUP.md` | OAuth setup instructions |

---

## ⚙️ Configuration

### config.yaml

```yaml
# Channels to monitor (supports wildcards)
channels:
  - "cslog-alertas*"
  - "incidents"
  - "prod-*"

# Keywords (Portuguese and English)
keywords:
  - "urgente"
  - "crítico"
  - "erro"
  - "urgent"
  - "critical"
  - "error"

# Check interval (seconds)
check_interval: 300

# Advanced features
advanced:
  notifications: true           # Desktop notifications
  database: "slack_messages.db" # Message persistence
  persist: true

# Custom importance rules
importance_rules: |
  Messages are CRITICAL if:
  1. From production channels
  2. Contain "down" or "offline"
  3. Affect customers

  Messages are IMPORTANT if:
  1. Deployment failures
  2. Code review requests
  3. Team announcements
```

### Environment Variables

```bash
# OAuth Token (recommended)
SLACK_BOT_TOKEN=xoxb-your-token-here

# Or Browser Tokens
SLACK_MCP_XOXC_TOKEN=xoxc-your-token-here
SLACK_MCP_XOXD_TOKEN=xoxd-your-token-here

# Optional
SLACK_DEBUG=--debug  # Enable debug output
```

---

## 🎯 Usage Examples

### Example 1: Monitor Production Alerts

```bash
# Edit config.yaml
channels:
  - "prod-alerts"
  - "incidents"
  - "on-call"

keywords:
  - "down"
  - "error"
  - "500"
  - "timeout"

check_interval: 60  # Check every minute

# Run monitor
./run_with_oauth.sh slack_monitor_yaml.py
```

### Example 2: Search for Issues

```bash
./run_with_oauth.sh

# Then ask:
Search for messages containing "database" in cslog-alertas-prod
from the last 2 hours
```

### Example 3: Get Channel History

```python
# custom_monitor.py
from slack_monitor import SlackMonitor
import asyncio

async def main():
    monitor = SlackMonitor(
        channels_to_monitor=["cslog-alertas-prod"],
        keywords=["erro", "falha", "crítico"],
        check_interval=120
    )

    await monitor.check_once()

asyncio.run(main())
```

### Example 4: Advanced with Notifications

```bash
# Uses desktop notifications and SQLite database
./run_with_oauth.sh advanced_example.py
```

---

## 🏗️ Architecture

```
┌─────────────────────────────┐
│   User Commands             │
│   - Interactive chat        │
│   - Automated monitor       │
│   - Claude Code queries     │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Python Scripts            │
│   - slack_chat.py           │
│   - slack_monitor_yaml.py   │
│   - Claude Agent SDK        │
└──────────┬──────────────────┘
           │
           ├──────────────────┐
           │                  │
           ▼                  ▼
┌──────────────────┐   ┌─────────────────┐
│ Slack MCP Server │   │  Claude AI      │
│ (Go binary)      │   │  (Sonnet 4.5)   │
│                  │   │                 │
│ Tools:           │   │  - Analyzes     │
│ - channels_list  │◄──┤  - Classifies   │
│ - conversations_ │   │  - Filters      │
│   history        │   │                 │
│ - search         │   │                 │
└────────┬─────────┘   └─────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   Slack Workspace           │
│   (via OAuth or Browser)    │
└─────────────────────────────┘
```

### How It Works

1. **You ask** (via chat or automated monitor)
2. **Claude SDK** sends request to Claude with Slack tools available
3. **Claude AI** decides which Slack tools to use
4. **MCP Server** executes tools and fetches data from Slack
5. **Claude AI** analyzes messages and classifies importance
6. **Results** returned to you (filtered and prioritized)

---

## 🔧 Troubleshooting

### Common Issues

#### "No OAuth token found"
```bash
# Make sure .env.oauth exists and is loaded
source .env.oauth
./run_with_oauth.sh
```

#### "Slack MCP server binary not found"
```bash
# Build the server
cd slack-mcp-server
go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server
```

#### "Permission denied" accessing channels
- Check your Slack app has the right OAuth scopes
- Go to: https://api.slack.com/apps → Your App → OAuth & Permissions
- Add scopes: `channels:read`, `channels:history`
- **Reinstall app** to workspace

#### Claude Code: "No MCP servers configured"
```bash
# Make sure you:
# 1. Ran setup: ./setup_oauth_token.sh xoxb-your-token
# 2. COMPLETELY restarted Claude Code
# 3. Verify config:
cat ~/.claude/settings.local.json | grep slack
```

#### "Invalid authentication"
- OAuth tokens may be revoked
- Generate new token from Slack app dashboard
- Browser tokens expire on logout - get new ones

### Diagnostic Commands

```bash
# Check system status
python diagnose.py

# Test MCP server
./slack-mcp-server/slack-mcp-server --help

# Test connection
./run_with_oauth.sh test_slack_tools.py

# Check configuration
python config_loader.py
```

---

## 📚 Documentation

- **README.md** - This file (general overview)
- **USAGE.md** - Detailed usage guide
- **OAUTH_SETUP.md** - OAuth token setup
- **README_PT.md** - Portuguese documentation
- **HOW_IT_WORKS.md** - Architecture deep dive
- **CLAUDE_CODE_MCP_SETUP.md** - Claude Code integration
- **SETUP_COMPLETE.md** - Installation summary

---

## 🆚 OAuth vs Browser Tokens

| Feature | OAuth Token (xoxb-) | Browser Tokens (xoxc-/xoxd-) |
|---------|---------------------|------------------------------|
| **Expires** | No (unless revoked) | Yes (on logout) |
| **Setup** | Create Slack app | Copy browser cookies |
| **Permissions** | Configurable scopes | Full user access |
| **Security** | ✅ Better | ⚠️ Less secure |
| **Stability** | ✅ Stable | ⚠️ Can break |
| **Recommended** | ✅ Yes | Only if OAuth not possible |

**Recommendation:** Always use OAuth tokens when possible.

---

## 🎨 Advanced Features

### Desktop Notifications

```bash
# Enable in config.yaml
advanced:
  notifications: true

# Run advanced monitor
./run_with_oauth.sh advanced_example.py
```

### Message Persistence

```bash
# Enable database in config.yaml
advanced:
  database: "slack_messages.db"
  persist: true

# View statistics
./run_with_oauth.sh cli.py --stats
```

### Custom Filtering

Edit `config.yaml`:
```yaml
importance_rules: |
  Custom rules for my team:
  1. Messages from @boss are CRITICAL
  2. Messages about "database" are IMPORTANT
  3. Messages in #test channels are NORMAL
  4. Ignore bot messages except build failures
```

### Multi-workspace Monitoring

```python
# See advanced_example.py
from advanced_example import MultiWorkspaceMonitor

monitor = MultiWorkspaceMonitor({
    "work": {
        "xoxb_token": "xoxb-work-token",
        "channels": ["alerts"],
        "keywords": ["urgent"]
    },
    "community": {
        "xoxb_token": "xoxb-community-token",
        "channels": ["announcements"],
        "keywords": ["important"]
    }
})

await monitor.start_all()
```

---

## 🔒 Security & Privacy

### Best Practices

1. ✅ Use OAuth tokens instead of browser tokens
2. ✅ Store tokens in `.env.oauth` (gitignored)
3. ✅ Never commit tokens to version control
4. ✅ Use minimum required OAuth scopes
5. ✅ Review which channels the bot can access
6. ✅ Understand messages are sent to Claude API for analysis

### Data Privacy

- Messages are sent to Claude API (Anthropic) for analysis
- No data is stored unless you enable the database feature
- OAuth tokens give specific, controlled access
- MCP server runs locally on your machine

### Token Security

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.oauth" >> .gitignore
echo "*.db" >> .gitignore

# Set restrictive permissions
chmod 600 .env.oauth
```

---

## 🛠️ Development

### Running Tests

```bash
source venv/bin/activate

# Test MCP connection
python test_slack_tools.py

# Test configuration
python config_loader.py

# System diagnostic
python diagnose.py
```

### Adding Custom Tools

See `advanced_example.py` for examples of:
- Custom notification handlers
- Database persistence
- Multi-workspace support
- Custom filtering logic

### Extending the Monitor

```python
from slack_monitor import SlackMonitor

class CustomMonitor(SlackMonitor):
    async def check_messages(self):
        messages = await super().check_messages()

        # Your custom logic here
        for msg in messages:
            if msg.importance == "CRITICAL":
                await self.send_email(msg)

        return messages
```

---

## 📞 Quick Reference

### Common Commands

```bash
# Interactive chat
./run_with_oauth.sh

# 🧠 SMART MONITOR (Recommended - Intelligent Filtering)
./run_smart_monitor.sh              # Run with intelligent filtering
./run_smart_monitor.sh --once       # Test run
./run_smart_monitor.sh --stats      # View filtering statistics

# Standard monitor (sends all alerts)
./run_with_oauth.sh slack_monitor_yaml.py --once
./run_with_oauth.sh slack_monitor_yaml.py

# Advanced with notifications
./run_with_oauth.sh advanced_example.py

# System diagnostic
python diagnose.py

# View stats
./run_with_oauth.sh cli.py --stats
```

### Which Monitor to Use?

| Monitor | Best For | Alert Volume |
|---------|----------|--------------|
| **Smart Monitor** 🧠 | Production, reducing noise | Low (filtered) |
| Standard Monitor | Logging everything | High (all alerts) |
| Interactive Chat | Manual queries | On-demand |

### File Locations

```bash
~/.claude/settings.local.json  # Claude Code MCP config
.env.oauth                     # OAuth token
config.yaml                    # Standard monitor configuration
smart_config.yaml              # Smart monitor configuration
slack_messages.db              # Standard monitor database
smart_alerts.db                # Smart monitor database (with filtering data)
venv/                          # Python virtual environment
slack-mcp-server/              # MCP server binary
docs/SMART_MONITOR.md          # Smart monitor documentation
```

---

## 🤝 Contributing

Suggestions and improvements welcome! This is a personal tool but feel free to:

- Add new features
- Improve documentation
- Report bugs
- Share your use cases

---

## 📜 License

This is a personal tool. Use and modify as needed for your workflow.

---

## 🔗 References

- **Claude Agent SDK**: https://docs.claude.com/en/docs/claude-code/python-sdk-reference
- **Slack MCP Server**: https://github.com/korotovsky/slack-mcp-server
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **Slack API**: https://api.slack.com/

---

## 🎉 Getting Started Checklist

- [ ] Run `./setup.sh` to install dependencies
- [ ] Get Slack OAuth token from https://api.slack.com/apps
- [ ] Save token to `.env.oauth`
- [ ] Run `python diagnose.py` (should show 9/9 passed)
- [ ] Edit `config.yaml` with your channels and keywords
- [ ] Test: `./run_with_oauth.sh`
- [ ] Try: "List my Slack channels"
- [ ] Set up Claude Code integration (optional)
- [ ] Run automated monitoring: `./run_with_oauth.sh slack_monitor_yaml.py`

**Ready to start! Run `./run_with_oauth.sh` and ask "List my Slack channels"** 🚀
