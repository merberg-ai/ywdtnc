import os
import json
import getpass
import hashlib
import binascii

CONFIG_FILE = "config.json"

def hash_password(password: str, salt: bytes = None) -> dict:
    if not salt:
        salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return {
        "salt": binascii.hexlify(salt).decode(),
        "hash": binascii.hexlify(hash_bytes).decode()
    }

def verify_password(stored: dict, password: str) -> bool:
    salt = binascii.unhexlify(stored["salt"])
    expected_hash = hash_password(password, salt)["hash"]
    return expected_hash == stored["hash"]

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("No config found. Launching first-time setup...")
        return first_time_setup()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print("Config saved.")

def first_time_setup():
    config = {}
    config["MYCALL"] = input("Enter system call sign (e.g., N0CALL): ").strip().upper()
    config["SYSOP"] = input("Enter sysop username: ").strip()
    raw_pw = getpass.getpass("Enter sysop password: ").strip()
    config["PASSWORD"] = hash_password(raw_pw)

    config["DIREWOLF_ADDR"] = input("Direwolf IP address [127.0.0.1]: ").strip() or "127.0.0.1"
    port_input = input("Direwolf port [8001]: ").strip()
    config["DIREWOLF_PORT"] = int(port_input) if port_input else 8001

    log_choice = input("Enable logging to file? [y/N]: ").strip().lower()
    config["LOGGING"] = log_choice == "y"
    config["LOGFILE"] = input("Log filename [ywdtnc.log]: ").strip() or "ywdtnc.log"

    save_config(config)
    return config
