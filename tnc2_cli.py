import asyncio
from kiss_tcp import KissTCP
from tnc_commands import TNCCommandParser
from config import load_config, save_config

async def main():
    config = load_config()
    kiss = KissTCP(config["DIREWOLF_ADDR"], config["DIREWOLF_PORT"])
    await kiss.connect()

    print("YWD-TNC (Python TAPR TNC-2 Emulator)")
    print("Version 1.0 by KJ6YWD")
    print("Type 'help' for available commands.\n")

    parser = TNCCommandParser(kiss, config)

    while True:
        try:
            line = input("> ").strip()
            if line.lower() in ["exit", "quit"]:
                print("Exiting.")
                break
            await parser.handle_command(line)
        except (KeyboardInterrupt, EOFError):
            print("\nInterrupted.")
            break

    await kiss.close()
    save_config(config)

if __name__ == "__main__":
    asyncio.run(main())