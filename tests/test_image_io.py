import io

import numpy as np
import pytest
from PIL import Image

from src.config import ImageLimits
from src.core.errors import ImageValidationError
from src.vision.image_io import load_image, sanitize_filename
from tests.helpers import encode


def rgb(w=640, h=480, color=(180, 140, 120)):
    arr = np.zeros((h, w, 3), np.uint8)
    arr[:] = color
    return arr


def code_of(data, limits=None):
    with pytest.raises(ImageValidationError) as exc:
        load_image(data, limits) if limits else load_image(data)
    return exc.value.code


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_valid_formats_decode(fmt):
    out = load_image(encode(rgb(), fmt))
    assert out.rgb.dtype == np.uint8 and out.rgb.shape == (480, 640, 3)
    assert out.format == fmt
    assert len(out.fingerprint) == 64


def test_empty_file():
    assert code_of(b"") == "file_empty"


def test_corrupt_bytes():
    data = b"\x89PNG\r\n\x1a\n" + b"garbage" * 50
    assert code_of(data) in {"decode_failed", "unsupported_format"}


def test_truncated_jpeg():
    data = encode(rgb(), "JPEG")
    assert code_of(data[: len(data) // 3]) == "decode_failed"


def test_random_bytes_unsupported():
    assert code_of(bytes(range(256)) * 10) == "unsupported_format"


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_unsupported_formats(fmt):
    assert code_of(encode(rgb(), fmt)) == "unsupported_format"


def test_oversized_bytes():
    limits = ImageLimits(max_bytes=1000)
    assert code_of(encode(rgb(), "PNG"), limits) == "file_too_large"


def test_too_many_pixels():
    limits = ImageLimits(max_pixels=100_000)
    assert code_of(encode(rgb(640, 480), "PNG"), limits) == "too_many_pixels"


def test_too_small():
    assert code_of(encode(rgb(200, 300), "PNG")) == "too_small"


def test_downscale_to_processing_size():
    out = load_image(encode(rgb(2000, 1500), "JPEG"))
    assert max(out.rgb.shape[:2]) == 1280
    assert out.original_size == (2000, 1500)


def test_exif_orientation_applied():
    img = Image.fromarray(rgb(640, 480))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    out = load_image(buf.getvalue())
    assert out.rgb.shape[:2] == (640, 480)


def test_alpha_flattened_on_white():
    arr = np.zeros((300, 300, 4), np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, format="PNG")
    out = load_image(buf.getvalue())
    assert out.rgb.shape[2] == 3 and out.rgb.min() == 255


def test_fingerprint_changes_with_content():
    a = load_image(encode(rgb(color=(1, 2, 3)))).fingerprint
    b = load_image(encode(rgb(color=(3, 2, 1)))).fingerprint
    assert a != b


@pytest.mark.parametrize("name, expected", [
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\selfie.jpg", "selfie.jpg"),
    ("<script>.png", "script.png"),
    ("", "image"),
    (None, "image"),
])
def test_sanitize_filename(name, expected):
    assert sanitize_filename(name) == expected


def test_sanitize_filename_truncates():
    assert len(sanitize_filename("a" * 500 + ".jpg")) <= 60
