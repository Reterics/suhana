import asyncio
import base64, hashlib
import json, os, time

from typing import AsyncGenerator, Iterator

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def _salt_for_conversation(conversation_id: str) -> bytes:
    return hashlib.sha256(f"chat-stream-v1:{conversation_id}".encode("utf-8")).digest()

def _derive_aes256_gcm(shared_secret: bytes, conversation_id: str) -> AESGCM:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_salt_for_conversation(conversation_id),
        info=b"e2ee-stream/aes-gcm",
    )
    key = hkdf.derive(shared_secret)
    return AESGCM(key)

def _b64u(data: bytes) -> str:
    # standard b64 is fine; keep consistent with client
    return base64.b64encode(data).decode("ascii")

def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

async def _ndjson_encrypted_stream(
    conversation_id: str,
    token_iter: Iterator[str],
    aesgcm: AESGCM,
    *,
    max_tokens: int = 20,       # ~10–50 is a good range
    max_bytes: int = 2048,      # ~1–4 KB
    max_delay_ms: int = 40      # 25–50 ms feels realtime
) -> AsyncGenerator[str, None]:
    buf: list[str] = []
    buf_bytes = 0
    seq = 0
    last_flush = time.perf_counter()

    async def flush():
        nonlocal buf, buf_bytes, seq, last_flush
        if not buf:
            return
        payload = ("".join(buf)).encode("utf-8")
        iv = os.urandom(12)
        seq += 1
        aad_str = f"cid={conversation_id};seq={seq}"
        ct = aesgcm.encrypt(iv, payload, aad_str.encode("utf-8"))
        packet = {
            "type": "ciphertext",
            "seq": seq,
            "iv": _b64u(iv),
            "ciphertext": _b64u(ct),
            "aad": aad_str,
        }
        buf = []
        buf_bytes = 0
        last_flush = time.perf_counter()
        # yield one NDJSON line
        yield json.dumps(packet, separators=(",", ":")) + "\n"
    for tok in token_iter:
        buf.append(tok)
        buf_bytes += len(tok.encode("utf-8"))

        # count/size trigger
        if len(buf) >= max_tokens or buf_bytes >= max_bytes:
            async for line in flush():
                yield line
            # give event loop a chance to push bytes
            await asyncio.sleep(0)

        # time trigger
        elif (time.perf_counter() - last_flush) * 1000 >= max_delay_ms:
            async for line in flush():
                yield line
            await asyncio.sleep(0)

    async for line in flush():
        yield line


