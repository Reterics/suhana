
const b64 = (buf: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(buf instanceof Uint8Array ? buf : new Uint8Array(buf))));
const ub64 = (s: string) => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function saltFromConversationId(conversationId: string): Promise<ArrayBuffer> {
  return crypto.subtle.digest("SHA-256", new TextEncoder().encode("chat-stream-v1:" + conversationId));
}

async function generateX25519() {
  const kp = await crypto.subtle.generateKey(
    { name: "X25519", namedCurve: "X25519" },
    true,
    ["deriveBits"]
  );
  const rawPub = await crypto.subtle.exportKey("raw", kp.publicKey);
  return { privateKey: kp.privateKey, rawPublicKey: new Uint8Array(rawPub) };
}

async function importPeerX25519(raw: Uint8Array) {
  return crypto.subtle.importKey("raw", raw, { name: "X25519", namedCurve: "X25519" }, false, []);
}

async function deriveAesKey(myPriv: CryptoKey, peerPub: CryptoKey, conversationId: string): Promise<CryptoKey> {
  const bits = await crypto.subtle.deriveBits({ name: "X25519", public: peerPub }, myPriv, 256);
  const hkdfKey = await crypto.subtle.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
  const salt = await saltFromConversationId(conversationId);
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt, info: new TextEncoder().encode("e2ee-stream/aes-gcm") },
    hkdfKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
}

export async function consumeEncryptedStream(
  url: string,
  apiKey: string,
  conversationId: string,
  onText: (text: string) => void,
  body?: string | ArrayBuffer | null,
) {
  const { privateKey, rawPublicKey } = await generateX25519();
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "X-Client-PubKey": b64(rawPublicKey),
      'Content-Type': 'application/json',
        ...(apiKey ? { 'x-api-key': apiKey } : {})
    },
    body: body,
  });
  if (!resp.ok || !resp.body) throw new Error("stream failed");

  const reader = resp.body.getReader();
  const textDecoder = new TextDecoder();
  let buf = "";
  let aesKey: CryptoKey | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += textDecoder.decode(value, { stream: true });

    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      const msg = JSON.parse(line);

      if (msg.type === "server_pubkey") {
        const serverPub = await importPeerX25519(ub64(msg.pubkey));
        aesKey = await deriveAesKey(privateKey, serverPub, conversationId);
        continue;
      }

      if (msg.type === "ciphertext" && aesKey) {
        try {
          const iv = ub64(msg.iv);
          const ct = ub64(msg.ciphertext);
          const aad = new TextEncoder().encode(msg.aad ?? `cid=${conversationId};seq=${msg.seq}`);
          const pt = await crypto.subtle.decrypt(
            { name: "AES-GCM", iv, additionalData: aad },
            aesKey,
            ct
          );
          onText(new TextDecoder().decode(pt));
        } catch (e) {
          // bad tag or wrong context — ignore
          console.warn("decrypt failed", e);
        }
      }
    }
  }
}
