#!/usr/bin/env python3
"""Unified CLI for the revamped monitoring system."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from monitoring.configuration import ConfigurationError, load_runtime_config
from monitoring.digest import run_digest
from monitoring.realtime import run_realtime_monitor
from monitoring.storage import AlertStore


def _load_env() -> None:
    if not load_dotenv:
        return
    env_path = Path(__file__).parent / ".env"
    oauth_path = Path(__file__).parent / ".env.oauth"
    if env_path.exists():
        load_dotenv(env_path)
    if oauth_path.exists():
        load_dotenv(oauth_path)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Slack alert monitoring toolkit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to configuration file")
    parser.add_argument(
        "--mode",
        choices=["realtime", "digest", "both"],
        default="realtime",
        help="Which monitoring mode to execute",
    )
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--stats", action="store_true", help="Show alert statistics and exit")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history for statistics")
    parser.add_argument("--clear-old", action="store_true", help="Delete alerts older than --days")
    parser.add_argument("--days", type=int, default=30, help="Age threshold for clear-old")
    return parser


def show_stats(store: AlertStore, hours: int) -> None:
    stats = store.get_statistics(hours=hours)
    total = stats["total"]
    sent = stats["sent"]
    filtered = max(0, total - sent)
    critical = stats["critical"]
    important = stats["important"]

    print(f"\n📊 Alert Statistics (last {hours}h)")
    print("=" * 60)
    print(f"Total alerts:       {total}")
    print(f"Sent to Slack:      {sent}")
    print(f"Filtered locally:   {filtered}")
    print(f"Critical alerts:    {critical}")
    print(f"Important alerts:   {important}")

    if stats["top_channels"]:
        print("\nTop channels:")
        for channel_id, count in stats["top_channels"]:
            print(f"  • {channel_id}: {count}")
    print("=" * 60)


def clear_old(store: AlertStore, days: int) -> None:
    deleted = store.purge_old_alerts(days)
    if deleted:
        print(f"✅ Deleted {deleted} alerts older than {days} days")
    else:
        print(f"✅ No alerts older than {days} days found")


async def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    _load_env()

    try:
        config = load_runtime_config(args.config)
    except ConfigurationError as error:
        print(f"❌ Configuration error: {error}")
        sys.exit(1)

    store = AlertStore(config.database_path)

    if args.stats:
        show_stats(store, hours=max(1, args.hours))
        return

    if args.clear_old:
        clear_old(store, days=max(1, args.days))
        return

    mode = args.mode

    if mode in {"realtime", "both"}:
        print("🔄 Starting realtime monitor..." if not args.once else "🔍 Running realtime monitor once...")
        await run_realtime_monitor(config_path=args.config, once=args.once)

    if mode in {"digest", "both"} and not args.once:
        print("📰 Generating digest summary...")
        await run_digest(config_path=args.config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")
