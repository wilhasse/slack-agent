"""Realtime critical monitor that queries Slack directly without Claude MCP."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from .classifier import HeuristicClassifier
from .configuration import load_runtime_config
from .llm import LLMClient, LLMInvocationError, render_triage_prompt
from .models import AlertRecord, RuntimeConfig, SeverityLevel
from .notifications import NotificationManager
from .slack_client import SlackClientWrapper, SlackMessage
from .storage import AlertStore


class RealtimeMonitor:
    """Continuously polls Slack channels, classifies alerts, and emits notifications."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.store = AlertStore(config.database_path)
        self.slack_client = SlackClientWrapper(config.slack.bot_token)
        self.classifier = HeuristicClassifier(self.store, config.realtime)
        self.notifier = NotificationManager(config.slack, config.notifications, slack_client=self.slack_client)
        self.llm_client: Optional[LLMClient] = None

        if config.realtime.llm.enabled:
            try:
                self.llm_client = LLMClient(config.realtime.llm)
            except ValueError as error:
                raise RuntimeError(f"Realtime LLM configuration invalid: {error}") from error

    async def run_once(self) -> None:
        """Poll all channels a single time."""
        for channel_rule in self.config.channels:
            if channel_rule.muted:
                continue

            cursor_key = f"cursor:{channel_rule.id}"
            oldest_ts = self.store.get_state(cursor_key)

            # On first run (cursor is None), set cursor to "now" to avoid backfilling old messages
            if oldest_ts is None:
                import time
                current_ts = str(time.time())
                self.store.set_state(cursor_key, current_ts)
                print(f"⏭️  First run for {channel_rule.label} - skipping historical messages, cursor set to now")
                continue

            messages = await self.slack_client.fetch_recent_messages(
                channel_rule.id,
                oldest_ts=oldest_ts,
                limit=200,
            )

            if not messages:
                continue

            for message in messages:
                await self._process_message(channel_rule.id, channel_rule.label, channel_rule, message)

            # Update cursor to the most recent message timestamp processed
            latest_ts = messages[-1].ts
            self.store.set_state(cursor_key, latest_ts)

    async def run_forever(self) -> None:
        interval = max(5, self.config.realtime.check_interval_seconds)
        while True:
            try:
                await self.run_once()
            except Exception as error:  # pylint: disable=broad-except
                print(f"❌ Realtime monitor error: {error}")
            await asyncio.sleep(interval)

    async def _process_message(self, channel_id: str, channel_label: str, channel_rule, message: SlackMessage) -> None:
        if self.store.has_message(f"{channel_id}:{message.ts}"):
            return

        decision, context = self.classifier.classify(channel_rule, message.text)

        # Optional secondary check with cheap LLM when near threshold
        if (
            self.llm_client
            and decision.severity == self.config.realtime.severity_threshold
            and decision.severity != SeverityLevel.CRITICAL
        ):
            prompt = render_triage_prompt(message.text, channel_label, context.recurrence_count)
            try:
                llm_response = await self.llm_client.invoke(prompt)
                llm_response = llm_response.strip().upper()
                if llm_response in {"CRITICAL", "IMPORTANT", "NORMAL", "IGNORE"}:
                    llm_severity = SeverityLevel(llm_response)
                    if llm_severity != decision.severity:
                        decision.severity = llm_severity
                        decision.notify = llm_severity.at_least(self.config.realtime.severity_threshold)
                        decision.reason += f"; Overridden by LLM ({llm_response})"
            except LLMInvocationError as error:
                decision.reason += f"; LLM error: {error}"

        message_id = f"{channel_id}:{message.ts}"
        detected_at = datetime.now(timezone.utc)
        event_ts = datetime.fromtimestamp(float(message.ts), tz=timezone.utc)

        alert_record = AlertRecord(
            message_id=message_id,
            channel_id=channel_id,
            channel_label=channel_label,
            user=message.user,
            text=message.text,
            slack_ts=message.ts,
            importance=decision.severity,
            decision_reason=decision.reason,
            detected_at=detected_at,
            event_ts=event_ts,
            content_hash=context.content_hash,
            sent_to_slack=decision.notify,
        )

        if self.store.record_alert(alert_record) and decision.notify:
            await self._dispatch_notifications(alert_record, decision)

    async def _dispatch_notifications(self, alert: AlertRecord, decision) -> None:
        user_display = alert.user or "unknown"
        icon = "🚨" if alert.importance == SeverityLevel.CRITICAL else "⚠️"
        message = (
            f"{icon} *{alert.importance.value}* alerta em #{alert.channel_label}\n"
            f"• Usuário: `{user_display}`\n"
            f"• Texto: {alert.text.strip()}\n"
            f"• Motivo: {decision.reason}"
        )

        await self.notifier.send_slack_message(message)

        if self.config.notifications.whatsapp.get("enabled"):
            await self.notifier.send_whatsapp_message(
                f"{icon} ALERTA {alert.importance.value}\n"
                f"Canal: #{alert.channel_label}\n"
                f"Usuário: {user_display}\n"
                f"Mensagem: {alert.text.strip()}\n"
                f"Motivo: {decision.reason}"
            )


async def run_realtime_monitor(config_path: str = "config.yaml", once: bool = False) -> None:
    config = load_runtime_config(config_path)
    if not config.realtime.enabled:
        print("Realtime monitor disabled in configuration.")
        return

    monitor = RealtimeMonitor(config)
    if once:
        await monitor.run_once()
    else:
        await monitor.run_forever()
