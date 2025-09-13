import os
import json
import getpass

CONFIG_FILE = "config.json"

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
    config["PASSWORD"] = getpass.getpass("Enter sysop password: ").strip()
    config["DIREWOLF_ADDR"] = input("Direwolf IP address [127.0.0.1]: ").strip() or "127.0.0.1"
    port_input = input("Direwolf port [8001]: ").strip()
    config["DIREWOLF_PORT"] = int(port_input) if port_input else 8001
    save_config(config)
    return config