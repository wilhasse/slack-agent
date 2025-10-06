#!/bin/bash
# Update dependencies to include PyYAML

echo "📦 Atualizando dependências..."

source venv/bin/activate
pip install pyyaml

echo "✅ PyYAML instalado!"
echo ""
echo "Você pode agora usar:"
echo "  python slack_monitor_yaml.py --once"
echo "  python slack_monitor_yaml.py"
