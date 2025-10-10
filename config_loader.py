#!/usr/bin/env python3
"""
Configuration loader for YAML config files
"""

import yaml
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class Config:
    """Configuration loader for Slack Monitor"""

    def __init__(self, config_file: str = "config.yaml"):
        """Load configuration from YAML file"""
        self.config_file = config_file
        self.config = self._load_config()

        self._channel_aliases = {}
        self._alias_to_id = {}
        self._initialize_channel_aliases()

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

    def _initialize_channel_aliases(self):
        raw_aliases = self.config.get('channel_aliases', {}) or {}
        for key, value in raw_aliases.items():
            if value:
                key_str = str(key)
                value_str = str(value)
                self._channel_aliases[key_str] = value_str
                self._alias_to_id.setdefault(value_str, key_str)

        channel_rules = self.config.get('channel_rules', {}) or {}
        for channel_id, rule in channel_rules.items():
            if isinstance(rule, dict):
                alias = rule.get('alias')
                if alias:
                    cid = str(channel_id)
                    alias_str = str(alias)
                    self._channel_aliases.setdefault(cid, alias_str)
                    self._alias_to_id.setdefault(alias_str, cid)

    @property
    def channel_aliases(self) -> Dict[str, str]:
        return dict(self._channel_aliases)

    def get_channel_alias(self, channel_id: str) -> Optional[str]:
        return self._channel_aliases.get(channel_id)

    def resolve_channel_label(self, channel_id: str) -> str:
        alias = self._channel_aliases.get(channel_id)
        return f"{alias} ({channel_id})" if alias else channel_id

    def get_channel_id_from_alias(self, alias: str) -> Optional[str]:
        if not alias:
            return None
        alias = alias.lstrip('#')
        return self._alias_to_id.get(alias)

    @property
    def channels(self) -> List[str]:
        """Get list of channels to monitor"""
        raw_channels = self.config.get('channels', []) or []
        unique_channels: List[str] = []
        seen = set()

        for channel in raw_channels:
            channel_str = str(channel)
            if '*' in channel_str:
                channel_str = channel_str.replace('*', '')
            if channel_str not in seen:
                seen.add(channel_str)
                unique_channels.append(channel_str)

        return unique_channels

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

    @property
    def channel_rules(self) -> Dict[str, Any]:
        """Get channel-specific alert rules"""
        return self.config.get('channel_rules', {})

    def get_channel_rule(self, channel_name: str) -> Dict[str, Any]:
        """
        Get rules for a specific channel.
        Returns the channel's rules or default rules if not found.

        Args:
            channel_name: Name of the channel (e.g., "cslog-alertas-bd")

        Returns:
            Dict with channel rules including:
            - description: Channel description
            - recurrence_threshold: How many times alert must occur
            - importance_hint: Suggested importance level
            - patterns_to_watch: List of patterns (optional)
            - pattern_rules: List of pattern-specific rules (optional)
            - ignore_patterns: Patterns to ignore (optional)
        """
        rules = self.channel_rules

        # Direct match
        if channel_name in rules:
            return rules[channel_name]

        # Strip leading # if present
        normalized = channel_name.lstrip('#') if isinstance(channel_name, str) else channel_name

        # Alias lookup
        channel_id = self.get_channel_id_from_alias(normalized)
        if channel_id and channel_id in rules:
            return rules[channel_id]

        # Try partial match for historical configs
        for rule_channel, rule_config in rules.items():
            if rule_channel == 'default':
                continue
            if isinstance(rule_channel, str) and normalized.startswith(rule_channel):
                return rule_config

        # Return default if no match
        return rules.get('default', {
            'description': 'Default channel',
            'recurrence_threshold': 5,
            'importance_hint': 'IMPORTANT'
        })

    def get_recurrence_threshold(self, channel_name: str, pattern_match: str = None) -> int:
        """
        Get the recurrence threshold for a specific channel and optionally pattern.

        Args:
            channel_name: Name of the channel
            pattern_match: Optional pattern name that was matched

        Returns:
            Number of occurrences before alerting
        """
        channel_rule = self.get_channel_rule(channel_name)

        # If pattern_match provided, check pattern_rules
        if pattern_match and 'pattern_rules' in channel_rule:
            for pattern_rule in channel_rule['pattern_rules']:
                patterns = pattern_rule.get('patterns', [])
                if any(p.lower() in pattern_match.lower() for p in patterns):
                    return pattern_rule.get('recurrence_threshold', channel_rule.get('recurrence_threshold', 3))

        # Return channel default
        return channel_rule.get('recurrence_threshold', 3)

    def should_ignore_pattern(self, channel_name: str, text: str) -> tuple[bool, str]:
        """
        Check if a message should be ignored based on channel ignore patterns.

        Args:
            channel_name: Name of the channel
            text: Message text to check

        Returns:
            Tuple of (should_ignore: bool, reason: str)
        """
        channel_rule = self.get_channel_rule(channel_name)
        ignore_patterns = channel_rule.get('ignore_patterns', [])

        if not ignore_patterns:
            return False, ""

        text_lower = text.lower()
        for pattern in ignore_patterns:
            if pattern.lower() in text_lower:
                reason = channel_rule.get('ignore_reason', f"Matches ignore pattern: {pattern}")
                return True, reason

        return False, ""

    def get_pattern_match(self, channel_name: str, text: str) -> Dict[str, Any]:
        """
        Check if message matches any specific patterns for the channel.

        Args:
            channel_name: Name of the channel
            text: Message text to analyze

        Returns:
            Dict with pattern match info:
            - matched: bool
            - pattern_name: str (if matched)
            - importance: str (if matched)
            - min_importance: str (if requires minimum importance)
            - recurrence_threshold: int
        """
        channel_rule = self.get_channel_rule(channel_name)
        pattern_rules = channel_rule.get('pattern_rules', [])

        if not pattern_rules:
            return {'matched': False}

        text_lower = text.lower()

        for pattern_rule in pattern_rules:
            patterns = pattern_rule.get('patterns', [])
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return {
                        'matched': True,
                        'pattern_name': pattern_rule.get('name', pattern),
                        'importance': pattern_rule.get('importance', channel_rule.get('importance_hint', 'IMPORTANT')),
                        'min_importance': pattern_rule.get('min_importance'),
                        'recurrence_threshold': pattern_rule.get('recurrence_threshold', channel_rule.get('recurrence_threshold', 3)),
                        'description': pattern_rule.get('description', '')
                    }

        return {'matched': False}

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

        # Test channel rules
        if config.channel_rules:
            print(f"\n📋 Channel Rules:")
            for channel, rules in config.channel_rules.items():
                print(f"  • {channel}: {rules.get('description', 'No description')}")
                print(f"    Threshold: {rules.get('recurrence_threshold', 'N/A')}")
                if 'pattern_rules' in rules:
                    print(f"    Pattern rules: {len(rules['pattern_rules'])}")

        # Test specific channel lookups
        print(f"\n🔍 Testing channel rule lookups:")
        test_channels = ["cslog-alertas-bd", "cslog-alertas-mc", "cslog-alertas-grave", "other-channel"]
        for ch in test_channels:
            rule = config.get_channel_rule(ch)
            threshold = config.get_recurrence_threshold(ch)
            print(f"  {ch}: threshold={threshold}, hint={rule.get('importance_hint', 'N/A')}")

        # Test pattern matching
        print(f"\n🎯 Testing pattern matching:")
        test_cases = [
            ("cslog-alertas-mc", "LOAD average is high"),
            ("cslog-alertas-mc", "database lock detected"),
            ("cslog-alertas-mc", "memory usage critical"),
            ("cslog-alertas-grave", "dxserver serviço updating"),
        ]
        for channel, text in test_cases:
            pattern_match = config.get_pattern_match(channel, text)
            should_ignore, ignore_reason = config.should_ignore_pattern(channel, text)
            print(f"  {channel}: '{text[:40]}...'")
            if should_ignore:
                print(f"    → IGNORE: {ignore_reason}")
            elif pattern_match['matched']:
                print(f"    → Pattern: {pattern_match['pattern_name']}, threshold={pattern_match['recurrence_threshold']}")
            else:
                print(f"    → No special pattern")

        if config.importance_rules:
            print(f"\n📜 Custom rules defined: {len(config.importance_rules)} characters")
    except FileNotFoundError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()
