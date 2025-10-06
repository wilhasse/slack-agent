#!/usr/bin/env python3
"""
Test sending a message to Slack to debug truncation issue
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from slack_monitor import SlackMonitor

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.oauth")
except:
    pass

async def test_send():
    # Test message with multiple lines
    test_message = """🔔 *Test Alert*

🚨 *1 CRITICAL Alert:*

1. *#cslog-alertas-bd* (@System)
   📝 ALERTA - RENAC - daserver 172.22.8.5 ESPAÇO CRÍTICO
   ⚠️ Disk space critically low (1490M free on /var partition)

_This is a test message to verify full content is sent_"""

    print("Sending test message:")
    print("=" * 70)
    print(test_message)
    print("=" * 70)

    monitor = SlackMonitor(
        channels_to_monitor=["test"],
        summary_channel="cslog-alertas-resumo"
    )

    await monitor.connect()

    # Use the private _send_to_slack method from SmartSlackMonitor
    from smart_slack_monitor import SmartSlackMonitor

    smart_monitor = SmartSlackMonitor(
        channels_to_monitor=["test"],
        summary_channel="cslog-alertas-resumo"
    )
    smart_monitor.client = monitor.client

    success = await smart_monitor._send_to_slack(test_message)

    if success:
        print("\n✅ Message sent successfully!")
        print("Check #cslog-alertas-resumo to verify all lines appear")
    else:
        print("\n❌ Message failed to send")

    await monitor.disconnect()

if __name__ == "__main__":
    asyncio.run(test_send())
