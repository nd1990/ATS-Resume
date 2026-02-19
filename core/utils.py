from cryptography.fernet import Fernet
from django.conf import settings

def get_cipher_suite():
    return Fernet(settings.ENCRYPTION_KEY)

def encrypt_content(content: bytes) -> bytes:
    """Encrypts bytes content."""
    cipher_suite = get_cipher_suite()
    return cipher_suite.encrypt(content)

def decrypt_content(content: bytes) -> bytes:
    """Decrypts bytes content."""
    cipher_suite = get_cipher_suite()
    return cipher_suite.decrypt(content)
