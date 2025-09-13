import os
import sys
from config import save_config, CONFIG_FILE

class TNCCommandParser:
    def __init__(self, kiss, config):
        self.kiss = kiss
        self.config = config

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

        else:
            print(f"Unknown command: {cmd}")

    def show_config(self):
        print("Current Configuration:")
        for k, v in self.config.items():
            print(f"  {k}: {v}")

    def print_help(self):
        print("Available commands:")
        print("  SHOW                     Show current config")
        print("  SET <KEY> <VALUE>        Set config key")
        print("  SAVE                     Save config to file")
        print("  RESET                    Delete config and re-run setup")
        print("  SHUTDOWN                 Gracefully exit (local console only)")
        print("  HELP                     Show this help message")

    def _is_local_console(self):
        """Basic check to verify we're in an interactive local console."""
        return sys.stdin.isatty() and sys.stdout.isatty()
