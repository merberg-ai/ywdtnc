import asyncio
import json
import os
import signal
from ui import launch_ui, set_ui_state
from monitor import start_monitoring
from utils import hash_password, check_password

CONFIG_FILE = "config.json"
config = {}
monitor_on = False
command_queue = asyncio.Queue()
current_user = "anonymous"
logged_in = False

def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return True
    return False

async def config_wizard():
    print("=== YWDTNC Config Wizard ===")
    config['callsign'] = input("Enter your callsign: ").strip().upper() or "N0CALL"
    while True:
        pw = input("Set sysop password: ").strip()
        pw2 = input("Confirm password: ").strip()
        if pw and pw == pw2:
            break
        print("Passwords do not match or are empty. Try again.")
    config['sysop_password'] = hash_password(pw)
    config['direwolf_host'] = input("Direwolf host [127.0.0.1]: ").strip() or "127.0.0.1"
    port = input("Direwolf port [8001]: ").strip()
    config['direwolf_port'] = int(port) if port else 8001
    config['logging'] = input("Enable logging? (y/n) [n]: ").strip().lower() == 'y'
    config['log_file'] = input("Log file name [ywdtnc.log]: ").strip() or "ywdtnc.log"
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print("Config saved.\n")

async def handle_command(cmd):
    global monitor_on, current_user, logged_in
    parts = cmd.strip().split()
    if not parts:
        return
    command = parts[0].lower()

    if command == "help":
        set_ui_state(config.get("callsign", "N0CALL"), monitor_on, current_user)
        print("Commands: LOGIN, LOGOUT, WHOAMI, MONITOR ON/OFF, HELP, EXIT")
    elif command == "login":
        if logged_in:
            print("Already logged in.")
            return
        pw = input("Sysop password: ").strip()
        if check_password(config.get('sysop_password', ''), pw):
            current_user = "sysop"
            logged_in = True
            print("Logged in as sysop.")
        else:
            print("Invalid credentials.")
    elif command == "logout":
        current_user = "anonymous"
        logged_in = False
        print("Logged out.")
    elif command == "whoami":
        print(f"You are: {current_user}")
    elif command == "monitor":
        if len(parts) > 1:
            state = parts[1].lower()
            if state == "on":
                monitor_on = True
                print("Monitor enabled.")
            elif state == "off":
                monitor_on = False
                print("Monitor disabled.")
        else:
            print(f"Monitor is currently {'ON' if monitor_on else 'OFF'}")
    elif command == "exit":
        print("Goodbye.")
        os._exit(0)
    else:
        print(f"Unknown command: {command}")

async def command_loop():
    while True:
        cmd = await command_queue.get()
        await handle_command(cmd)

def signal_handler(sig, frame):
    print("\nExiting YWDTNC...")
    os._exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    if not load_config():
        asyncio.run(config_wizard())
        load_config()

    set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "anonymous")

    loop = asyncio.get_event_loop()
    loop.create_task(command_loop())
    launch_ui(command_queue, config.get("callsign", "N0CALL"))
    loop.run_forever()

if __name__ == "__main__":
    main()
