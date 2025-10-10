#!/usr/bin/env python3
"""
CLI for Smart Slack Monitor

Usage:
  python smart_monitor_cli.py                # Run continuously
  python smart_monitor_cli.py --once         # Check once and exit
  python smart_monitor_cli.py --stats        # Show statistics
  python smart_monitor_cli.py --clear-old    # Clear old alerts from DB
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
import yaml

try:
    from smart_slack_monitor import SmartSlackMonitor
except ImportError:
    print("❌ Error: smart_slack_monitor.py not found")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also try to load .env.oauth
    env_oauth = Path(__file__).parent / ".env.oauth"
    if env_oauth.exists():
        load_dotenv(env_oauth)
except ImportError:
    pass


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"⚠️  Config file not found: {config_path}")
        print("   Please ensure config.yaml exists")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    return config


def show_statistics(monitor: SmartSlackMonitor, hours: int = 24):
    """Display statistics about alert filtering"""
    stats = monitor.get_statistics(hours=hours)

    print(f"\n📊 Smart Monitor Statistics (Last {hours}h)")
    print("=" * 70)

    print(f"\n📨 Alert Processing:")
    print(f"   Total alerts analyzed:  {stats['total_alerts']}")
    print(f"   Sent to Slack:          {stats['sent_to_slack']} ({100 - stats['filter_rate_percent']:.1f}%)")
    print(f"   Filtered out:           {stats['filtered_out']} ({stats['filter_rate_percent']:.1f}%)")

    print(f"\n🎯 By Importance:")
    print(f"   Critical:               {stats['critical_count']}")
    print(f"   Important:              {stats['important_count']}")

    print(f"\n🔍 Pattern Detection:")
    print(f"   Active patterns:        {stats['active_patterns']}")

    if stats['top_patterns']:
        print(f"\n🔝 Top Patterns:")
        for i, pattern in enumerate(stats['top_patterns'], 1):
            print(f"   {i}. {pattern['pattern']:<30} ({pattern['count']} occurrences)")

    # Calculate efficiency
    if stats['total_alerts'] > 0:
        print(f"\n✨ Filtering Efficiency:")
        print(f"   {stats['filter_rate_percent']:.1f}% of alerts filtered")
        print(f"   Reduced noise by {stats['filtered_out']} messages")
        print(f"   Channel pollution avoided! 🎉")
    else:
        print(f"\n📭 No alerts in the last {hours}h")

    print("=" * 70)


async def clear_old_alerts(monitor: SmartSlackMonitor, days: int = 30):
    """Clear alerts older than specified days"""
    import sqlite3

    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()

    # Count how many will be deleted
    cursor.execute("""
        SELECT COUNT(*) FROM alerts
        WHERE created_at < datetime('now', '-' || ? || ' days')
    """, (days,))

    count = cursor.fetchone()[0]

    if count == 0:
        print(f"✅ No alerts older than {days} days")
        conn.close()
        return

    print(f"🗑️  Found {count} alerts older than {days} days")
    response = input(f"Delete them? [y/N]: ").strip().lower()

    if response == 'y':
        # Delete old alerts
        cursor.execute("""
            DELETE FROM alerts
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """, (days,))

        # Delete old decision logs
        cursor.execute("""
            DELETE FROM decision_log
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """, (days,))

        # Clean up patterns with no recent activity
        cursor.execute("""
            DELETE FROM patterns
            WHERE last_seen < datetime('now', '-' || ? || ' days')
        """, (days,))

        conn.commit()
        print(f"✅ Deleted {count} old alerts")
    else:
        print("❌ Cancelled")

    conn.close()


async def run_monitor(config: dict, config_file: str, run_once: bool = False):
    """Run the smart monitor"""

    # Extract config
    channels = config.get("channels", [])
    keywords = config.get("keywords", ["urgent", "critical", "error"])
    check_interval = config.get("check_interval", 300)
    summary_channel = config.get("summary_channel")
    summary_channel_id = config.get("summary_channel_id")

    # Smart filtering settings (use smart_filtering section, fallback to filtering for backwards compat)
    smart_filtering = config.get("smart_filtering", config.get("filtering", {}))
    min_urgency = smart_filtering.get("min_urgency_level", "IMPORTANT")
    duplicate_window = smart_filtering.get("duplicate_window_hours", 24)
    critical_dedup = smart_filtering.get("critical_dedup_hours", 2)
    recurrence_threshold = smart_filtering.get("recurrence_threshold", 3)
    send_full_analysis = smart_filtering.get("send_full_analysis", False)
    interactive_mode = smart_filtering.get("interactive_mode", False)
    interaction_check_interval = smart_filtering.get("interaction_check_interval", 5)
    active_hours_config = smart_filtering.get("active_hours", {})
    active_hours = None
    if isinstance(active_hours_config, dict):
        start_hour = active_hours_config.get("start")
        end_hour = active_hours_config.get("end")
        if start_hour and end_hour:
            active_hours = {"start": str(start_hour), "end": str(end_hour)}

    summary_config = config.get("smart_summary", {})
    summary_schedule = summary_config if isinstance(summary_config, dict) else None

    prompt_log_file = smart_filtering.get("prompt_log_file")

    # Advanced options
    advanced = config.get("advanced", {})
    db_path = advanced.get("smart_database", advanced.get("database", "smart_alerts.db"))
    send_startup = advanced.get("send_startup_notification", True)
    startup_summary_hours = advanced.get("startup_summary_hours", 1)
    webhook_url = advanced.get("slack_webhook_url")

    # Load Config object for channel-specific rules
    from config_loader import Config
    config_obj = Config(config_file)
    channel_aliases = config_obj.channel_aliases

    # Create monitor
    monitor = SmartSlackMonitor(
        channels_to_monitor=channels,
        keywords=keywords,
        check_interval=check_interval,
        summary_channel=summary_channel,
        db_path=db_path,
        min_urgency_level=min_urgency,
        duplicate_window_hours=duplicate_window,
        critical_dedup_hours=critical_dedup,
        recurrence_threshold=recurrence_threshold,
        slack_webhook_url=webhook_url,
        interaction_check_interval=interaction_check_interval,
        active_hours=active_hours,
        summary_schedule=summary_schedule,
        prompt_log_file=prompt_log_file,
        config=config_obj,  # Pass config for channel-specific rules
    )

    # Store startup notification preference
    monitor.send_startup_notification = send_startup
    monitor.startup_summary_hours = startup_summary_hours

    # Store full analysis mode preference
    monitor.send_full_analysis = send_full_analysis

    # Store interactive mode preference
    monitor.interactive_mode = interactive_mode

    # Pre-set channel ID if provided (skips lookup)
    if summary_channel_id:
        monitor._summary_channel_id = summary_channel_id
        print(f"   Using pre-configured channel ID: {summary_channel_id}")

    # Update system prompt with custom rules if provided
    if "importance_rules" in config:
        monitor.options.system_prompt += f"\n\n{config['importance_rules']}"

    # Display configuration
    print("\n🧠 Smart Slack Monitor")
    print("=" * 70)
    print(f"\n⚙️  Configuration:")

    if channels:
        channel_labels = [config_obj.resolve_channel_label(ch) for ch in channels]
        print(f"   Channels:               {', '.join(channel_labels)}")
    else:
        print(f"   Channels:               All (keyword search)")

    print(f"   Keywords:               {len(keywords)} keywords")
    print(f"   Check interval:         {check_interval}s ({check_interval // 60}min)")

    if summary_channel:
        print(f"   Summary channel:        #{summary_channel}")
    else:
        print(f"   Summary channel:        Not configured (alerts will be displayed only)")
    if active_hours:
        print(f"   Active hours:           {active_hours['start']} -> {active_hours['end']} (local)")
    else:
        print(f"   Active hours:           24h (monitoramento contínuo)")
    if summary_schedule and summary_schedule.get("enabled"):
        interval = summary_schedule.get("interval_minutes", 60)
        lookback = summary_schedule.get("lookback_minutes", 60)
        print(f"   Digest schedule:        {interval} min (janela {lookback} min)")
    else:
        print(f"   Digest schedule:        disabled")

    print(f"\n🎯 Filtering Rules:")
    if send_full_analysis:
        print(f"   📋 MODE:                FULL ANALYSIS (showing everything)")
        print(f"      Filtering still runs but sends complete Claude report")
    else:
        print(f"   📋 MODE:                FILTERED SUMMARY (smart filtering)")
    print(f"   Min urgency level:      {min_urgency}")
    print(f"   Dedup window:           {duplicate_window}h (IMPORTANT)")
    print(f"   Critical dedup:         {critical_dedup}h (CRITICAL - more aggressive)")
    print(f"   Recurrence threshold:   {recurrence_threshold}x occurrences")
    print(f"   Database:               {db_path}")

    print(f"\n💡 Smart Features:")
    print(f"   ✓ Duplicate detection")
    print(f"   ✓ Pattern recognition")
    print(f"   ✓ Recurrence tracking")
    print(f"   ✓ Claude-powered decision making")
    print(f"   ✓ Historical analysis")
    if interactive_mode:
        print(f"   ✓ Interactive mode - Ask questions in #{summary_channel}!")

    print("=" * 70)
    print()

    # Run
    if run_once:
        print("🔍 Checking messages once...\n")
        await monitor.check_once()
        print("\n📊 Statistics:")
        show_statistics(monitor, hours=24)
    else:
        print("🔄 Starting continuous monitoring...")
        print("   Press Ctrl+C to stop\n")
        await monitor.monitor_continuously()


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description="Smart Slack Monitor - Intelligent alert filtering with Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run continuously with default config
  %(prog)s

  # Check once and show stats
  %(prog)s --once

  # Show statistics for last 7 days
  %(prog)s --stats --hours 168

  # Use custom config file
  %(prog)s --config my_config.yaml

  # Clear old alerts
  %(prog)s --clear-old --days 60

Features:
  - Deduplicates alerts within configurable time windows
  - Detects recurrent patterns and only alerts when threshold is met
  - Uses Claude to make intelligent decisions on borderline cases
  - Tracks alert history in SQLite database
  - Filters noise to keep your monitoring channel clean
        """
    )

    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        metavar="FILE",
        help="Configuration file (default: config.yaml)"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit (don't monitor continuously)"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics and exit"
    )

    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        metavar="N",
        help="Hours of history for stats (default: 24)"
    )

    parser.add_argument(
        "--clear-old",
        action="store_true",
        help="Clear old alerts from database"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        metavar="N",
        help="Age threshold for clearing (default: 30 days)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    return parser


async def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    # Get database path
    db_path = config.get("database", "smart_alerts.db")

    # Create a temporary monitor just for stats/admin commands
    temp_monitor = SmartSlackMonitor(
        channels_to_monitor=[],
        keywords=[],
        db_path=db_path
    )

    # Handle different modes
    if args.stats:
        show_statistics(temp_monitor, hours=args.hours)
        return

    if args.clear_old:
        await clear_old_alerts(temp_monitor, days=args.days)
        return

    # Normal monitoring mode
    await run_monitor(config, args.config, run_once=args.once)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
