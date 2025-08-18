import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { consumeEncryptedStream } from './client-stream';

// Simple base64 helpers mirroring the module's behavior
const b64 = (buf: Uint8Array) => btoa(String.fromCharCode(...buf));

function makeStreamReaderFromString(s: string) {
  const enc = new TextEncoder().encode(s);
  let called = 0;
  return {
    read: vi.fn().mockImplementation(async () => {
      if (called === 0) {
        called++;
        return { value: enc, done: false };
      }
      return { value: undefined, done: true };
    })
  };
}

describe('consumeEncryptedStream', () => {
  const originalFetch = globalThis.fetch;
  let decryptImpl: (params: { iv: Uint8Array; ct: Uint8Array; aad?: Uint8Array }) => ArrayBuffer | Promise<ArrayBuffer>;

  beforeEach(() => {
    // Mock WebCrypto subtle API used in client-stream by spying on existing methods
    decryptImpl = () => new TextEncoder().encode('PLAINTEXT');

    const subtle = globalThis.crypto?.subtle as any;

    vi.spyOn(subtle, 'generateKey').mockResolvedValue({
      publicKey: { __pub: true },
      privateKey: { __priv: true }
    });

    vi.spyOn(subtle, 'exportKey').mockResolvedValue(new Uint8Array([1, 2, 3]).buffer);

    vi.spyOn(subtle, 'importKey').mockImplementation(async (_format: string, _data: any, algo: any) => {
      // HKDF import vs X25519 import
      if (algo === 'HKDF') return { __hkdf: true } as any;
      return { __peerPub: true } as any;
    });

    vi.spyOn(subtle, 'deriveBits').mockResolvedValue(new Uint8Array(32).buffer);

    vi.spyOn(subtle, 'deriveKey').mockImplementation(async () => ({ __aesKey: true } as any));

    vi.spyOn(subtle, 'decrypt').mockImplementation(async (_alg: any, _key: any, _ct: ArrayBuffer) => {
      // our test-controlled decrypt implementation
      const res = await decryptImpl({ iv: new Uint8Array(), ct: new Uint8Array(new Uint8Array(_ct)) as any });
      return res as ArrayBuffer;
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch as any;
    vi.restoreAllMocks();
  });

  it('handles server_pubkey then ciphertext messages and calls onText for each decrypted chunk', async () => {
    // Prepare mock stream with newline-delimited JSON
    const serverPub = b64(new Uint8Array([4, 5, 6]));
    const line1 = JSON.stringify({ type: 'server_pubkey', pubkey: serverPub });
    const line2 = JSON.stringify({ type: 'ciphertext', iv: b64(new Uint8Array([7, 7, 7])), ciphertext: b64(new Uint8Array([9, 9, 9])), seq: 1 });
    const line3 = JSON.stringify({ type: 'ciphertext', iv: b64(new Uint8Array([8, 8, 8])), ciphertext: b64(new Uint8Array([10, 10, 10])), seq: 2 });
    const payload = `${line1}\n${line2}\n${line3}\n`;

    const getReader = () => makeStreamReaderFromString(payload);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader }
    }) as any;

    const chunks: string[] = [];
    await consumeEncryptedStream('/stream', 'KEY', 'cid-123', t => chunks.push(t), JSON.stringify({ hello: 'world' }));

    expect(globalThis.fetch).toHaveBeenCalledWith('/stream', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'X-Client-PubKey': expect.any(String), 'Content-Type': 'application/json', 'x-api-key': 'KEY' }),
      body: expect.any(String)
    }));

    expect(chunks).toEqual(['PLAINTEXT', 'PLAINTEXT']);
  });

  it('continues when a decrypt fails and logs a warning', async () => {
    // First ciphertext decrypt throws, second succeeds
    let call = 0;
    decryptImpl = vi.fn().mockImplementation(async () => {
      call++;
      if (call === 1) throw new Error('bad tag');
      return new TextEncoder().encode('OK');
    });
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const serverPub = b64(new Uint8Array([1]));
    const line1 = JSON.stringify({ type: 'server_pubkey', pubkey: serverPub });
    const line2 = JSON.stringify({ type: 'ciphertext', iv: b64(new Uint8Array([2])), ciphertext: b64(new Uint8Array([3])), seq: 1 });
    const line3 = JSON.stringify({ type: 'ciphertext', iv: b64(new Uint8Array([4])), ciphertext: b64(new Uint8Array([5])), seq: 2 });
    const payload = `${line1}\n${line2}\n${line3}\n`;

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => makeStreamReaderFromString(payload) }
    }) as any;

    const chunks: string[] = [];
    await consumeEncryptedStream('/s', '', 'cid', t => chunks.push(t));

    expect(warnSpy).toHaveBeenCalled();
    expect(chunks).toEqual(['OK']);
  });

  it('throws when response is not ok or body missing', async () => {
    // Not ok
    globalThis.fetch = vi.fn().mockResolvedValueOnce({ ok: false }) as any;
    await expect(consumeEncryptedStream('/bad', '', 'cid', () => {})).rejects.toThrow(/stream failed/);

    // Missing body
    globalThis.fetch = vi.fn().mockResolvedValueOnce({ ok: true, body: null }) as any;
    await expect(consumeEncryptedStream('/bad2', '', 'cid', () => {})).rejects.toThrow(/stream failed/);
  });
});
