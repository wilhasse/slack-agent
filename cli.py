#!/usr/bin/env python3
"""
Command-line interface for Slack Monitor
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import List

try:
    from slack_monitor import SlackMonitor
    from advanced_example import AdvancedSlackMonitor
except ImportError:
    print("❌ Error: Required modules not found")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""

    parser = argparse.ArgumentParser(
        description="Slack Alert Monitor - AI-powered message filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check once and exit
  %(prog)s --once

  # Monitor specific channels
  %(prog)s --channels alerts incidents --keywords urgent critical

  # Monitor continuously with custom interval
  %(prog)s --interval 60

  # Use advanced features (notifications, persistence)
  %(prog)s --advanced

  # Show statistics from database
  %(prog)s --stats

  # Interactive setup
  %(prog)s --setup
        """
    )

    parser.add_argument(
        "--channels", "-c",
        nargs="+",
        metavar="CHANNEL",
        help="Slack channels to monitor (default: all channels with keyword matching)"
    )

    parser.add_argument(
        "--keywords", "-k",
        nargs="+",
        metavar="KEYWORD",
        default=["urgent", "critical", "emergency", "help", "alert"],
        help="Keywords to match (default: urgent, critical, emergency, help, alert)"
    )

    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Check interval in seconds (default: 300)"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit (don't monitor continuously)"
    )

    parser.add_argument(
        "--advanced",
        action="store_true",
        help="Use advanced features (notifications, persistence)"
    )

    parser.add_argument(
        "--db",
        default="slack_messages.db",
        metavar="PATH",
        help="Database path for advanced mode (default: slack_messages.db)"
    )

    parser.add_argument(
        "--no-notifications",
        action="store_true",
        help="Disable desktop notifications in advanced mode"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics from database and exit"
    )

    parser.add_argument(
        "--stats-hours",
        type=int,
        default=24,
        metavar="HOURS",
        help="Hours of history for stats (default: 24)"
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    return parser


async def show_stats(db_path: str, hours: int):
    """Show statistics from database"""

    import sqlite3
    from datetime import datetime, timedelta

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("   Run the monitor first to collect data")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Overall stats
    print(f"\n📊 Slack Monitor Statistics (Last {hours} hours)")
    print("=" * 60)

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN importance = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN importance = 'IMPORTANT' THEN 1 ELSE 0 END) as important,
            SUM(CASE WHEN importance = 'NORMAL' THEN 1 ELSE 0 END) as normal,
            SUM(CASE WHEN importance = 'IGNORE' THEN 1 ELSE 0 END) as ignored
        FROM messages
        WHERE checked_at > datetime('now', '-' || ? || ' hours')
    """, (hours,))

    result = cursor.fetchone()
    total, critical, important, normal, ignored = result

    print(f"\nTotal messages analyzed: {total or 0}")
    print(f"  🚨 Critical:  {critical or 0}")
    print(f"  ⚠️  Important: {important or 0}")
    print(f"  📝 Normal:    {normal or 0}")
    print(f"  🗑️  Ignored:   {ignored or 0}")

    # By channel
    print(f"\n📺 By Channel:")
    cursor.execute("""
        SELECT
            channel,
            COUNT(*) as count,
            SUM(CASE WHEN importance = 'CRITICAL' THEN 1 ELSE 0 END) as critical
        FROM messages
        WHERE checked_at > datetime('now', '-' || ? || ' hours')
        GROUP BY channel
        ORDER BY critical DESC, count DESC
        LIMIT 10
    """, (hours,))

    for row in cursor.fetchall():
        channel, count, crit = row
        print(f"  #{channel:<20} {count:>4} messages  ({crit} critical)")

    # Recent critical messages
    print(f"\n🚨 Recent Critical Messages:")
    cursor.execute("""
        SELECT channel, user, text, checked_at, reason
        FROM messages
        WHERE importance = 'CRITICAL'
          AND checked_at > datetime('now', '-' || ? || ' hours')
        ORDER BY checked_at DESC
        LIMIT 5
    """, (hours,))

    for row in cursor.fetchall():
        channel, user, text, checked_at, reason = row
        text_preview = text[:60] + "..." if len(text) > 60 else text
        print(f"\n  #{channel} - @{user}")
        print(f"  {checked_at}")
        print(f"  \"{text_preview}\"")
        if reason:
            print(f"  Reason: {reason}")

    # Check history
    print(f"\n🕐 Check History:")
    cursor.execute("""
        SELECT
            checked_at,
            messages_found,
            critical_count,
            important_count
        FROM check_history
        ORDER BY checked_at DESC
        LIMIT 5
    """)

    for row in cursor.fetchall():
        checked, found, crit, imp = row
        print(f"  {checked}: {found} messages ({crit} critical, {imp} important)")

    conn.close()
    print()


async def run_monitor(args):
    """Run the monitor with given arguments"""

    # Determine monitor class
    if args.advanced or args.stats:
        MonitorClass = AdvancedSlackMonitor
    else:
        MonitorClass = SlackMonitor

    # Show stats and exit
    if args.stats:
        await show_stats(args.db, args.stats_hours)
        return

    # Create monitor
    monitor_kwargs = {
        "channels_to_monitor": args.channels,
        "keywords": args.keywords,
        "check_interval": args.interval
    }

    if args.advanced:
        monitor_kwargs["db_path"] = args.db
        monitor_kwargs["enable_notifications"] = not args.no_notifications

    monitor = MonitorClass(**monitor_kwargs)

    # Print configuration
    print("🔍 Slack Monitor Configuration")
    print("=" * 60)
    if args.channels:
        print(f"Channels: {', '.join(args.channels)}")
    else:
        print(f"Channels: All (keyword search mode)")
    print(f"Keywords: {', '.join(args.keywords)}")
    print(f"Interval: {args.interval} seconds")
    if args.advanced:
        print(f"Database: {args.db}")
        print(f"Notifications: {'Enabled' if not args.no_notifications else 'Disabled'}")
    print()

    # Run
    if args.once:
        print("📋 Checking messages once...\n")
        await monitor.check_once()
    else:
        print("🔄 Starting continuous monitoring...")
        print("   Press Ctrl+C to stop")
        print()
        await monitor.monitor_continuously()


async def run_setup():
    """Run interactive setup"""
    from quick_start import interactive_setup
    await interactive_setup()


def main():
    """Main entry point"""

    parser = create_parser()
    args = parser.parse_args()

    # Setup mode
    if args.setup:
        asyncio.run(run_setup())
        return

    # Run monitor
    try:
        asyncio.run(run_monitor(args))
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
