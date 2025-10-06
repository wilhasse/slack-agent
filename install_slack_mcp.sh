#!/bin/bash
# Install Slack MCP Server

set -e  # Exit on error

echo "🔧 Installing Slack MCP Server..."
echo ""

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "❌ Go is not installed"
    echo "   Install from: https://golang.org/dl/"
    exit 1
fi

echo "✅ Go installed: $(go version)"
echo ""

# Clone repository if not exists
if [ -d "slack-mcp-server" ]; then
    echo "📁 slack-mcp-server directory already exists"
    echo "   Updating..."
    cd slack-mcp-server
    git pull
    cd ..
else
    echo "📥 Cloning slack-mcp-server repository..."
    git clone https://github.com/korotovsky/slack-mcp-server.git
fi

echo ""
echo "🔨 Building Slack MCP server..."
cd slack-mcp-server

# Install dependencies
echo "   Installing Go dependencies..."
go mod download

# Build the server
echo "   Building binary..."
go build -o slack-mcp-server ./mcp/mcp-server.go

# Check if build was successful
if [ -f "slack-mcp-server" ]; then
    echo "✅ Build successful!"
    echo ""
    echo "Binary location: $(pwd)/slack-mcp-server"

    # Make executable
    chmod +x slack-mcp-server

    cd ..

    # Update MCP config with correct path
    echo ""
    echo "📝 Creating MCP configuration..."

    MCP_PATH="$(pwd)/slack-mcp-server/slack-mcp-server"

    cat > slack_mcp_config.json <<EOF
{
  "slack": {
    "type": "stdio",
    "command": "$MCP_PATH",
    "args": ["--transport", "stdio"],
    "env": {
      "SLACK_MCP_XOXC_TOKEN": "\${SLACK_MCP_XOXC_TOKEN}",
      "SLACK_MCP_XOXD_TOKEN": "\${SLACK_MCP_XOXD_TOKEN}"
    }
  }
}
EOF

    echo "✅ Configuration saved to: slack_mcp_config.json"
    echo ""
    echo "🎉 Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Make sure your Slack tokens are set:"
    echo "     export SLACK_MCP_XOXC_TOKEN='xoxc-...'"
    echo "     export SLACK_MCP_XOXD_TOKEN='xoxd-...'"
    echo ""
    echo "  2. Test the server:"
    echo "     $MCP_PATH --transport stdio"
    echo ""
    echo "  3. Run the chat:"
    echo "     python slack_chat_fixed.py"

else
    echo "❌ Build failed"
    exit 1
fi
