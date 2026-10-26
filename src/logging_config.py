"""Logging setup. Logs contain timings, counts and error codes only — never image data."""

from __future__ import annotations

import logging

from src.config import SETTINGS

_CONFIGURED = False


def configure_logging(level: str = SETTINGS.log_level) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _CONFIGURED = True
