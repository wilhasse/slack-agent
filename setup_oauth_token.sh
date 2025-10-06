#!/bin/bash
# Setup Slack MCP with OAuth bot token (xoxb-)

OAUTH_TOKEN="$1"

if [ -z "$OAUTH_TOKEN" ]; then
    echo "Usage: $0 <oauth-token>"
    echo ""
    echo "Example:"
    echo "  $0 xoxb-YOUR-SLACK-BOT-TOKEN-HERE"
    exit 1
fi

echo "🔧 Configuring Slack MCP with OAuth token..."
echo ""

# Validate token format
if [[ ! $OAUTH_TOKEN =~ ^xoxb- ]]; then
    echo "⚠️  Warning: Token doesn't start with 'xoxb-'"
    echo "   Are you sure this is correct? (y/n): "
    read -r response
    if [[ ! $response =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

BINARY_PATH="/home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server"

if [ ! -f "$BINARY_PATH" ]; then
    echo "❌ Binary not found: $BINARY_PATH"
    exit 1
fi

echo "✅ Binary found"
echo ""

# Backup settings
sudo cp ~/.claude/settings.local.json ~/.claude/settings.local.json.backup 2>/dev/null || true
echo "✅ Settings backed up"
echo ""

# Update settings.local.json with OAuth token
echo "📝 Updating Claude Code settings..."

sudo python3 << EOF
import json
import os
import sys

settings_file = os.path.expanduser("~/.claude/settings.local.json")

# Read existing settings
try:
    with open(settings_file, 'r') as f:
        settings = json.load(f)
except:
    settings = {}

# Add MCP servers with OAuth token
if 'mcpServers' not in settings:
    settings['mcpServers'] = {}

settings['mcpServers']['slack'] = {
    "command": "$BINARY_PATH",
    "args": ["--transport", "stdio"],
    "env": {
        "SLACK_BOT_TOKEN": "$OAUTH_TOKEN",
        "SLACK_MCP_XOXP_TOKEN": "$OAUTH_TOKEN"
    }
}

# Write back
with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

print("✅ Updated settings.local.json")
EOF

echo ""
echo "🎉 OAuth token configured!"
echo ""
echo "Token: ${OAUTH_TOKEN:0:20}...${OAUTH_TOKEN: -10}"
echo ""
echo "Next steps:"
echo "  1. RESTART Claude Code (completely exit and start again)"
echo "  2. Run: /mcp"
echo "  3. You should see: slack"
echo ""
echo "Then try:"
echo '  "List my Slack channels"'
echo '  "Show channels starting with cslog-alertas"'
echo ""
echo "Backup saved: ~/.claude/settings.local.json.backup"
