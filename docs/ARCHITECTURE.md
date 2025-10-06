# Slack Monitor Architecture

## Overview

This is an **AI-powered Slack monitoring system** that automatically reads messages from Slack channels, analyzes them using Claude AI, and posts intelligent summaries back to Slack. The system runs autonomously without requiring an Anthropic API key by leveraging Claude Code's authentication.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  slack_monitor.py (Python Script)                           │
│  - Runs continuously every 60 seconds                        │
│  - Orchestrates the entire monitoring loop                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
                Every 60 seconds
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Claude Agent SDK → Claude Code CLI → Claude API            │
│                                                              │
│  Query: "Fetch messages from cslog-alertas* channels        │
│          and analyze for important alerts"                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    Uses MCP Tools
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Slack MCP Server (slack-mcp-server binary)                 │
│                                                              │
│  Tools Used:                                                 │
│  - conversations_history → Reads #cslog-alertas-bd          │
│  - conversations_history → Reads #cslog-alertas-sc          │
│  - conversations_search_messages → Searches by keywords     │
└─────────────────────────────────────────────────────────────┘
                          ↓
                  Returns messages
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Claude AI Analysis Engine                                   │
│                                                              │
│  Analyzes messages using:                                    │
│  - Portuguese keywords: urgente, crítico, erro, falha, etc. │
│  - English keywords: urgent, critical, error, failed, etc.   │
│  - Contextual understanding (not just keyword matching)      │
│                                                              │
│  Classification Levels:                                      │
│  - CRITICAL: Needs immediate attention                       │
│  - IMPORTANT: Should be reviewed soon                        │
│  - NORMAL: Can be reviewed later                            │
│  - IGNORE: Not relevant or spam                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
              Returns analysis summary
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  slack_monitor.py processes results                         │
│                                                              │
│  1. Prints analysis to console                              │
│  2. Formats summary with timestamp                          │
│  3. Sends summary back to Slack                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    Uses MCP Tool
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Slack MCP Server                                            │
│                                                              │
│  Tool Used:                                                  │
│  - chat_postMessage → Posts to #cslog-alertas-resumo       │
└─────────────────────────────────────────────────────────────┘
                          ↓
                          ✓
              Message appears in Slack channel
```

## Components

### 1. slack_monitor.py (Main Application)
**Purpose**: Orchestrates the monitoring loop

**Responsibilities**:
- Connects to Claude via Agent SDK
- Configures Slack MCP server with OAuth token
- Sends queries to Claude for message analysis
- Receives and prints analysis results
- Posts summaries back to Slack

**Configuration** (from `config.py`):
- `MONITORED_CHANNELS`: Channels to watch (e.g., `cslog-alertas*`)
- `IMPORTANCE_KEYWORDS`: Keywords indicating important messages
- `CHECK_INTERVAL`: How often to check (60 seconds)
- `SUMMARY_CHANNEL`: Where to post summaries (`cslog-alertas-resumo`)

### 2. Claude Agent SDK (Python Library)
**Purpose**: Interface to Claude AI

**Key Features**:
- Connects to Claude Code CLI (no API key needed!)
- Manages conversation sessions
- Handles MCP tool execution
- Streams responses from Claude

**Authentication**: Uses Claude Code's existing authentication, so no `ANTHROPIC_API_KEY` required

### 3. Claude Code CLI
**Purpose**: Local Claude interface

**Role**:
- Already authenticated with Claude API (from user login)
- Acts as a proxy for the Python script
- Provides the Agent SDK with Claude access
- No additional setup needed

### 4. Slack MCP Server (Go Binary)
**Purpose**: Provides Slack API access via Model Context Protocol

**Location**: `slack-mcp-server/slack-mcp-server` (compiled Go binary)

**Tools Provided**:
- `conversations_history`: Read channel messages
- `conversations_replies`: Read thread replies
- `conversations_search_messages`: Search by keywords
- `chat_postMessage`: Send messages to channels

**Authentication**: OAuth Bot Token (`xoxb-...`)

**Configuration**:
```bash
SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN-HERE
SLACK_MCP_ADD_MESSAGE_TOOL=true  # Enable posting (disabled by default)
```

### 5. Claude AI (Anthropic API)
**Purpose**: Natural language understanding and analysis

**Capabilities**:
- Reads messages in Portuguese and English
- Understands context, not just keywords
- Classifies message importance
- Generates human-readable summaries
- Decides which messages deserve attention

## Data Flow

### Reading Messages (Every 60 seconds)

1. **slack_monitor.py** sends query to Claude:
   ```
   "Check channels cslog-alertas* for messages in the last 60 seconds.
    Look for keywords: urgente, crítico, erro, falha, etc."
   ```

2. **Claude** uses MCP tools:
   ```
   mcp__slack__conversations_history(channel: "cslog-alertas-bd")
   mcp__slack__conversations_history(channel: "cslog-alertas-sc")
   ```

3. **Slack MCP Server** calls Slack API:
   ```
   GET https://slack.com/api/conversations.history
   Authorization: Bearer xoxb-...
   ```

4. **Slack API** returns messages as JSON

5. **Claude** analyzes and returns:
   ```
   "CRITICAL: Database error reported in #cslog-alertas-bd
    User reported 'erro crítico no banco de dados'

    IMPORTANT: High latency alert in #cslog-alertas-sc
    Automated monitoring detected slow response times"
   ```

### Writing Summary (After analysis)

1. **slack_monitor.py** formats summary:
   ```
   📊 Análise de Alertas - 2025-10-06 01:15:00

   [Claude's analysis]

   Gerado automaticamente pelo Monitor de Slack
   ```

2. **Claude** uses MCP tool:
   ```
   mcp__slack__chat_postMessage(
     channel: "cslog-alertas-resumo",
     text: "[formatted summary]"
   )
   ```

3. **Slack MCP Server** calls Slack API:
   ```
   POST https://slack.com/api/chat.postMessage
   Authorization: Bearer xoxb-...
   ```

4. **Message appears** in #cslog-alertas-resumo

## Key Features

### 1. No API Key Required
- Uses **Claude Code's authentication**
- Agent SDK automatically detects Claude Code
- No `ANTHROPIC_API_KEY` environment variable needed

### 2. AI-Powered Analysis
- **Not just keyword matching** - Claude understands context
- Handles Portuguese and English naturally
- Learns from conversation history
- Provides reasoning for classifications

### 3. Bidirectional Slack Integration
- **READ**: Monitors multiple channels (`cslog-alertas*`)
- **WRITE**: Posts summaries to dedicated channel

### 4. Autonomous Operation
- Runs continuously in background
- No manual intervention needed
- Self-contained monitoring loop

### 5. Safety Features
- Message posting disabled by default (`SLACK_MCP_ADD_MESSAGE_TOOL`)
- OAuth token authentication (more secure than browser tokens)
- Channel-specific permissions

## Configuration Files

### config.py (Main Configuration)
```python
MONITORED_CHANNELS = ["cslog-alertas*"]
SUMMARY_CHANNEL = "cslog-alertas-resumo"
CHECK_INTERVAL = 60  # seconds
IMPORTANCE_KEYWORDS = ["urgente", "crítico", "erro", ...]
SLACK_MCP_CONFIG = {
    "env": {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_MCP_ADD_MESSAGE_TOOL": "true"
    }
}
```

### config.yaml (Alternative for YAML-based monitor)
Used by `slack_monitor_yaml.py` - same settings in YAML format

## Security Considerations

### OAuth Token
- Stored in `config.py` (excluded from git via `.gitignore`)
- Bot token scope: `channels:read`, `channels:history`, `chat:write`
- More stable than browser tokens

### Message Posting
- **Disabled by default** to prevent spam
- Must explicitly enable: `SLACK_MCP_ADD_MESSAGE_TOOL=true`
- Can limit to specific channels: `SLACK_MCP_ADD_MESSAGE_TOOL=C123,C456`

### Channel Access
- Bot only sees channels it's invited to
- Must manually add bot to each channel
- Private channels require explicit invitation

## Running the System

### Start Monitoring
```bash
cd /home/cslog/svn/ticslog_trunk/python/slack_agent
source venv/bin/activate
python slack_monitor.py
```

### Expected Output
```
✅ Loaded configuration from config.py
🔍 Starting Slack monitor...
   Checking every 60 seconds
   Keywords: urgente, crítico, emergência, erro, falha, ...
   Channels: cslog-alertas*
   📤 Sending summaries to: #cslog-alertas-resumo

✅ Connected to Claude with Slack MCP server

================================================================================
📊 Slack Analysis (2025-10-06 01:15:00)
================================================================================
[Claude's analysis of messages]
================================================================================

🔍 Claude's response to posting summary:
Message sent successfully to #cslog-alertas-resumo
================================================================================
✅ Summary sent to #cslog-alertas-resumo
```

## Troubleshooting

### Bot can't see messages
- **Solution**: Invite bot to the channel in Slack

### Can't post messages
- **Solution**: Set `SLACK_MCP_ADD_MESSAGE_TOOL=true` in config

### Channel not found
- **Solution**: Bot may not have `channels:read` scope, but can still post if invited

### EPIPE errors
- **Solution**: Ensure Claude Code is running and accessible

## Future Enhancements

Potential improvements:
- Database storage for historical analysis
- Configurable notification thresholds
- Integration with PagerDuty/OpsGenie
- Custom alert routing rules
- Machine learning for better classification
- Multi-workspace support
- Web dashboard for viewing summaries

## Technology Stack

- **Python 3.x**: Main application language
- **Claude Agent SDK**: AI integration
- **Claude Code CLI**: Authentication proxy
- **Slack MCP Server (Go)**: Slack API bridge
- **Model Context Protocol (MCP)**: Tool integration standard
- **Anthropic Claude**: AI analysis engine
- **Slack OAuth**: Workspace authentication

---

**Created**: 2025-10-06
**Author**: AI-Assisted Development with Claude Code
**License**: See repository LICENSE file
