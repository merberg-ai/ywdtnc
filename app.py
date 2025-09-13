import asyncio
import json
import os
import socket
import sys
import time
from utils import hash_password, check_password
from ax25_monitor import toggle_monitor, simulate_monitor_output, monitor_enabled

CONFIG_FILE = 'config.json'
LOGGED_IN_USER = None

def log(msg, config=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if config and config.get("logging", False):
        with open(config.get("logfile", "ywdtnc.log"), "a") as f:
            f.write(line + "\n")

def direwolf_check(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False

async def config_wizard():
    config = {}
    config['callsign'] = input("Enter system callsign (e.g., KJ6YWD): ").strip().upper() or "N0CALL"

    while True:
        password = input("Set sysop password: ").strip()
        confirm = input("Confirm password: ").strip()
        if not password:
            print("Password cannot be empty.")
        elif password != confirm:
            print("Passwords do not match.")
        else:
            config['sysop_password'] = hash_password(password)
            break

    config['direwolf_host'] = input("Enter Direwolf TCP host (default 127.0.0.1): ").strip() or "127.0.0.1"
    port_input = input("Enter Direwolf TCP port (default 8001): ").strip()
    config['direwolf_port'] = int(port_input) if port_input.isdigit() else 8001

    log_toggle = input("Enable logging to file? (y/n): ").lower().strip() == 'y'
    config['logging'] = log_toggle
    config['logfile'] = "ywdtnc.log"

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    return config

def show_help():
    print("\nAvailable Commands:")
    print("  LOGIN         - Log in as sysop")
    print("  LOGOUT        - Log out current user")
    print("  WHOAMI        - Show current user")
    print("  MONITOR ON    - Enable AX.25 packet monitor")
    print("  MONITOR OFF   - Disable packet monitor")
    print("  MONITOR       - Show monitor status")
    print("  SHUTDOWN      - Shutdown system (sysop only)")
    print("  RESTART       - Soft restart system (sysop only)")
    print("  HELP          - Show this help message")
    print("")

async def cli_loop(config):
    global LOGGED_IN_USER
    log(f"{config['callsign']} TNC-2 emulator ready.", config)
    while True:
        simulate_monitor_output()
        cmd = input("> ").strip().upper()

        if cmd == "EXIT":
            log("Use SHUTDOWN to quit.", config)

        elif cmd == "SHUTDOWN":
            if LOGGED_IN_USER != "sysop":
                log("Unauthorized. Login as sysop to shutdown.", config)
                continue
            log("Shutting down. 73!", config)
            sys.exit(0)

        elif cmd == "RESTART":
            if LOGGED_IN_USER != "sysop":
                log("Unauthorized. Login as sysop to restart.", config)
                continue
            log("Restarting session...", config)
            break

        elif cmd == "WHOAMI":
            log(f"Logged in as: {LOGGED_IN_USER or 'anonymous'}", config)

        elif cmd == "LOGOUT":
            LOGGED_IN_USER = None
            log("Logged out.", config)

        elif cmd.startswith("LOGIN") or cmd.startswith("TESTLOGIN"):
            password = input("Password: ").strip()
            if check_password(password, config['sysop_password']):
                LOGGED_IN_USER = "sysop"
                log("Login successful.", config)
            else:
                log("Invalid credentials.", config)

        elif cmd.startswith("MONITOR"):
            parts = cmd.split()
            if len(parts) == 2:
                toggle_monitor(parts[1])
            elif len(parts) == 1:
                print(f"[MONITOR] Status: {'ON' if monitor_enabled else 'OFF'}")
            else:
                print("Usage: MONITOR [ON|OFF]")

        elif cmd == "HELP":
            show_help()

        else:
            log(f"Unknown command: {cmd}. Type HELP for available commands.", config)

async def main():
    config = None
    if not os.path.exists(CONFIG_FILE):
        config = await config_wizard()
    else:
        with open(CONFIG_FILE) as f:
            config = json.load(f)

    if direwolf_check(config['direwolf_host'], config['direwolf_port']):
        log(f"Direwolf connected at {config['direwolf_host']}:{config['direwolf_port']}", config)
    else:
        log("Unable to connect to Direwolf.", config)

    while True:
        await cli_loop(config)

if __name__ == "__main__":
    asyncio.run(main())
