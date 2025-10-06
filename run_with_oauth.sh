#!/bin/bash
# Run any script with OAuth token loaded

# Load OAuth token from .env.oauth
if [ -f ".env.oauth" ]; then
    source .env.oauth
    echo "✅ OAuth token loaded from .env.oauth"
else
    echo "⚠️  .env.oauth not found"
    echo "   Using tokens from environment"
fi

# Activate venv
source venv/bin/activate

# Show which token type is being used
if [ -n "$SLACK_BOT_TOKEN" ] || [ -n "$SLACK_MCP_XOXP_TOKEN" ]; then
    TOKEN="${SLACK_BOT_TOKEN:-$SLACK_MCP_XOXP_TOKEN}"
    echo "🔑 Using OAuth token: ${TOKEN:0:20}...${TOKEN: -10}"
elif [ -n "$SLACK_MCP_XOXC_TOKEN" ] && [ -n "$SLACK_MCP_XOXD_TOKEN" ]; then
    echo "🔑 Using browser tokens (xoxc/xoxd)"
else
    echo "❌ No Slack tokens found!"
    echo ""
    echo "Please either:"
    echo "  1. Use OAuth token: source .env.oauth"
    echo "  2. Set browser tokens:"
    echo "     export SLACK_MCP_XOXC_TOKEN='xoxc-...'"
    echo "     export SLACK_MCP_XOXD_TOKEN='xoxd-...'"
    exit 1
fi

echo ""

# Run the script passed as argument, or default to slack_chat.py
SCRIPT="${1:-slack_chat.py}"

echo "🚀 Running: $SCRIPT"
echo ""

python "$SCRIPT" "${@:2}"
