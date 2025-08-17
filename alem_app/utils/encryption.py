
import base64
import json
import os as _os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_key(password: str, salt: bytes, iterations: int = 390000) -> Optional[bytes]:
    """Derive a Fernet-compatible key from a password and salt."""
    if PBKDF2HMAC is None or base64 is None:
        return None
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_content(plain_text: str, password: str, iterations: int) -> str:
    """Encrypt content; returns JSON string containing metadata and ciphertext."""
    if Fernet is None:
        raise RuntimeError("Encryption support not available. Install 'cryptography'.")
    salt = _os.urandom(16)
    key = _derive_key(password, salt, iterations)
    f = Fernet(key)
    token = f.encrypt(plain_text.encode('utf-8'))
    payload = {
        'enc': True,
        'alg': 'fernet-pbkdf2',
        'it': iterations,
        'salt': base64.urlsafe_b64encode(salt).decode('ascii'),
        'ct': token.decode('ascii')
    }
    return json.dumps(payload)


def decrypt_content(enc_payload: str, password: str) -> str:
    """Decrypt JSON payload back to plaintext."""
    if Fernet is None:
        raise RuntimeError("Encryption support not available. Install 'cryptography'.")
    data = json.loads(enc_payload)
    if not data.get('enc'):
        return enc_payload
    salt = base64.urlsafe_b64decode(data['salt'])
    iterations = int(data.get('it', 390000))
    key = _derive_key(password, salt, iterations)
    f = Fernet(key)
    try:
        pt = f.decrypt(data['ct'].encode('ascii'))
        return pt.decode('utf-8')
    except InvalidToken:
        raise ValueError("Invalid password")
