import os
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# Encryption key file path
ENCRYPTION_KEY_FILE = ".encryption_key"


def _get_or_create_encryption_key() -> bytes:
    """Get Fernet encryption key from env var (production) or local file (dev).

    On Railway/production: set the FERNET_KEY environment variable to a stable
    base64-encoded Fernet key so the key survives redeployments.  Generate one
    with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    Local dev: falls back to reading/creating the .encryption_key file.
    """
    env_key = os.getenv("FERNET_KEY")
    if env_key:
        return env_key.encode()
    if os.path.exists(ENCRYPTION_KEY_FILE):
        with open(ENCRYPTION_KEY_FILE, "rb") as f:
            return f.read()
    # Local dev only — generate and persist
    key = Fernet.generate_key()
    with open(ENCRYPTION_KEY_FILE, "wb") as f:
        f.write(key)
    logger.info("Generated new encryption key")
    return key


# Get encryption key on module load
try:
    _ENCRYPTION_KEY = _get_or_create_encryption_key()
    _CIPHER = Fernet(_ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"Failed to initialize encryption: {str(e)}")
    _CIPHER = None


def encrypt_key(plain_key: str) -> str:
    """
    Encrypt an API key

    Args:
        plain_key: Plain text API key

    Returns:
        Encrypted key as string

    Raises:
        RuntimeError: If encryption is not available
    """
    if not _CIPHER:
        raise RuntimeError("Encryption not available")

    encrypted = _CIPHER.encrypt(plain_key.encode())
    return encrypted.decode()


def decrypt_key(encrypted_key: str) -> str:
    """
    Decrypt an API key

    Args:
        encrypted_key: Encrypted key as string

    Returns:
        Decrypted plain text key

    Raises:
        RuntimeError: If decryption fails
    """
    if not _CIPHER:
        raise RuntimeError("Encryption not available")

    try:
        decrypted = _CIPHER.decrypt(encrypted_key.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt key: {str(e)}")
        raise RuntimeError(f"Decryption failed: {str(e)}")
