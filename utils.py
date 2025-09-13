import hashlib
import os

def hash_password(password):
    salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + hashed.hex()

def check_password(password, stored):
    try:
        salt_hex, hashed_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return hashed.hex() == hashed_hex
    except Exception:
        return False
