#!/bin/bash
# Setup Slack MCP server in Claude Code

echo "🔧 Setting up Slack MCP in Claude Code"
echo ""

# Check if tokens are set
if [ -z "$SLACK_MCP_XOXC_TOKEN" ] || [ -z "$SLACK_MCP_XOXD_TOKEN" ]; then
    echo "❌ Slack tokens not set in environment"
    echo ""
    echo "Please set your tokens first:"
    echo "  export SLACK_MCP_XOXC_TOKEN='xoxc-...'"
    echo "  export SLACK_MCP_XOXD_TOKEN='xoxd-...'"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✅ Slack tokens found in environment"
echo ""

# Get the binary path
BINARY_PATH="/home/cslog/svn/ticslog_trunk/python/slack_agent/slack-mcp-server/slack-mcp-server"

if [ ! -f "$BINARY_PATH" ]; then
    echo "❌ Slack MCP server binary not found at: $BINARY_PATH"
    exit 1
fi

echo "✅ Slack MCP server binary found"
echo ""

# Backup settings.json
cp ~/.claude/settings.json ~/.claude/settings.json.backup

echo "✅ Backed up settings.json"
echo ""

# Update settings.json with tokens
echo "📝 Updating Claude Code settings..."

python3 << EOF
import json
import os

settings_file = os.path.expanduser("~/.claude/settings.json")

with open(settings_file, 'r') as f:
    settings = json.load(f)

# Add or update MCP servers
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

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

print("✅ Settings updated successfully!")
EOF

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code (exit and start again)"
echo "  2. Run: /mcp"
echo "  3. You should see: slack (with available tools)"
echo ""
echo "Then you can ask Claude directly:"
echo '  "List my Slack channels"'
echo '  "Show channels starting with cslog-alertas"'
echo '  "Get recent messages from #cslog-alertas-prod"'
echo ""
echo "Backup saved at: ~/.claude/settings.json.backup"
