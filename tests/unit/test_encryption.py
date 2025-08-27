import os
from pathlib import Path
import base64
import json
import shutil
import tempfile
import pytest

from engine.security.encryption import (
    EncryptionManager,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
)


@pytest.fixture()
def temp_dir(tmp_path: Path):
    # Use a temp working dir to avoid polluting repo
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(cwd)


def test_encrypt_decrypt_roundtrip_string(temp_dir: Path):
    mgr = EncryptionManager()
    plaintext = "hello secret"
    token = mgr.encrypt(plaintext)
    assert isinstance(token, (bytes, bytearray))
    out = mgr.decrypt(token)
    assert out == plaintext


def test_encrypt_decrypt_roundtrip_bytes(temp_dir: Path):
    mgr = EncryptionManager()
    data = b"\x00\x01binary"
    token = mgr.encrypt(data)
    out = mgr.decrypt(token)
    # decrypt returns str for non-JSON, so compare bytes->str decode
    assert out == data.decode()


def test_encrypt_decrypt_roundtrip_dict(temp_dir: Path):
    mgr = EncryptionManager()
    payload = {"a": 1, "b": "two"}
    token = mgr.encrypt(payload)
    out = mgr.decrypt(token)
    assert isinstance(out, dict)
    assert out == payload


def test_encrypt_decrypt_file_flow(temp_dir: Path):
    mgr = EncryptionManager()
    src = Path("sample.txt")
    src.write_text("file content", encoding="utf-8")

    enc_path = mgr.encrypt_file(src)
    assert enc_path.exists()
    assert enc_path.suffix == ".enc"

    dec_path = mgr.decrypt_file(enc_path)
    assert dec_path.exists()
    assert dec_path.read_text(encoding="utf-8") == "file content"


def test_rotate_keys_and_multi_decrypt(temp_dir: Path):
    mgr = EncryptionManager()
    token_old = mgr.encrypt("keep me")

    # rotate keys to ensure a new primary is added; keep both
    mgr.rotate_keys(max_keys=2)

    # Should still decrypt using MultiFernet
    out = mgr.decrypt(token_old)
    assert out == "keep me"


def test_reencrypt_file_and_directory(temp_dir: Path):
    mgr = EncryptionManager()
    directory = Path("vault")
    directory.mkdir()

    # Prepare two files
    for i in range(2):
        p = directory / f"f{i}.txt"
        p.write_text(f"data {i}", encoding="utf-8")
        mgr.encrypt_file(p)
        # remove plaintext
        p.unlink()

    # Now rotate keys and reencrypt directory
    mgr.rotate_keys(max_keys=3)
    success, total = mgr.reencrypt_directory(directory)
    assert total == 2
    assert success == 2


def test_encrypt_sensitive_and_decrypt_sensitive_data(temp_dir: Path):
    data = {
        "username": "bob",
        "password": "secret123",
        "token": None,  # None should be ignored
    }
    sensitive = ["password", "token"]

    enc = encrypt_sensitive_data(data, sensitive)
    assert enc["username"] == "bob"
    assert enc.get("password_encrypted") is True
    # base64 string stored
    enc_val = enc["password"]
    assert isinstance(enc_val, str)

    dec = decrypt_sensitive_data(enc)
    assert dec.get("password_encrypted") is None
    assert dec["password"] == "secret123"


def test_init_with_password_derivation_creates_keys(temp_dir: Path):
    # ensure no keys exist
    keys_dir = Path("config") / "encryption_keys"
    if keys_dir.exists():
        shutil.rmtree(keys_dir)

    mgr = EncryptionManager(password="passw0rd")
    # current_keys.json should be created
    key_file = keys_dir / "current_keys.json"
    assert key_file.exists()
    with open(key_file, "r") as f:
        serialized = json.load(f)
    assert isinstance(serialized, list) and len(serialized) >= 1
    # keys are base64 strings
    base64.b64decode(serialized[0]["key"])  # will raise if invalid


def test_reencrypt_directory_handles_empty_and_invalid_path(temp_dir: Path):
    mgr = EncryptionManager()

    empty_dir = Path("empty")
    empty_dir.mkdir()
    succ, tot = mgr.reencrypt_directory(empty_dir)
    assert (succ, tot) == (0, 0)

    # non-existing path -> method catches and returns (0,0)
    succ2, tot2 = mgr.reencrypt_directory(Path("no_such_dir"))
    assert (succ2, tot2) == (0, 0)
