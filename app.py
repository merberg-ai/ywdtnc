import asyncio
import logging
from kiss_tcp import KissTCP
from tnc_commands import TNCCommandParser
from config import load_config, save_config

async def monitor_loop(kiss: KissTCP):
    while True:
        try:
            frame = await kiss.receive()
            if frame:
                hex_str = " ".join(f"{b:02X}" for b in frame)
                print(f"[RAW] {hex_str}")
                logging.info(f"[RAW] {hex_str}")
        except Exception as e:
            print(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(1)

async def main():
    config = load_config()

    if config.get("LOGGING", False):
        logfile = config.get("LOGFILE", "ywdtnc.log")
        logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    else:
        logging.basicConfig(level=logging.CRITICAL)

    kiss = KissTCP(config["DIREWOLF_ADDR"], config["DIREWOLF_PORT"])

    success = await kiss.connect()
    if success:
        logging.info(f"Direwolf connection successful: {config['DIREWOLF_ADDR']}:{config['DIREWOLF_PORT']}")
        print(f"[INFO] Connected to Direwolf at {config['DIREWOLF_ADDR']}:{config['DIREWOLF_PORT']}")
    else:
        logging.error("Direwolf connection failed.")
        print(f"[ERROR] Could not connect to Direwolf at {config['DIREWOLF_ADDR']}:{config['DIREWOLF_PORT']}")

    print("YWD-TNC (Python TAPR TNC-2 Emulator)")
    print("Version 1.0 by KJ6YWD")
    print("Type 'help' for available commands.\n")

    parser = TNCCommandParser(kiss, config)

    # Start live packet monitor in background
    asyncio.create_task(monitor_loop(kiss))

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
