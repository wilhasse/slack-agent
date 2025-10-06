#!/bin/bash
# Help get the correct Slack tokens

echo "🔍 Checking your current Slack tokens..."
echo ""

echo "Current XOXD token:"
echo "  ${SLACK_MCP_XOXD_TOKEN:0:50}..."
echo ""

echo "Current XOXC token:"
echo "  ${SLACK_MCP_XOXC_TOKEN}"
echo ""

if [[ ! $SLACK_MCP_XOXC_TOKEN =~ ^xoxc- ]]; then
    echo "⚠️  WARNING: Your XOXC token doesn't look correct!"
    echo "   It should start with 'xoxc-' but yours is: $SLACK_MCP_XOXC_TOKEN"
    echo ""
    echo "📋 To get the correct tokens:"
    echo ""
    echo "1. Open Slack in your browser: https://app.slack.com"
    echo "2. Press F12 (Developer Tools)"
    echo "3. Go to: Application → Cookies → https://app.slack.com"
    echo "4. Find TWO cookies:"
    echo ""
    echo "   Cookie 'd'    → SLACK_MCP_XOXD_TOKEN (starts with xoxd-)"
    echo "   Cookie 'd-s'  → SLACK_MCP_XOXC_TOKEN (starts with xoxc-)"
    echo ""
    echo "5. Copy BOTH complete values"
    echo ""
    echo "Then set them:"
    echo "  export SLACK_MCP_XOXD_TOKEN='xoxd-your-d-cookie-value'"
    echo "  export SLACK_MCP_XOXC_TOKEN='xoxc-your-d-s-cookie-value'"
    echo ""
    echo "Then run: ./update_claude_code_mcp.sh"
else
    echo "✅ XOXC token format looks correct!"
    echo ""
    echo "Ready to update Claude Code settings."
    echo "Run: ./update_claude_code_mcp.sh"
fi
