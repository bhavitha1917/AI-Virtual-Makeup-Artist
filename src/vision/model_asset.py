"""Locate, download and verify the MediaPipe Face Landmarker model asset."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from src.config import SETTINGS, ModelSettings
from src.core.errors import ModelUnavailableError

logger = logging.getLogger(__name__)

SETUP_HINT = "Run `python scripts/download_model.py` from the project folder, then reload."


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(settings: ModelSettings = SETTINGS.model) -> Path:
    """Download the pinned model to ``settings.path`` atomically after verifying SHA-256."""
    target = settings.path
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading face landmarker model from %s", settings.url)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".part")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(  # noqa: S310 - pinned https URL
            settings.url, timeout=settings.download_timeout_s
        ) as response:
            remaining = settings.size_bytes * 2  # refuse unexpectedly large responses
            while chunk := response.read(1 << 16):
                remaining -= len(chunk)
                if remaining < 0:
                    raise ModelUnavailableError("model_download_failed",
                                                details="response larger than expected")
                out.write(chunk)
        actual = sha256_of(tmp)
        if actual != settings.sha256:
            raise ModelUnavailableError(
                "model_checksum_mismatch",
                "The downloaded face-analysis model failed its integrity check.",
                details=f"expected {settings.sha256}, got {actual}",
            )
        os.replace(tmp, target)
        return target
    except ModelUnavailableError:
        raise
    except OSError as exc:  # includes URLError/HTTPError/timeouts
        raise ModelUnavailableError(
            "model_download_failed",
            "The face-analysis model could not be downloaded. " + SETUP_HINT,
            details=str(exc),
        ) from exc
    finally:
        if tmp.exists():
            tmp.unlink()


def ensure_model(settings: ModelSettings = SETTINGS.model) -> Path:
    """Return a verified model path, downloading it if allowed and missing."""
    path = settings.path
    if path.is_file():
        if sha256_of(path) == settings.sha256:
            return path
        raise ModelUnavailableError(
            "model_checksum_mismatch",
            "The face-analysis model file is corrupted or not the expected version. "
            "Delete it and " + SETUP_HINT[0].lower() + SETUP_HINT[1:],
        )
    if not settings.allow_download:
        raise ModelUnavailableError(
            "model_missing", "The face-analysis model is not installed. " + SETUP_HINT)
    return download_model(settings)
