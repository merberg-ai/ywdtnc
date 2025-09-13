import hashlib
import os

SALT_LENGTH = 16

def hash_password(password):
    salt = os.urandom(SALT_LENGTH)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return salt.hex() + ":" + pwd_hash.hex()

def check_password(password, stored_hash):
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        stored_bytes = bytes.fromhex(hash_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
        return pwd_hash == stored_bytes
    except Exception:
        return False
