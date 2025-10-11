# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-powered Slack monitoring system** that autonomously monitors Slack channels, analyzes messages using Claude AI, and posts intelligent summaries back to Slack. The system uses the Claude Agent SDK and Model Context Protocol (MCP) to provide real-time Slack workspace analysis without requiring an Anthropic API key.

## Core Architecture

```
Python Monitor Scripts (slack_monitor.py, smart_slack_monitor.py)
    ↓
Claude Agent SDK → Claude Code CLI → Claude API
    ↓
Slack MCP Server (Go binary: slack-mcp-server/slack-mcp-server)
    ↓
Slack API (via OAuth Bot Token)
```

**Key insight**: The system uses Claude Code's existing authentication, so no `ANTHROPIC_API_KEY` is needed. The Agent SDK automatically connects to Claude Code CLI.

### Main Entry Points

- **`slack_chat.py`**: Interactive chat with Claude about Slack workspace
- **`slack_monitor.py`**: Basic continuous monitoring (sends all alerts)
- **`slack_monitor_yaml.py`**: YAML config-based monitoring
- **`smart_slack_monitor.py`**: Enhanced monitor with intelligent filtering (deduplication, pattern detection, recurrence tracking)

### Monitoring Modes

**Standard Monitor**: Analyzes all messages matching keywords and sends every alert to summary channel.

**Smart Monitor** (Recommended): Adds intelligent filtering layer:
- Deduplicates similar alerts within configurable time window
- Detects recurring patterns (only alerts after N occurrences)
- Filters by urgency level (CRITICAL/IMPORTANT/NORMAL/IGNORE)
- Uses SQLite database to track alert history and prevent noise
- Interactive mode: Responds to user questions in summary channel
- Database schema in `smart_slack_monitor.py:80-110`

## Build and Development Commands

```bash
# Initial setup
./setup.sh                     # Create venv, install Python deps, build Go MCP server

# Build MCP server (if slack-mcp-server/ changes)
cd slack-mcp-server
go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server
cd ..

# Activate virtual environment
source venv/bin/activate

# Run interactive chat
./run_with_oauth.sh            # OAuth-aware wrapper, loads .env.oauth

# Run Smart Monitor (recommended)
./run_smart_monitor.sh         # Continuous intelligent monitoring
./run_smart_monitor.sh --once  # Single check (testing)
./run_smart_monitor.sh --stats # View filtering statistics

# Run standard monitor
./run_with_oauth.sh slack_monitor_yaml.py --once

# Diagnostics
python diagnose.py             # Verify connectivity, tokens, tools
python test_slack_tools.py     # End-to-end MCP tool test (requires OAuth token)
python config_loader.py        # Validate config.yaml parsing
python test_sdk.py             # Test Agent SDK wiring
```

## Configuration

**Single unified config**: `config.yaml` (used by all monitors)

Key sections:
- `channels`: Which channels to monitor (supports wildcards like `"cslog-alertas*"`)
- `summary_channel`: Where to send filtered alerts/summaries
- `summary_channel_id`: Pre-resolved channel ID for faster lookups (optional)
- `channel_rules`: **Channel-specific alert rules** (replaces keywords)
  - Per-channel `recurrence_threshold`: How many occurrences before alerting
  - `importance_hint`: Suggested importance level for channel
  - `patterns_to_watch`: List of patterns specific to that channel
  - `pattern_rules`: Pattern-specific rules within a channel (e.g., LOAD alerts, memory alerts)
    - Each pattern can have its own `importance`, `min_importance`, and `recurrence_threshold`
  - `ignore_patterns`: Patterns to automatically ignore (e.g., "dxserver serviço" updates)
- `check_interval`: How often to check (seconds)
- `smart_filtering`: Smart Monitor settings
  - `min_urgency_level`: "CRITICAL" or "IMPORTANT"
  - `duplicate_window_hours`: Dedup window (24h default)
  - `critical_dedup_hours`: Shorter window for CRITICAL alerts (0.5h = 30 min)
  - `interactive_mode`: Enable Q&A in summary channel
  - `interaction_check_interval`: How often to check for questions (2s default)
- `advanced`: Database paths, startup notifications, verbosity
- `keywords`: Deprecated (empty array for backwards compatibility)

**Important**: `config.py` now loads from `config.yaml` (backwards compatible). Edit `config.yaml` only.

## Authentication & Secrets

**OAuth Token** (preferred):
```bash
# Store in .env.oauth (gitignored)
echo "SLACK_BOT_TOKEN=xoxb-your-token-here" > .env.oauth
source .env.oauth
```

**Browser Tokens** (fallback):
```bash
export SLACK_MCP_XOXC_TOKEN='xoxc-...'
export SLACK_MCP_XOXD_TOKEN='xoxd-...'
```

**Required OAuth Scopes**:
- `channels:read` - List public channels
- `channels:history` - Read messages
- `chat:write` - Post messages (for summary channel)
- Optional: `groups:read`, `groups:history` for private channels

**Security**: Never commit `.env.oauth`, `config.py`, or `*.db` files (already gitignored).

## Code Architecture Notes

### Message Flow (Standard Monitor)

1. `slack_monitor.py` creates Claude session with Slack MCP server configured
2. Every `check_interval` seconds, sends query to Claude: "Check channels X for messages in last Z seconds"
3. Claude uses MCP tools (`conversations_history`) to fetch messages from monitored channels
4. Claude analyzes each message based on:
   - Channel context (from `importance_rules` and `channel_rules`)
   - Message content and urgency
   - **Not keyword matching** - understands actual meaning
5. Claude classifies each message (CRITICAL/IMPORTANT/NORMAL/IGNORE) with reasoning
6. Monitor receives analysis, prints to console
7. If `summary_channel` configured, posts summary back to Slack via `conversations_add_message`

**Key difference from old approach**: No keyword filtering. Claude analyzes all messages in monitored channels using context-aware understanding.

### Smart Monitor Enhancements

Extends `SlackMonitor` with filtering logic:

**Database**: `smart_alerts.db` (SQLite)
- `alerts`: Historical alerts with content hashes, pattern signatures
- `alert_patterns`: Aggregated recurring patterns with occurrence counts
- `sent_summaries`: Track what was sent to avoid duplicates

**Content Hashing**: Messages normalized (lowercased, whitespace trimmed) then MD5 hashed to detect exact duplicates.

**Pattern Signature**: Uses **channel-specific patterns** from `channel_rules`:
- Checks `pattern_rules` first (e.g., LOAD alerts, memory alerts, database locks)
- Falls back to `patterns_to_watch` for the channel
- Generic patterns only if no channel rules defined
- Creates signature like: `channel_name:pattern1-pattern2`

**Filtering Pipeline**:
1. Fetch messages from Slack (via parent class)
2. **Check ignore patterns** (`channel_rules[channel].ignore_patterns`) - skip if matched (e.g., "dxserver serviço")
3. Hash each message, check database for duplicates within `duplicate_window_hours`
4. For CRITICAL alerts, use shorter `critical_dedup_hours` window
5. Extract pattern signature using channel-specific patterns
6. **Get channel-specific recurrence threshold** (e.g., cslog-alertas-bd: 2, cslog-alertas-mc LOAD: 3)
7. **Check min_importance requirement** (e.g., memory alerts in cslog-alertas-mc only sent if CRITICAL)
8. Only send if: urgency ≥ `min_urgency_level` AND (not duplicate OR recurrence threshold met)
9. Optional: Ask Claude for final decision on borderline cases (`use_claude_decision`)
10. Store in database, mark as sent

**Interactive Mode** (`smart_filtering.interactive_mode`):
- Every `interaction_check_interval` seconds, checks summary channel for new user messages
- Uses timestamp tracking to avoid re-answering same message
- Responds to questions about recent alerts with context from database
- Example: "What was that disk space alert about?" → Claude queries DB and explains

### MCP Server Configuration

The Slack MCP server (Go binary) is configured dynamically in Python:

```python
mcp_server_config = {
    "type": "stdio",
    "command": str(mcp_binary_path),
    "args": ["--transport", "stdio"],
    "env": {
        "SLACK_BOT_TOKEN": oauth_token,
        "SLACK_MCP_ADD_MESSAGE_TOOL": "true",  # Enable posting
    }
}
```

**Tool Filtering**: `slack_monitor.py:97-105` restricts which MCP tools Claude can use (reduces latency, prevents unintended actions).

## Testing Strategy

**Before commits**:
1. `python diagnose.py` → Verify 9/9 checks pass
2. `./run_smart_monitor.sh --once` → Smoke test monitoring logic
3. Check console output for errors, verify summary posted to Slack

**New features**:
- Add test script alongside existing ones (e.g., `test_new_feature.py`)
- Document any required environment setup in script docstring
- Export tokens from `.env.oauth` before running

## Channel Rules Architecture

The system now uses **channel-specific rules** instead of global keywords:

**Config Loader** (`config_loader.py`):
- `get_channel_rule(channel_name)`: Returns rules for specific channel (with fallback to default)
- `get_recurrence_threshold(channel, pattern)`: Gets threshold, checking pattern rules first
- `should_ignore_pattern(channel, text)`: Checks ignore patterns (e.g., "dxserver serviço")
- `get_pattern_match(channel, text)`: Matches text against channel's `pattern_rules`

**Smart Monitor** (`smart_slack_monitor.py`):
- Receives `config` object in `__init__`
- `_extract_pattern_signature()`: Uses channel-specific patterns from config
- `_should_send_alert()`:
  - Checks ignore patterns first
  - Checks `min_importance` requirement for pattern rules
  - Uses channel-specific recurrence threshold

**Example**: cslog-alertas-mc (verbose monitoring center)
- Default threshold: 5 occurrences
- LOAD alerts: threshold 3, importance IMPORTANT
- Memory alerts: threshold 2, **only if CRITICAL** (min_importance check)
- Database locks: threshold 4, importance IMPORTANT

## Common Pitfalls

1. **Claude responses timeout**: Smart Monitor has timeouts hardened to 60s+ due to large channel histories. See `slack_monitor.py:59` and `smart_slack_monitor.py:334-338`.

2. **Duplicate responses**: Smart Monitor tracks `_responded_messages` set using message timestamps. Always use timestamp-based dedup, not just message ID. See commit `2641518`.

3. **Message posting disabled**: MCP server disables `conversations_add_message` by default. Must set `SLACK_MCP_ADD_MESSAGE_TOOL=true` in config.

4. **Channel resolution failures**: If bot can't resolve channel name to ID, use pre-resolved `summary_channel_id` in `config.yaml` for faster lookups.

5. **Interactive mode blocking**: During alert monitoring, skip interaction checks to avoid delaying alerts. See `smart_slack_monitor.py:275-282`.

6. **False "already answered"**: Use message timestamps (`ts` field) not just content to track responses. Recent fix in commit `b98dc90`.

7. **Forgetting to pass config to SmartSlackMonitor**: Must pass `config` parameter for channel rules to work. See `smart_monitor_cli.py:164-182`.

## Claude Agent SDK Patterns

**Session Management**:
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    mcp_servers={"slack": mcp_config},
    allowed_tools=["mcp__slack__conversations_history", ...],  # Restrict tools
    timeout_seconds=60.0,  # Adjust for large channels
)

async with ClaudeSDKClient(options) as client:
    response = await client.completion(prompt, conversation_history)
```

**Streaming Responses**: Use `async for block in response` to process streaming tool calls and text incrementally.

**Tool Result Extraction**: Parse `ToolResultBlock` objects to get MCP tool outputs. See `slack_monitor.py:210-230`.

## Commit Message Style

Follow imperative mood, capitalized:
- ✅ `Fix duplicate responses: Track which messages have been answered`
- ✅ `Add AGENTS guide and harden monitor timeouts`
- ❌ `Fixed bug` or `fixes the timeout issue`

Cite key files in commit body when helpful. Link issues if applicable.

## Documentation References

- `README.md`: User-facing overview, quick start, features
- `AGENTS.md`: This coding guide (now deprecated in favor of CLAUDE.md)
- `CONFIG_GUIDE.md`: Configuration migration and unified config explanation
- `docs/ARCHITECTURE.md`: Detailed system architecture and data flow
- `docs/SMART_MONITOR.md`: Smart Monitor feature guide
- `docs/INTERACTIVE_MODE.md`: Interactive mode Q&A documentation
- `docs/OAUTH_SETUP.md`: How to get Slack OAuth tokens

## Repository Structure Philosophy

- **Root level**: Entry points (`slack_monitor.py`, `smart_slack_monitor.py`, `slack_chat.py`) and helper scripts
- **slack-mcp-server/**: Go binary (rebuild when changed)
- **docs/**: Extended documentation
- **venv/**: Python virtual environment (gitignored)
- **config.yaml**: Single source of truth for all configuration
- ***.db**: SQLite databases (gitignored)

Keep workflows scriptable. Add new entry points as small shell helpers (`.sh`) when possible.
