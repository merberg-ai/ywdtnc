import hashlib
import os
import base64

def hash_password(password: str, salt: bytes = None) -> str:
    if not salt:
        salt = os.urandom(16)  # Generate a 16-byte random salt
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return base64.b64encode(salt + dk).decode()

def check_password(password: str, stored_hash: str) -> bool:
    try:
        decoded = base64.b64decode(stored_hash.encode())
        salt = decoded[:16]
        stored_dk = decoded[16:]
        new_dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
        return new_dk == stored_dk
    except Exception as e:
        print(f"[ERROR] Password check failed: {e}")
        return False
