import crypto from "crypto";

export function base32Decode(str: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = 0;
  let value = 0;
  let index = 0;
  const output = Buffer.alloc(Math.ceil((str.length * 5) / 8));
  for (let i = 0; i < str.length; i++) {
    const val = alphabet.indexOf(str[i].toUpperCase());
    if (val === -1) continue;
    value = (value << 5) | val;
    bits += 5;
    if (bits >= 8) {
      output[index++] = (value >>> (bits - 8)) & 255;
      bits -= 8;
    }
  }
  return output.subarray(0, index);
}

export function generateTotp(secret: string, offsetSeconds: number = 0): string {
  const key = base32Decode(secret.trim().replace(/\s+/g, ""));
  const epoch = Math.floor(Date.now() / 1000) + offsetSeconds;
  const time = Math.floor(epoch / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(time));
  const hmac = crypto.createHmac("sha1", key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const code = (hmac.readUInt32BE(offset) & 0x7fffffff) % 1000000;
  return code.toString().padStart(6, "0");
}

