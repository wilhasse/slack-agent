#!/usr/bin/env python3
"""
Show the exact system prompt that Claude sees
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from slack_monitor import SlackMonitor
import yaml

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Create monitor
monitor = SlackMonitor(
    channels_to_monitor=config.get("channels", []),
    keywords=config.get("keywords", []),
    check_interval=60
)

# Add custom rules
if "importance_rules" in config:
    monitor.options.system_prompt += f"\n\n{config['importance_rules']}"

# Display the prompt
print("=" * 80)
print("SYSTEM PROMPT THAT CLAUDE SEES:")
print("=" * 80)
print(monitor.options.system_prompt)
print("=" * 80)
