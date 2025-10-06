#!/bin/bash
# Update Claude Code MCP settings with current environment tokens

echo "🔧 Updating Claude Code MCP settings..."
echo ""

# Check tokens
if [ -z "$SLACK_MCP_XOXC_TOKEN" ] || [ -z "$SLACK_MCP_XOXD_TOKEN" ]; then
    echo "❌ Slack tokens not set!"
    echo ""
    echo "Please set them first:"
    echo "  export SLACK_MCP_XOXC_TOKEN='xoxc-...'"
    echo "  export SLACK_MCP_XOXD_TOKEN='xoxd-...'"
    exit 1
fi

# Validate XOXC token format
if [[ ! $SLACK_MCP_XOXC_TOKEN =~ ^xoxc- ]]; then
    echo "⚠️  WARNING: XOXC token doesn't start with 'xoxc-'"
    echo "   Current value: $SLACK_MCP_XOXC_TOKEN"
    echo ""
    echo "Are you sure this is correct? (y/n): "
    read -r response
    if [[ ! $response =~ ^[Yy]$ ]]; then
        echo "Aborted. Please get the correct token from Slack cookies."
        exit 1
    fi
fi

echo "✅ Tokens found"
echo ""

# Binary path
BINARY_PATH="/home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server"

if [ ! -f "$BINARY_PATH" ]; then
    echo "❌ Binary not found: $BINARY_PATH"
    exit 1
fi

echo "✅ Binary found"
echo ""

# Backup both settings files
cp ~/.claude/settings.json ~/.claude/settings.json.backup 2>/dev/null || true
sudo cp ~/.claude/settings.local.json ~/.claude/settings.local.json.backup 2>/dev/null || true

echo "✅ Settings backed up"
echo ""

# Update settings.local.json (takes precedence)
echo "📝 Updating settings.local.json..."

sudo python3 << EOF
import json
import os

settings_file = os.path.expanduser("~/.claude/settings.local.json")

# Read existing settings
try:
    with open(settings_file, 'r') as f:
        settings = json.load(f)
except:
    settings = {}

# Add MCP servers
if 'mcpServers' not in settings:
    settings['mcpServers'] = {}

settings['mcpServers']['slack'] = {
    "command": "$BINARY_PATH",
    "args": ["--transport", "stdio"],
    "env": {
        "SLACK_MCP_XOXC_TOKEN": os.getenv("SLACK_MCP_XOXC_TOKEN"),
        "SLACK_MCP_XOXD_TOKEN": os.getenv("SLACK_MCP_XOXD_TOKEN")
    }
}

# Write back
with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

print("✅ Updated settings.local.json")
EOF

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. RESTART Claude Code (exit and start again)"
echo "  2. Run: /mcp"
echo "  3. You should see: slack"
echo ""
echo "Then try:"
echo '  "List my Slack channels"'
echo ""
