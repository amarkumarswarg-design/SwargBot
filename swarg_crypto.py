"""
SWARG Crypto Engine
Exact same standard as hiamar.online (Web Crypto API):
- PBKDF2 (100,000 iterations, SHA-256) to derive key from password
- AES-256-GCM for encryption
- 30-minute expiry embedded in the payload
- Format: base64( salt[16] + iv[12] + ciphertext )

Because this matches the website's algorithm exactly, anything encrypted
on hiamar.online can be decrypted here (same password), and vice versa.
"""

import os
import json
import time
import base64

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT_LEN = 16
IV_LEN = 12
PBKDF2_ITERATIONS = 100_000
EXPIRY_SECONDS = 30 * 60  # 30 minutes, same as website


class SwargCryptoError(Exception):
    pass


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256-bit key
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(text: str, password: str) -> str:
    """Encrypt text with password. Returns base64 string (same format as website)."""
    if not text or not password:
        raise SwargCryptoError("Text and password are required")

    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = _derive_key(password, salt)

    payload = json.dumps({
        "t": text,
        "e": int(time.time() * 1000) + EXPIRY_SECONDS * 1000  # ms epoch, like Date.now()
    }).encode("utf-8")

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, payload, None)

    combined = salt + iv + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt(encrypted_b64: str, password: str) -> str:
    """Decrypt base64 string with password. Raises SwargCryptoError on failure/expiry."""
    if not encrypted_b64 or not password:
        raise SwargCryptoError("Encrypted text and password are required")

    try:
        combined = base64.b64decode(encrypted_b64)
    except Exception:
        raise SwargCryptoError("Invalid encrypted data (bad base64)")

    if len(combined) < SALT_LEN + IV_LEN:
        raise SwargCryptoError("Invalid encrypted data (too short)")

    salt = combined[:SALT_LEN]
    iv = combined[SALT_LEN:SALT_LEN + IV_LEN]
    ciphertext = combined[SALT_LEN + IV_LEN:]

    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        payload = aesgcm.decrypt(iv, ciphertext, None)
    except Exception:
        raise SwargCryptoError("Decryption failed. Invalid password or corrupted data.")

    data = json.loads(payload.decode("utf-8"))
    if int(time.time() * 1000) > data["e"]:
        raise SwargCryptoError("Expired! 30 minutes are over.")

    return data["t"]


if __name__ == "__main__":
    # Quick self-test
    enc = encrypt("Hello SWARG", "mypassword123")
    print("Encrypted:", enc)
    dec = decrypt(enc, "mypassword123")
    print("Decrypted:", dec)
    assert dec == "Hello SWARG"
    print("✅ Self-test passed")
