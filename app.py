import os
import json
import signal
import asyncio

from monitor import start_monitor
from utils import hash_password, check_password
from ui import launch_ui, set_ui_state

CONFIG_FILE = "config.json"
config = {}
monitor_on = False
logged_in_user = "anonymous"
monitor_task = None

def load_config():
    global config
    if not os.path.exists(CONFIG_FILE):
        return False
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return True

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

async def config_wizard():
    print("=== Initial Configuration Wizard ===")
    config["system_callsign"] = input("Enter system callsign (e.g., KJ6YWD): ").strip()
    while True:
        pw = input("Set sysop password: ").strip()
        confirm = input("Confirm sysop password: ").strip()
        if not pw:
            print("Password cannot be blank.")
            continue
        if pw != confirm:
            print("Passwords do not match.")
            continue
        config["sysop_password"] = hash_password(pw)
        break

    host = input("Enter Direwolf host (default 127.0.0.1): ").strip()
    config["direwolf_host"] = host if host else "127.0.0.1"

    port = input("Enter Direwolf TCP port (default 8001): ").strip()
    try:
        config["direwolf_port"] = int(port) if port else 8001
    except ValueError:
        config["direwolf_port"] = 8001

    log_choice = input("Enable logging to file? (y/n): ").strip().lower()
    config["logging"] = log_choice == "y"
    config["log_file"] = "ywdtnc.log"

    save_config()
    print("Configuration saved.")

def log_to_file(msg):
    if config.get("logging"):
        with open(config.get("log_file", "ywdtnc.log"), "a") as f:
            f.write(msg + "\n")

async def handle_command(command):
    global monitor_on, monitor_task, logged_in_user

    command = command.strip()
    log_to_file(f"> {command}")
    if not command:
        return

    parts = command.split()
    cmd = parts[0].upper()

    if cmd == "HELP":
        ui_output("Available commands: MONITOR ON|OFF, LOGIN, LOGOUT, WHOAMI, SHUTDOWN, RESTART, EXIT")
        return

    if cmd == "MONITOR":
        if len(parts) == 2:
            if parts[1].upper() == "ON":
                if not monitor_on:
                    monitor_on = True
                    monitor_task = asyncio.create_task(start_monitor(config["direwolf_host"], config["direwolf_port"]))
                    ui_output("Monitor enabled.")
            elif parts[1].upper() == "OFF":
                if monitor_on:
                    monitor_on = False
                    if monitor_task:
                        monitor_task.cancel()
                    ui_output("Monitor disabled.")
        else:
            ui_output(f"Monitor is {'ON' if monitor_on else 'OFF'}.")

    elif cmd == "LOGIN":
        if logged_in_user == "sysop":
            ui_output("Already logged in as sysop.")
            return
        pw = input("Enter sysop password: ")
        if check_password(pw, config["sysop_password"]):
            logged_in_user = "sysop"
            set_ui_state(config.get("callsign", "N0CALL"), monitor_on, logged_in_user)
            ui_output("Login successful.")
        else:
            ui_output("Invalid credentials.")

    elif cmd == "LOGOUT":
        if logged_in_user == "anonymous":
            ui_output("You are not logged in.")
        else:
            logged_in_user = "anonymous"
            set_ui_state(config.get("callsign", "N0CALL"), monitor_on, logged_in_user)
            ui_output("Logged out.")

    elif cmd == "WHOAMI":
        ui_output(f"You are logged in as: {logged_in_user}")

    elif cmd == "SHUTDOWN":
        if logged_in_user != "sysop":
            ui_output("Sysop privileges required.")
            return
        ui_output("Shutting down... Goodbye.")
        raise urwid.ExitMainLoop()

    elif cmd == "RESTART":
        if logged_in_user != "sysop":
            ui_output("Sysop privileges required.")
            return
        ui_output("Restarting UI...")
        raise urwid.ExitMainLoop()  # Soft exit; app.py could be looped if desired

    elif cmd == "EXIT":
        ui_output("Use SHUTDOWN instead.")

    else:
        ui_output(f"Unknown command: {cmd}")

def ui_output(text):
    print(text)  # fallback
    if 'ui_output_hook' in globals():
        ui_output_hook(text)

def signal_handler(sig, frame):
    print("\nInterrupted. Exiting.")
    exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    if not load_config():
        asyncio.run(config_wizard())
        load_config()

    asyncio.set_event_loop(asyncio.new_event_loop())  # Ensure we have a running loop

    set_ui_state(config.get("callsign", "N0CALL"), monitor_on, "anonymous")

    def run_command(cmd):
        asyncio.get_event_loop().create_task(handle_command(cmd))

    launch_ui(run_command, config.get("callsign", "N0CALL"))

if __name__ == "__main__":
    main()
