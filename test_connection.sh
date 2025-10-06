#!/bin/bash
# Test Slack MCP server connection

echo "🧪 Testing Slack MCP Server Connection"
echo ""

# Activate venv
source venv/bin/activate

# Check if binary exists
if [ ! -f "slack-mcp-server/slack-mcp-server" ]; then
    echo "❌ Slack MCP server binary not found"
    echo "   Please run: cd slack-mcp-server && go build -buildvcs=false -o slack-mcp-server ./cmd/slack-mcp-server"
    exit 1
fi

echo "✅ Slack MCP server binary found"
echo ""

# Check tokens
if [ -z "$SLACK_MCP_XOXC_TOKEN" ] || [ -z "$SLACK_MCP_XOXD_TOKEN" ]; then
    echo "❌ Slack tokens not set"
    echo "   Please run:"
    echo "   export SLACK_MCP_XOXC_TOKEN='xoxc-...'"
    echo "   export SLACK_MCP_XOXD_TOKEN='xoxd-...'"
    exit 1
fi

echo "✅ Slack tokens configured"
echo ""

# Now run the chat
echo "🚀 Starting interactive chat..."
echo "   (Type 'List all my channels' to test)"
echo ""

python slack_chat.py
