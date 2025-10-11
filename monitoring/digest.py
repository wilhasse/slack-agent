"""Periodic digest generation built on top of the shared alert store."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from .configuration import load_runtime_config
from .llm import LLMClient, LLMInvocationError
from .models import AlertRecord, DigestConfig, RuntimeConfig, SeverityLevel
from .notifications import NotificationManager
from .storage import AlertStore


class DigestGenerator:
    """Builds and delivers digest summaries from stored alerts."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.store = AlertStore(config.database_path)
        self.notifier = NotificationManager(config.slack, config.notifications)
        self.llm_client: Optional[LLMClient] = None

        if config.digest.llm.enabled:
            self.llm_client = LLMClient(config.digest.llm)

    def build_digest_message(self, lookback_minutes: int, include_filtered: bool) -> str:
        alerts = self.store.fetch_recent_alerts(
            lookback_minutes=lookback_minutes,
            include_filtered=include_filtered,
            min_severity=SeverityLevel.NORMAL,
        )
        now_local = datetime.now(timezone.utc)
        header_time = now_local.strftime("%d/%m %H:%M")

        lines: List[str] = [
            f"🕒 *Resumo automático - {header_time}*",
            f"Período analisado: últimas {lookback_minutes} minutos",
        ]

        total = len(alerts)
        sent = sum(1 for alert in alerts if alert.sent_to_slack)
        filtered = total - sent
        critical = sum(1 for alert in alerts if alert.importance == SeverityLevel.CRITICAL)
        important = sum(1 for alert in alerts if alert.importance == SeverityLevel.IMPORTANT)

        lines.append(f"Total de alertas registrados: {total} (notificados: {sent} | filtrados: {filtered})")

        if critical or important:
            segments: List[str] = []
            if critical:
                segments.append(f"🚨 {critical} crítico(s)")
            if important:
                segments.append(f"⚠️ {important} importante(s)")
            lines.append("Classificação: " + ", ".join(segments))
        else:
            lines.append("Classificação: Nenhum alerta crítico/importante no período.")

        if alerts:
            lines.append("\n📌 Destaques:")
            for alert in alerts[: self.config.digest.lookback_minutes // 5 or 5]:
                timestamp = alert.event_ts or alert.detected_at
                time_str = timestamp.astimezone(timezone.utc).strftime("%H:%M")
                status_icon = "✅" if alert.sent_to_slack else "⏳"
                preview = alert.text.strip()
                if len(preview) > 120:
                    preview = preview[:117] + "..."
                lines.append(
                    f"{status_icon} {time_str} · #{alert.channel_label} · [{alert.importance.value}] · {preview}"
                )
                lines.append(f"   • Motivo: {alert.decision_reason}")
        else:
            lines.append("\n✅ Nenhum alerta relevante registrado no período.")

        lines.append("\n_Monitor em modo resumo periódico_")
        return "\n".join(lines)

    async def send_digest(self) -> None:
        digest_cfg: DigestConfig = self.config.digest
        if not digest_cfg.enabled:
            return

        message = self.build_digest_message(digest_cfg.lookback_minutes, digest_cfg.include_filtered)

        if self.llm_client:
            try:
                llm_summary = await self.llm_client.invoke(
                    "Resuma em PT-BR as informações principais:\n\n" + message
                )
                if llm_summary:
                    message += f"\n\n🧠 *Resumo inteligente:*\n{llm_summary.strip()}"
            except LLMInvocationError as error:
                message += f"\n\n⚠️ Falha ao chamar LLM: {error}"

        target = self.config.slack.summary_channel_id or self.config.slack.summary_channel
        await self.notifier.send_slack_message(message, channel_override=target)

        if self.config.notifications.whatsapp.get("enabled"):
            await self.notifier.send_whatsapp_message(message)


async def run_digest(config_path: str = "config.yaml") -> None:
    config = load_runtime_config(config_path)
    generator = DigestGenerator(config)
    await generator.send_digest()
