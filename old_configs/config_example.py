"""
Example configuration for Slack Monitor
Copy this file to config.py and customize for your needs
"""

# Channels to monitor (leave empty to monitor all channels with keyword matching)
MONITORED_CHANNELS = [
    # "general",
    # "alerts",
    # "incidents",
    # "team-notifications",
]

# Keywords that indicate a message might be important
IMPORTANCE_KEYWORDS = [
    "urgent",
    "critical",
    "emergency",
    "help",
    "alert",
    "incident",
    "down",
    "error",
    "failed",
    "blocked",
    "asap",
    "immediate",
    "production",
    "outage",
]

# How often to check for new messages (in seconds)
CHECK_INTERVAL = 300  # 5 minutes

# MCP Server Configuration
# You can use different transport types:

# Option 1: Stdio (default - runs as a subprocess)
SLACK_MCP_CONFIG_STDIO = {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@korotovsky/slack-mcp-server"],
    "env": {
        # Will be read from environment variables
        "SLACK_MCP_XOXC_TOKEN": "",  # Set via environment
        "SLACK_MCP_XOXD_TOKEN": "",  # Set via environment
    }
}

# Option 2: SSE (if running as a standalone server)
SLACK_MCP_CONFIG_SSE = {
    "type": "sse",
    "url": "http://localhost:3000/sse",
    "headers": {
        # Add any auth headers if needed
    }
}

# Option 3: HTTP
SLACK_MCP_CONFIG_HTTP = {
    "type": "http",
    "url": "http://localhost:3000",
    "headers": {
        # Add any auth headers if needed
    }
}

# Choose which config to use
SLACK_MCP_CONFIG = SLACK_MCP_CONFIG_STDIO

# Claude Model Configuration
CLAUDE_MODEL = None  # Use default, or specify like "claude-sonnet-4"

# Custom importance rules
IMPORTANCE_RULES = """
Additional rules for determining message importance:

1. Messages from specific users (managers, leads, etc.)
2. Messages in threads where you were mentioned
3. Messages with @ mentions of your name or team
4. Messages about systems you're responsible for
5. Build/deployment failures
6. Customer-reported issues
7. Security alerts
"""
