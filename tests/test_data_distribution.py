import json
import zipfile

import pytest

from scripts.package_banking_data import install, sha, verify


def bundle(tmp_path, extra=False):
    path = tmp_path / "bundle.zip"
    data = tmp_path / "source"
    data.write_bytes(b"synthetic test bytes, not a real database")
    manifest = {
        "format": "private-banking-bundle-v1",
        "kind": "analytics",
        "file": "analysis.duckdb",
        "bytes": data.stat().st_size,
        "sha256": sha(data),
    }
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.write(data, "analysis.duckdb")
        if extra:
            z.writestr("../escape", "bad")
    return path


def test_roundtrip_and_no_overwrite(tmp_path):
    path = bundle(tmp_path)
    assert verify(path, sha(path))["kind"] == "analytics"
    destination = tmp_path / "installed"
    install(path, sha(path), destination)
    assert (destination / "analysis.duckdb").stat().st_mode & 0o777 == 0o400
    with pytest.raises(FileExistsError):
        install(path, sha(path), destination)


def test_wrong_checksum(tmp_path):
    with pytest.raises(ValueError, match="checksum"):
        verify(bundle(tmp_path), "0" * 64)


def test_traversal_rejected(tmp_path):
    path = bundle(tmp_path, extra=True)
    with pytest.raises(ValueError, match="members"):
        verify(path, sha(path))


def test_corrupt_database(tmp_path):
    path = bundle(tmp_path)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
    manifest["sha256"] = "0" * 64
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.write(tmp_path / "source", "analysis.duckdb")
    with pytest.raises(ValueError, match="Database checksum"):
        verify(path, sha(path))
