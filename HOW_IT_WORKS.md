# How the Slack Monitor Works

## 🎯 Your Question: "Can I talk with this system?"

**YES!** You have two modes:

### 1. **Interactive Chat** (Recommended for exploring)
```bash
python slack_chat.py
```

This lets you **talk directly** with Claude about your Slack channels:
- "Show me all my channels"
- "List channels starting with cslog-alertas"
- "Get recent messages from #cslog-alertas-prod"
- "Search for messages with 'erro' in the last hour"

### 2. **Automated Monitor** (For continuous monitoring)
```bash
python slack_monitor.py        # Fixed version - now uses tools
python slack_monitor_yaml.py   # YAML config version
```

This runs automatically and analyzes messages periodically.

---

## 🔧 How It Works

### The Problem You Had

When you ran `slack_monitor.py`, Claude said:
> "I don't have access to Slack data"

**Why?** The prompt wasn't explicit enough about USING the Slack MCP tools.

### The Architecture

```
┌─────────────────────────────────────────┐
│  Your Command                           │
│  python slack_chat.py                   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Claude SDK Client                      │
│  - Manages connection to Claude         │
│  - Loads Slack MCP server               │
│  - Makes tools available                │
└──────────────┬──────────────────────────┘
               │
               ├──────────────────┐
               │                  │
               ▼                  ▼
┌──────────────────────┐   ┌─────────────────┐
│  Slack MCP Server    │   │  Claude AI      │
│  (via browser tokens)│   │  (Sonnet 4.5)   │
│                      │   │                 │
│  Tools:              │   │  Decides which  │
│  - channels_list     │◄──┤  tools to use   │
│  - conversations_    │   │                 │
│    history           │   │  Analyzes       │
│  - search_messages   │   │  responses      │
└──────────────────────┘   └─────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Your Slack Workspace                   │
│  - All your channels                    │
│  - Message history                      │
│  - Search capabilities                  │
└─────────────────────────────────────────┘
```

### The Flow (Step by Step)

1. **You ask:** "Show me channels starting with cslog-alertas"

2. **SDK Client:**
   - Sends your question to Claude
   - Tells Claude: "You have these Slack tools available"

3. **Claude decides:**
   - "I need to use the `channels_list` tool"
   - Calls: `mcp__slack__channels_list`

4. **Slack MCP Server:**
   - Uses your browser tokens
   - Connects to Slack API
   - Gets list of all channels
   - Returns data to Claude

5. **Claude analyzes:**
   - Receives channel list
   - Filters for channels starting with "cslog-alertas"
   - Formats response

6. **You receive:**
   - "Found 3 channels: cslog-alertas-prod, cslog-alertas-dev, cslog-alertas-test"

---

## 🔍 Available Tools

The Slack MCP server provides these tools:

| Tool | What It Does | Example Use |
|------|-------------|-------------|
| `channels_list` | Get all channels | "Show me my channels" |
| `conversations_history` | Get messages from a channel | "Messages from #alerts" |
| `conversations_replies` | Get thread replies | "Show replies to this thread" |
| `conversations_search_messages` | Search messages | "Find 'erro' in last 24h" |

---

## 🎮 Three Ways to Use

### Option 1: Interactive Chat (Best for exploring)

```bash
python slack_chat.py
```

**Pros:**
- ✅ Talk directly with Claude
- ✅ Explore your channels interactively
- ✅ Ask follow-up questions
- ✅ See what tools Claude uses

**Cons:**
- ❌ Manual - you need to ask each time

**Use when:**
- Exploring your Slack workspace
- Finding channels
- Investigating specific issues
- Testing queries

### Option 2: Step-by-Step Tests

```bash
python test_slack_tools.py
```

**Pros:**
- ✅ Shows exactly what each tool does
- ✅ Helps understand the system
- ✅ Good for debugging

**Use when:**
- First time setup
- Troubleshooting
- Learning how it works

### Option 3: Automated Monitor

```bash
# Fixed version (now uses tools correctly)
python slack_monitor.py

# Or YAML config version
python slack_monitor_yaml.py
```

**Pros:**
- ✅ Runs automatically
- ✅ Periodic checks
- ✅ Filters important messages
- ✅ Can send notifications

**Cons:**
- ❌ Not interactive
- ❌ Fixed schedule

**Use when:**
- Continuous monitoring
- Background watching
- Alert filtering

---

## 🐛 What Was Fixed

### Before (Didn't Work)

```python
query = "Check the following Slack channels for messages..."
# Claude: "I don't have access to Slack" ❌
```

**Problem:** Too vague - Claude didn't know to USE the tools.

### After (Works Now)

```python
query = """USE the Slack MCP tools to check messages.

IMPORTANT: You must use the mcp__slack__conversations_history tool.

Look for messages from channels: {channel_list}"""
# Claude: *uses tool* "Here are the messages..." ✅
```

**Solution:** Explicitly tell Claude to USE the tools.

---

## 💡 Interactive Examples

### Example 1: Find Your Alert Channels

```bash
python slack_chat.py
```

```
You: List all channels that start with cslog-alertas

Claude: *uses channels_list tool*
       Found 3 channels:
       1. cslog-alertas-prod
       2. cslog-alertas-dev
       3. cslog-alertas-test
```

### Example 2: Check Recent Messages

```
You: Show me recent messages from cslog-alertas-prod

Claude: *uses conversations_history tool*
       Latest messages in #cslog-alertas-prod:

       1. @joao (2 min ago): "Deploy concluído com sucesso"
       2. @maria (15 min ago): "⚠️ ERRO: Timeout na API"
       3. @bot (1 hour ago): "Build #1234 failed"
```

### Example 3: Search for Errors

```
You: Search for messages containing "erro" in the last hour

Claude: *uses conversations_search_messages tool*
       Found 2 messages with "erro":

       CRÍTICO - #cslog-alertas-prod
       @maria: "⚠️ ERRO: Timeout na API"
       Reason: Production error affecting API

       IMPORTANTE - #cslog-alertas-dev
       @pedro: "Erro de conexão no ambiente de teste"
       Reason: Development environment issue
```

---

## 🚀 Quick Start Commands

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Set Slack tokens
export SLACK_MCP_XOXC_TOKEN='xoxc-...'
export SLACK_MCP_XOXD_TOKEN='xoxd-...'

# 3a. Interactive chat (recommended first)
python slack_chat.py

# 3b. Test tools step by step
python test_slack_tools.py

# 3c. Run automated monitor
python slack_monitor_yaml.py --once
```

---

## ❓ FAQ

**Q: Why does it ask Claude instead of directly calling Slack API?**

A: Claude adds intelligence:
- Filters important vs unimportant messages
- Understands context and urgency
- Classifies by priority
- Provides natural language summaries

**Q: Can I just call the Slack API directly?**

A: Yes, but you'd lose the AI filtering. You'd get ALL messages, not just important ones.

**Q: Does Claude see all my Slack messages?**

A: Only messages Claude fetches with the tools. You control what channels/timeframes it searches.

**Q: Can I add custom filtering rules?**

A: Yes! Edit `config.yaml`:
```yaml
importance_rules: |
  Custom rules:
  1. Messages from @boss are always CRITICAL
  2. Messages about "database" are IMPORTANT
  3. etc.
```

---

## 🎯 Best Practices

1. **Start with interactive chat** to explore your channels
2. **Use test_slack_tools.py** to understand how tools work
3. **Configure config.yaml** with your channels/keywords
4. **Run automated monitor** for continuous watching
5. **Adjust check_interval** based on urgency (60s = urgent, 600s = normal)

---

## 🔐 Security Notes

- Browser tokens are session-based
- They expire when you log out of Slack
- Messages are sent to Claude API for analysis
- No data is stored unless you use advanced mode with database

---

## 📚 Summary

**Can you talk with this system?** → **YES!** Use `slack_chat.py`

**How does it work?** → Claude uses Slack MCP tools to fetch real data, then analyzes it

**What was the problem?** → The prompt wasn't explicit about using tools (now fixed)

**What should you try first?** → `python slack_chat.py` - it's interactive and shows you what's happening
