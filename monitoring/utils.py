"""Utility helpers shared across monitoring components."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text by collapsing whitespace."""
    return WHITESPACE_RE.sub(" ", text.strip())


def compute_content_hash(text: str, extra_keys: Iterable[str] | None = None) -> str:
    """Return a deterministic hash for deduplication."""
    normalized = normalize_text(text).lower()
    digest = hashlib.md5(normalized.encode("utf-8"))
    if extra_keys:
        for key in extra_keys:
            digest.update(f"::{key}".encode("utf-8"))
    return digest.hexdigest()
