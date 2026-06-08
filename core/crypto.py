"""端到端加密 —— AES-256-GCM + PBKDF2 密钥派生"""

import os, base64

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def is_crypto_available():
    return _CRYPTO_AVAILABLE


def derive_key(passphrase: str, salt: bytes = None) -> tuple:
    """从密码派生 AES-256 密钥，返回 (key, salt)"""
    if not _CRYPTO_AVAILABLE:
        raise ImportError("cryptography 库未安装，pip install cryptography")
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    key = kdf.derive(passphrase.encode())
    return key, salt


def encrypt_data(plaintext: str, key: bytes) -> str:
    """AES-256-GCM 加密，返回 base64(nonce+密文)"""
    if not _CRYPTO_AVAILABLE:
        raise ImportError("cryptography 库未安装")
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_data(encrypted: str, key: bytes) -> str:
    """解密，输入 base64(nonce+密文)"""
    if not _CRYPTO_AVAILABLE:
        raise ImportError("cryptography 库未安装")
    raw = base64.b64decode(encrypted)
    if len(raw) < 13:
        raise ValueError("密文数据过短")
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
