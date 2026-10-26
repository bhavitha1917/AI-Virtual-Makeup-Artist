"""Validation and decoding of untrusted image bytes. Nothing is written to disk."""

from __future__ import annotations

import hashlib
import io
import re
import warnings
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from src.config import SETTINGS, ImageLimits
from src.core.errors import ImageValidationError

Image.MAX_IMAGE_PIXELS = SETTINGS.image.max_pixels  # Pillow's decompression-bomb guard

_UNSAFE = re.compile(r"[\x00-\x1f\x7f<>\"'`]")


@dataclass(frozen=True)
class DecodedImage:
    rgb: np.ndarray = field(repr=False)  # uint8 (H, W, 3)
    fingerprint: str
    original_size: tuple[int, int]
    format: str

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.rgb.shape[:2]
        return (w, h)


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_filename(name: str | None, max_len: int = 60) -> str:
    """Display-safe basename of an untrusted filename (never used as a path)."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = _UNSAFE.sub("", base).strip() or "image"
    return base if len(base) <= max_len else base[: max_len - 1] + "…"


def load_image(data: bytes, limits: ImageLimits = SETTINGS.image) -> DecodedImage:
    """Validate and decode image bytes into an EXIF-oriented, downscaled RGB array."""
    if not data:
        raise ImageValidationError("file_empty", "The file is empty.")
    if len(data) > limits.max_bytes:
        raise ImageValidationError(
            "file_too_large",
            f"The file is larger than {limits.max_bytes // (1024 * 1024)} MB. "
            "Please use a smaller photo.")
    allowed = ", ".join(sorted(f if f != "WEBP" else "WebP" for f in limits.allowed_formats))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                fmt = (probe.format or "").upper()
                width, height = probe.size
                if fmt not in limits.allowed_formats:
                    raise ImageValidationError(
                        "unsupported_format",
                        f"This file type is not supported. Please upload {allowed}.")
                if width * height > limits.max_pixels:
                    raise ImageValidationError(
                        "too_many_pixels", "The image resolution is too high to process safely.")
                probe.verify()
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                img = ImageOps.exif_transpose(img)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    img = Image.alpha_composite(background, img)
                img = img.convert("RGB")
    except ImageValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageValidationError(
            "too_many_pixels", "The image resolution is too high to process safely.") from exc
    except UnidentifiedImageError as exc:
        raise ImageValidationError(
            "unsupported_format", f"This file is not a recognised image. Please upload {allowed}."
        ) from exc
    except Exception as exc:  # truncated/corrupt data raises various Pillow errors
        raise ImageValidationError(
            "decode_failed", "The image appears to be damaged and could not be opened.",
            details=type(exc).__name__) from exc

    w, h = img.size
    if min(w, h) < limits.min_side:
        raise ImageValidationError(
            "too_small",
            f"The image is too small ({w}×{h}). Please use a photo at least "
            f"{limits.min_side} pixels on its shorter side.")
    long_side = max(w, h)
    if long_side > limits.processing_long_side:
        scale = limits.processing_long_side / long_side
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                         Image.Resampling.LANCZOS)
    rgb = np.asarray(img, dtype=np.uint8).copy()
    return DecodedImage(rgb=rgb, fingerprint=fingerprint_bytes(data), original_size=(w, h),
                        format=fmt)
