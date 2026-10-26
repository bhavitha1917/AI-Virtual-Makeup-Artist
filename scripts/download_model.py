"""Download and verify the MediaPipe Face Landmarker model.

Usage:  python scripts/download_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import SETTINGS  # noqa: E402
from src.core.errors import ModelUnavailableError  # noqa: E402
from src.vision.model_asset import download_model, sha256_of  # noqa: E402


def main() -> int:
    settings = SETTINGS.model
    if settings.path.is_file() and sha256_of(settings.path) == settings.sha256:
        print(f"Model already present and verified: {settings.path}")
        return 0
    try:
        path = download_model(settings)
    except ModelUnavailableError as exc:
        print(f"Error: {exc.user_message} ({exc.details})", file=sys.stderr)
        return 1
    print(f"Downloaded and verified (SHA-256 {settings.sha256[:12]}…): {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
