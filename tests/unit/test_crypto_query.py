import base64
import json
import asyncio

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from engine.crypto_query import (
    _salt_for_conversation,
    derive_aes256_gcm,
    b64u,
    b64d,
    ndjson_encrypted_stream,
)


def test_b64u_b64d_roundtrip():
    data = b"hello world\x00\xff"
    enc = b64u(data)
    assert isinstance(enc, str)
    dec = b64d(enc)
    assert dec == data


def test_salt_for_conversation_is_deterministic():
    s1 = _salt_for_conversation("conv-123")
    s2 = _salt_for_conversation("conv-123")
    s3 = _salt_for_conversation("other")
    assert s1 == s2
    assert s1 != s3
    assert len(s1) == 32  # sha256 digest length


def test_derive_aes256_gcm_key_length():
    shared_secret = b"\x00" * 32
    aes = derive_aes256_gcm(shared_secret, "conv-xyz")
    assert isinstance(aes, AESGCM)


def test_ndjson_encrypted_stream_packets_and_decrypt():
    async def _run():
        # Prepare a deterministic AESGCM using a fixed shared secret and conversation id
        shared_secret = b"sharedsecret0123456789abcdef!!"[:32]
        cid = "conv-test"
        aes = derive_aes256_gcm(shared_secret, cid)

        # Provide small thresholds to force multiple flushes
        tokens = ["hello ", "world", "! this ", "is ", "a ", "test"]

        # Use small max_tokens and max_bytes to ensure more than one packet
        agen = ndjson_encrypted_stream(
            cid,
            iter(tokens),
            aes,
            max_tokens=2,
            max_bytes=20,
            max_delay_ms=10,
        )

        lines = []
        async for line in agen:
            lines.append(line)

        # Should produce multiple NDJSON lines
        assert len(lines) >= 2

        # Parse and validate each packet and ensure we can decrypt back
        prev_seq = 0
        recovered = ""
        for line in lines:
            pkt = json.loads(line)
            assert pkt["type"] == "ciphertext"
            assert isinstance(pkt["seq"], int)
            assert pkt["seq"] > prev_seq
            prev_seq = pkt["seq"]
            # Validate IV and ciphertext are base64 strings that decode
            iv = base64.b64decode(pkt["iv"])  # should be 12 bytes
            assert len(iv) == 12
            ct = base64.b64decode(pkt["ciphertext"])  # includes auth tag
            # AAD must match the documented format
            aad = pkt["aad"].encode("utf-8")
            # Decrypt and append
            plaintext = aes.decrypt(iv, ct, aad)
            recovered += plaintext.decode("utf-8")

        # Original sequence concatenated should equal joined tokens
        assert recovered == "".join(tokens)

    asyncio.run(_run())


def test_ndjson_encrypted_stream_time_flush(monkeypatch):
    async def _run():
        # Force time-based flush by simulating max_delay_ms exceeded
        shared_secret = bytes(range(32))
        cid = "cid-time"
        aes = derive_aes256_gcm(shared_secret, cid)

        tokens = ["tick", "tock"]

        # Monkeypatch time.perf_counter to advance enough to trigger flush
        class _Counter:
            def __init__(self):
                self.v = 0.0
            def __call__(self):
                # Each call advances by 0.1s (100ms)
                self.v += 0.1
                return self.v

        monkeypatch.setattr("engine.crypto_query.time.perf_counter", _Counter())

        agen = ndjson_encrypted_stream(
            cid,
            iter(tokens),
            aes,
            max_tokens=100,   # ensure count threshold not hit
            max_bytes=10_000, # ensure size threshold not hit
            max_delay_ms=50,  # 50ms, our counter advances by 100ms per check
        )

        lines = [line async for line in agen]
        # Should have at least one flushed packet
        assert len(lines) >= 1

    asyncio.run(_run())
