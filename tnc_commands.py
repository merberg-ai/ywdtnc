import os
import sys
import getpass
from config import save_config, CONFIG_FILE, verify_password

class TNCCommandParser:
    def __init__(self, kiss, config):
        self.kiss = kiss
        self.config = config
        self.sysop_logged_in = False
        self.current_user = None

    async def handle_command(self, line: str):
        tokens = line.strip().split()
        if not tokens:
            return

        cmd = tokens[0].upper()

        if cmd == "HELP":
            self.print_help()

        elif cmd == "SHOW":
            self.show_config()

        elif cmd == "SET" and len(tokens) >= 3:
            key = tokens[1].upper()
            val = " ".join(tokens[2:])
            if key == "PASSWORD":
                print("Use the setup script to securely change password.")
            else:
                self.config[key] = val
                print(f"{key} set to {val}")

        elif cmd == "SAVE":
            save_config(self.config)

        elif cmd == "RESET":
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
                print("Config removed. Restart to re-run setup.")

        elif cmd == "SHUTDOWN":
            if self._is_local_console():
                print("Gracefully shutting down YWD-TNC... 73 and good DX!")
                sys.exit(0)
            else:
                print("SHUTDOWN is only available from the local console.")

        elif cmd == "RESTART":
            if self.sysop_logged_in:
                print("Soft restart initiated...\n")
                self.sysop_logged_in = False
                self.current_user = None
                print("System state reset. Awaiting new commands.")
            else:
                print("Sysop login required to restart.")

        elif cmd == "REBOOT":
            if self._authenticate_sysop():
                print("Rebooting YWD-TNC...\n")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                print("Sysop authentication failed. Reboot denied.")

        elif cmd == "LOGIN":
            self._login()

        elif cmd == "LOGOUT":
            self.sysop_logged_in = False
            self.current_user = None
            print("Logged out.")

        elif cmd == "WHOAMI":
            if self.sysop_logged_in:
                print(f"Logged in as: {self.current_user}")
            else:
                print("Not logged in.")

        else:
            print(f"Unknown command: {cmd}")

    def show_config(self):
        print("Current Configuration:")
        for k, v in self.config.items():
            masked = "[ENCRYPTED]" if k == "PASSWORD" else v
            print(f"  {k}: {masked}")

    def print_help(self):
        print("Available commands:")
        print("  SHOW                     Show current config")
        print("  SET <KEY> <VALUE>        Set config key")
        print("  SAVE                     Save config to file")
        print("  RESET                    Delete config and re-run setup")
        print("  SHUTDOWN                 Gracefully exit (local console only)")
        print("  RESTART                  Soft restart system state (sysop only)")
        print("  REBOOT                   Full system reboot (sysop only)")
        print("  LOGIN                    Authenticate as sysop")
        print("  LOGOUT                   End sysop session")
        print("  WHOAMI                   Show current logged-in user")
        print("  HELP                     Show this help message")

    def _is_local_console(self):
        return sys.stdin.isatty() and sys.stdout.isatty()

    def _authenticate_sysop(self):
        user = input("Sysop username: ").strip()
        pw = getpass.getpass("Sysop password: ").strip()
        return user == self.config.get("SYSOP") and verify_password(self.config["PASSWORD"], pw)

    def _login(self):
        if self.sysop_logged_in:
            print(f"Already logged in as: {self.current_user}")
            return
        user = input("Sysop username: ").strip()
        pw = getpass.getpass("Sysop password: ").strip()
        if user == self.config.get("SYSOP") and verify_password(self.config["PASSWORD"], pw):
            self.sysop_logged_in = True
            self.current_user = user
            print(f"Welcome, {user}. You are now logged in.")
        else:
            print("Invalid credentials.")
