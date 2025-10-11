"""Minimal HTTP client for calling external LLM services."""

from __future__ import annotations

import json
from typing import Optional

import httpx

from .models import LLMConfig


class LLMInvocationError(RuntimeError):
    """Raised when the LLM invocation fails."""


class LLMClient:
    """Simple async client supporting OpenAI-compatible chat endpoints."""

    def __init__(self, config: LLMConfig):
        if not config.enabled:
            raise ValueError("LLM client cannot be instantiated when disabled.")
        if not config.endpoint:
            raise ValueError("LLM endpoint is required when enabled.")
        if not config.model:
            raise ValueError("LLM model is required when enabled.")

        self.config = config
        self.api_key = config.api_key

    async def invoke(self, prompt: str) -> str:
        """Send prompt to configured endpoint and return text."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are an assistant that prioritizes production alerts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(self.config.endpoint, headers=headers, json=payload)

        if response.status_code >= 400:
            raise LLMInvocationError(f"LLM request failed: {response.status_code} {response.text}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMInvocationError("Unexpected LLM response format") from exc


def render_triage_prompt(message_text: str, channel_label: str, recurrence_count: int) -> str:
    """Helper prompt used by realtime monitor to double-check severity."""
    return (
        "Analise rapidamente o alerta abaixo e responda APENAS com CRITICAL, IMPORTANT, NORMAL ou IGNORE.\n\n"
        f"Canal: {channel_label}\n"
        f"Ocorrências recentes: {recurrence_count}\n"
        f"Mensagem: {message_text}\n"
    )
