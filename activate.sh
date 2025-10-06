#!/bin/bash
# Helper script to activate the virtual environment

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""
echo "You can now run:"
echo "  python test_sdk.py          # Test SDK without Slack"
echo "  python quick_start.py       # Test Slack connection"
echo "  python cli.py --help        # See all options"
echo ""
echo "To deactivate when done:"
echo "  deactivate"
