"""Daily rotating text log with secret redaction."""

from __future__ import annotations

import logging
import re
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(ALPACA_KEY\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(ALPACA_SECRET\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(ANTHROPIC_API_KEY\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(sk-ant-[a-zA-Z0-9_-]+)"),
    re.compile(r"(APCA-API-KEY-ID:\s*)\S+", re.IGNORECASE),
    re.compile(r"(APCA-API-SECRET-KEY:\s*)\S+", re.IGNORECASE),
]


def redact(message: str) -> str:
    """Strip anything that looks like a credential before it hits a log sink."""
    out = message
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) + "***REDACTED***") if m.groups() else "***REDACTED***", out)
    return out


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact(original)


def setup_logging(logs_dir: Path, run_date: str, level: int = logging.INFO) -> logging.Logger:
    """Configure the root 'trader' logger: rotating-by-day file + console."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("trader")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = RedactingFormatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    file_handler = logging.FileHandler(logs_dir / f"{run_date}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
