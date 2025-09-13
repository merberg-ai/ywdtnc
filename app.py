import asyncio
import os
import json
import getpass
import signal
from kiss_tcp import KissTCP
from tnc_commands import TNCCommandParser
from ax25 import parse_ax25
from utils import hash_password, check_password
import logging

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

async def config_wizard():
    print("Welcome to ywdtnc v1.0 Configuration Wizard")
    config = {}
    config['system_call'] = input("Enter system call: ").strip()
    config['sysop_user'] = input("Enter sysop username: ").strip()
    while True:
        password = getpass.getpass("Enter sysop password: ")
        if password.strip() == "":
            print("Password cannot be empty.")
            continue
        confirm = getpass.getpass("Confirm sysop password: ")
        if password == confirm:
            break
        else:
            print("Passwords do not match. Try again.")
    config['sysop_password'] = hash_password(password)

    # 🧠 Prefill host default = 127.0.0.1
    host_input = input("Enter Direwolf LAN address (default 127.0.0.1): ").strip()
    config['direwolf_host'] = host_input if host_input else "127.0.0.1"

    # 🛠 Port with fallback to default 8001
    while True:
        port_input = input("Enter Direwolf TCP port (default 8001): ").strip()
        if port_input == "":
            config['direwolf_port'] = 8001
            break
        elif port_input.isdigit():
            config['direwolf_port'] = int(port_input)
            break
        else:
            print("Invalid port number. Please enter a numeric value.")

    log_pref = input("Enable logging to file? (y/n): ").strip().lower()
    config['logging'] = log_pref == 'y'
    config['logfile'] = "ywdtnc.log"
    save_config(config)
    return config

async def monitor_loop(kiss, config, parser):
    while parser.monitor_enabled:
        try:
            frame = await kiss.receive()
            if not frame:
                continue
            parsed = parse_ax25(frame)
            if "error" in parsed:
                continue
            if parsed["ctrl"] == 0x03 and parsed["pid"] == 0xF0:  # UI frame
                try:
                    text = parsed["payload"].decode(errors="replace")
                except:
                    text = "<binary>"
                print(f"[MON] {parsed['src']} > {parsed['dst']} [UI]: {text}")
                if config.get("logging"):
                    logging.info(f"[MON] {parsed['src']} > {parsed['dst']} [UI]: {text}")
        except Exception as e:
            print(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(1)

async def main():
    config = load_config()
    if not config:
        config = await config_wizard()

    if config.get("logging"):
        logging.basicConfig(filename=config.get("logfile", "ywdtnc.log"), level=logging.INFO)

    kiss = KissTCP(config['direwolf_host'], config['direwolf_port'])
    if await kiss.connect():
        print(f"[INFO] Connected to Direwolf at {config['direwolf_host']}:{config['direwolf_port']}")
    else:
        print("[ERROR] Could not connect to Direwolf.")
        return

    parser = TNCCommandParser(kiss, config)

    async def conditional_monitor():
        while True:
            if parser.monitor_enabled:
                await monitor_loop(kiss, config, parser)
            else:
                await asyncio.sleep(1)

    asyncio.create_task(conditional_monitor())

    def shutdown_handler(sig, frame):
        print("\n[SHUTDOWN] Goodbye.")
        os._exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)

    while True:
        try:
            cmd = input("> ")
            await parser.handle_command(cmd)
        except KeyboardInterrupt:
            shutdown_handler(None, None)

if __name__ == "__main__":
    asyncio.run(main())
