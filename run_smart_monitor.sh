#!/bin/bash
# Launcher script for Smart Slack Monitor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧠 Smart Slack Monitor Launcher${NC}"
echo

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "   Run: ./setup.sh"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Check for .env.oauth
if [ -f ".env.oauth" ]; then
    source .env.oauth
    echo -e "${GREEN}✓${NC} Loaded OAuth token from .env.oauth"
elif [ -f ".env" ]; then
    source .env
    echo -e "${GREEN}✓${NC} Loaded environment from .env"
else
    echo -e "${YELLOW}⚠️  No .env.oauth or .env file found${NC}"
    echo "   Make sure SLACK tokens are set in environment"
fi

# Check if config exists
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ config.yaml not found!${NC}"
    echo "   Please ensure config.yaml exists with your settings"
    exit 1
fi

echo -e "${GREEN}✓${NC} Using config.yaml"

# Run the smart monitor
python3 smart_monitor_cli.py "$@"
