#!/usr/bin/env python3
"""
Configuration loader for YAML config files
"""

import yaml
import os
from pathlib import Path
from typing import Dict, List, Any


class Config:
    """Configuration loader for Slack Monitor"""

    def __init__(self, config_file: str = "config.yaml"):
        """Load configuration from YAML file"""
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration"""
        config_path = Path(self.config_file)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}\n"
                f"Please create it from config.yaml template"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config or {}

    @property
    def channels(self) -> List[str]:
        """Get list of channels to monitor"""
        channels = self.config.get('channels', [])

        # Expand wildcard patterns
        expanded = []
        for channel in channels:
            if '*' in channel:
                # For now, just remove the asterisk - the actual expansion
                # will happen when querying Slack
                expanded.append(channel.replace('*', ''))
            else:
                expanded.append(channel)

        return channels  # Return original with wildcards

    @property
    def keywords(self) -> List[str]:
        """Get list of keywords"""
        return self.config.get('keywords', [])

    @property
    def check_interval(self) -> int:
        """Get check interval in seconds"""
        return self.config.get('check_interval', 300)

    @property
    def enable_notifications(self) -> bool:
        """Check if notifications are enabled"""
        return self.config.get('advanced', {}).get('notifications', True)

    @property
    def database_path(self) -> str:
        """Get database path"""
        return self.config.get('advanced', {}).get('database', 'slack_messages.db')

    @property
    def persist_messages(self) -> bool:
        """Check if message persistence is enabled"""
        return self.config.get('advanced', {}).get('persist', True)

    @property
    def mcp_server_config(self) -> Dict[str, Any]:
        """Get MCP server configuration"""
        mcp_config = self.config.get('mcp_server', {})

        # Add environment variables for tokens
        if 'env' not in mcp_config:
            mcp_config['env'] = {}

        mcp_config['env'].update({
            'SLACK_MCP_XOXC_TOKEN': os.getenv('SLACK_MCP_XOXC_TOKEN', ''),
            'SLACK_MCP_XOXD_TOKEN': os.getenv('SLACK_MCP_XOXD_TOKEN', ''),
        })

        return mcp_config

    @property
    def importance_rules(self) -> str:
        """Get custom importance rules"""
        return self.config.get('importance_rules', '')

    def get_channel_pattern(self) -> str:
        """Get channel pattern for queries"""
        if not self.channels:
            return "all channels"

        # Build a readable description
        patterns = []
        for channel in self.channels:
            if '*' in channel:
                prefix = channel.rstrip('*')
                patterns.append(f"channels starting with '{prefix}'")
            else:
                patterns.append(f"#{channel}")

        return ", ".join(patterns)

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"Config(\n"
            f"  channels={self.channels}\n"
            f"  keywords={len(self.keywords)} keywords\n"
            f"  check_interval={self.check_interval}s\n"
            f"  notifications={self.enable_notifications}\n"
            f"  database={self.database_path}\n"
            f")"
        )


def load_config(config_file: str = "config.yaml") -> Config:
    """Load configuration from file"""
    return Config(config_file)


if __name__ == "__main__":
    # Test configuration loader
    try:
        config = load_config()
        print("✅ Configuration loaded successfully!\n")
        print(config)
        print(f"\nChannel pattern: {config.get_channel_pattern()}")
        print(f"\nKeywords: {', '.join(config.keywords[:10])}...")
        if config.importance_rules:
            print(f"\nCustom rules defined: {len(config.importance_rules)} characters")
    except FileNotFoundError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()
