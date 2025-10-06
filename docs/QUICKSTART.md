# Quick Start Guide

## 1. Setup (One-time)

```bash
# Run the setup script (creates venv and installs dependencies)
./setup.sh
```

## 2. Activate Virtual Environment

Every time you want to use the Slack monitor:

```bash
source venv/bin/activate
```

Or use the helper:
```bash
source activate.sh
```

## 3. Test Without Slack (Verify SDK Works)

```bash
python test_sdk.py
```

Expected output:
```
Testing Claude SDK Client (no Slack required)...
Sending test query to Claude...
Response: ...
✅ SDK is working!
```

## 4. Get Slack Tokens

1. Open Slack in browser: https://app.slack.com
2. Press **F12** (Developer Tools)
3. Go to: **Application** → **Cookies** → `https://app.slack.com`
4. Find and copy:
   - `d` cookie → This is your **SLACK_MCP_XOXD_TOKEN**
   - `d-s` cookie → This is your **SLACK_MCP_XOXC_TOKEN**

## 5. Configure Tokens

**Option A: Interactive Setup**
```bash
python quick_start.py --setup
```

**Option B: Manual .env file**
```bash
cp .env.example .env
# Edit .env and paste your tokens
nano .env
```

**Option C: Export directly**
```bash
export SLACK_MCP_XOXC_TOKEN='xoxc-your-token-here'
export SLACK_MCP_XOXD_TOKEN='xoxd-your-token-here'
```

## 6. Test Slack Connection

```bash
python quick_start.py
```

Expected output:
```
✅ Slack tokens found
🔌 Connecting to Slack via MCP server...
✅ Connection successful!
🔍 Checking for recent important messages...
```

## 7. Run the Monitor

**Check once:**
```bash
python cli.py --once
```

**Monitor continuously:**
```bash
python cli.py
```

**Monitor specific channels:**
```bash
python cli.py --channels alerts incidents --keywords urgent critical
```

**Advanced mode (notifications + database):**
```bash
python cli.py --advanced
```

## 8. When You're Done

```bash
deactivate  # Exit virtual environment
```

## Common Issues

**"ModuleNotFoundError: No module named 'claude_agent_sdk'"**
→ Activate the virtual environment: `source venv/bin/activate`

**"Claude Code not found"**
→ Install: `npm install -g @anthropic-ai/claude-code`

**"Connection failed to Slack MCP server"**
→ Check your tokens are still valid (log out/in to Slack if needed)

**"externally-managed-environment"**
→ Already fixed! You're using the virtual environment.

## Full Workflow Example

```bash
# First time setup
./setup.sh

# Start working
source venv/bin/activate

# Test basic SDK
python test_sdk.py

# Setup Slack tokens
python quick_start.py --setup

# Test Slack connection
python quick_start.py

# Run monitor
python cli.py --channels prod-alerts --keywords urgent error --advanced

# Done
deactivate
```
