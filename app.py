import asyncio
import json
import os
from utils import hash_password, check_password

session = {'authenticated': False}

async def config_wizard():
    config = {}

    print("\n--- YWDTNC Configuration Wizard ---")

    config['callsign'] = input("Enter system callsign (e.g., KJ6YWD): ").strip()

    while True:
        password = input("Set sysop password: ").strip()
        if not password:
            print("Password cannot be empty.")
            continue
        confirm = input("Confirm password: ").strip()
        if password != confirm:
            print("Passwords do not match.")
        else:
            break
    config['sysop_password'] = hash_password(password)

    host = input("Enter Direwolf TCP host [127.0.0.1]: ").strip() or "127.0.0.1"
    port = input("Enter Direwolf TCP port [8001]: ").strip() or "8001"
    config['direwolf_host'] = host
    config['direwolf_port'] = int(port)

    log_choice = input("Enable logging to file? (y/n) [n]: ").strip().lower() or 'n'
    config['logging'] = log_choice == 'y'
    if config['logging']:
        log_name = input("Enter log filename [ywdtnc.log]: ").strip() or 'ywdtnc.log'
        config['logfile'] = log_name

    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

    print("[CONFIG] Saved to config.json")
    return config

async def handle_command(command, config):
    global session
    command = command.strip().upper()

    if command == "LOGIN":
        if session.get('authenticated'):
            print("[INFO] Already logged in.")
            return
        pw = input("Sysop password: ").strip()
        if check_password(pw, config.get('sysop_password', '')):
            session['authenticated'] = True
            print("[LOGIN] Authenticated as sysop.")
        else:
            print("[LOGIN] Invalid credentials.")

    elif command == "TESTLOGIN":
        pw = input("Enter password: ").strip()
        if check_password(pw, config['sysop_password']):
            print("✔ PASS: Correct password")
        else:
            print("❌ FAIL: Invalid password")

    elif command == "EXIT":
        print("[EXIT] Goodbye.")
        exit()

    else:
        print(f"[COMMAND] Unknown command: {command}")

async def main():
    if not os.path.exists("config.json"):
        config = await config_wizard()
    else:
        with open("config.json", "r") as f:
            config = json.load(f)

    print("Welcome to YWDTNC. Type LOGIN to authenticate.")
    while True:
        command = input("ywdtnc> ")
        await handle_command(command, config)

if __name__ == "__main__":
    asyncio.run(main())
