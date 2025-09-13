import asyncio
import json
import os
import signal
from utils import hash_password, check_password
from monitor import start_monitor, stop_monitor
from ui import launch_ui, log_queue, set_ui_state

CONFIG_FILE = "config.json"
config = {}
sysop_logged_in = False
monitor_on = False

# === Utility ===

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_config():
    global config
    if not os.path.exists(CONFIG_FILE):
        return False
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    return True

def log(msg):
    log_queue.put(msg)

# === Command Handling ===

async def handle_command(command):
    global sysop_logged_in, monitor_on
    cmd = command.strip().lower()

    if cmd == "help":
        log("Available commands: HELP, MONITOR [ON|OFF], LOGIN, LOGOUT, WHOAMI, SHUTDOWN, RESTART")

    elif cmd.startswith("monitor"):
        parts = cmd.split()
        if len(parts) == 1:
            log(f"Monitor is {'ON' if monitor_on else 'OFF'}")
        elif parts[1] == "on":
            if not monitor_on:
                await start_monitor(config['direwolf_host'], config['direwolf_port'], log_queue)
                monitor_on = True
                set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "sysop" if sysop_logged_in else "anonymous")
                log("Monitor enabled")
            else:
                log("Monitor already ON")
        elif parts[1] == "off":
            if monitor_on:
                stop_monitor()
                monitor_on = False
                set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "sysop" if sysop_logged_in else "anonymous")
                log("Monitor disabled")
            else:
                log("Monitor already OFF")

    elif cmd == "whoami":
        log(f"You are {'sysop' if sysop_logged_in else 'anonymous'}")

    elif cmd == "logout":
        if sysop_logged_in:
            sysop_logged_in = False
            set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "anonymous")
            log("Logged out")
        else:
            log("You are not logged in")

    elif cmd == "login":
        password = input("Sysop password: ")
        if check_password(password, config.get("sysop_password", "")):
            sysop_logged_in = True
            set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "sysop")
            log("Login successful")
        else:
            log("Invalid password")

    elif cmd == "shutdown":
        if sysop_logged_in:
            log("Goodbye!")
            await asyncio.sleep(1)
            os._exit(0)
        else:
            log("Sysop access required for shutdown")

    elif cmd == "restart":
        if sysop_logged_in:
            log("Soft restarting...")
            await asyncio.sleep(1)
            main()
        else:
            log("Sysop access required for restart")

    else:
        log(f"Unknown command: {command}")

# === Config Wizard ===

async def config_wizard():
    print("=== First-Time Setup ===")
    config['callsign'] = input("Enter your station callsign: ").strip() or "N0CALL"

    while True:
        pw1 = input("Set sysop password: ").strip()
        pw2 = input("Verify password: ").strip()
        if not pw1 or pw1 != pw2:
            print("Passwords do not match or are empty. Try again.")
        else:
            break
    config['sysop_password'] = hash_password(pw1)

    config['direwolf_host'] = input("Direwolf host (default 127.0.0.1): ").strip() or "127.0.0.1"
    port_input = input("Direwolf TCP port (default 8001): ").strip()
    config['direwolf_port'] = int(port_input) if port_input else 8001

    log_pref = input("Enable file logging? (y/n): ").strip().lower()
    config['logging'] = log_pref == "y"
    if config['logging']:
        config['logfile'] = input("Log filename (default ywdtnc.log): ").strip() or "ywdtnc.log"

    save_config()

# === Main ===

def signal_handler(sig, frame):
    log("Shutting down...")
    stop_monitor()
    os._exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    if not load_config():
        asyncio.run(config_wizard())
        load_config()

    set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "anonymous")
    launch_ui(lambda cmd: asyncio.create_task(handle_command(cmd)), config.get("callsign", "N0CALL"))

if __name__ == "__main__":
    main()
