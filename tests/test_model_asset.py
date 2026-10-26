import hashlib
import io

import pytest

from src.config import ModelSettings
from src.core.errors import ModelUnavailableError
from src.vision import model_asset

PAYLOAD = b"fake-model-bytes"


def settings(tmp_path, **kw):
    base = dict(path=tmp_path / "m.task", url="https://example.invalid/m.task",
                sha256=hashlib.sha256(PAYLOAD).hexdigest(), size_bytes=len(PAYLOAD),
                allow_download=True)
    base.update(kw)
    return ModelSettings(**base)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_missing_and_download_disabled(tmp_path):
    with pytest.raises(ModelUnavailableError) as exc:
        model_asset.ensure_model(settings(tmp_path, allow_download=False))
    assert exc.value.code == "model_missing"
    assert "download_model.py" in exc.value.user_message


def test_existing_file_with_wrong_checksum(tmp_path):
    s = settings(tmp_path)
    s.path.write_bytes(b"tampered")
    with pytest.raises(ModelUnavailableError) as exc:
        model_asset.ensure_model(s)
    assert exc.value.code == "model_checksum_mismatch"


def test_download_verifies_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(model_asset.urllib.request, "urlopen",
                        lambda url, timeout: FakeResponse(b"wrong bytes"))
    s = settings(tmp_path)
    with pytest.raises(ModelUnavailableError) as exc:
        model_asset.ensure_model(s)
    assert exc.value.code == "model_checksum_mismatch"
    assert not s.path.exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_success_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setattr(model_asset.urllib.request, "urlopen",
                        lambda url, timeout: FakeResponse(PAYLOAD))
    s = settings(tmp_path)
    assert model_asset.ensure_model(s).read_bytes() == PAYLOAD
    assert model_asset.ensure_model(s) == s.path  # second call uses the verified file


def test_network_error_is_reported(tmp_path, monkeypatch):
    def boom(url, timeout):
        raise OSError("network unreachable")

    monkeypatch.setattr(model_asset.urllib.request, "urlopen", boom)
    with pytest.raises(ModelUnavailableError) as exc:
        model_asset.ensure_model(settings(tmp_path))
    assert exc.value.code == "model_download_failed"


def test_installed_model_matches_pinned_checksum(model_path):
    from src.config import SETTINGS

    assert model_asset.sha256_of(model_path) == SETTINGS.model.sha256
