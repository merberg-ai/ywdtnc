#!/usr/bin/env python3
import asyncio
import sys
import signal
from tnc_state import TNCState

BANNER = "MFJ-1270 Python Emulator (MVP) 0.2 — CMD mode. Type HELP."

class Shell:
    def __init__(self, tnc: TNCState):
        self.tnc = tnc
        self.mode = "CMD"
        self._beacon_task = None
        self._rx_task = None

    async def start(self):
        print(BANNER)
        self._rx_task = asyncio.create_task(self.tnc.rx_loop())
        if self.tnc.beacon_every is not None:
            self._beacon_task = asyncio.create_task(self.tnc.beacon_loop())

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown()))

        while True:
            try:
                if self.mode == "CMD":
                    line = await self._ainput("cmd: ")
                    if not await self.handle_cmd(line.strip()):
                        break
                else:
                    line = await self._ainput("")
                    await self.tnc.send_converse_line(line)
            except EOFError:
                break

        await self.shutdown()

    async def shutdown(self):
        if self._beacon_task:
            self._beacon_task.cancel()
        if self._rx_task:
            self._rx_task.cancel()
        await self.tnc.close()
        raise SystemExit

    async def _ainput(self, prompt: str) -> str:
        print(prompt, end="", flush=True)
        return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

    async def handle_cmd(self, line: str) -> bool:
        if not line:
            return True
        cmd, *rest = line.split()
        ucmd = cmd.upper()

        if ucmd in ("QUIT", "EXIT", "BYE"):
            return False

        if ucmd == "HELP":
            self.print_help()
            return True

        if ucmd in ("CONVERSE", "C"):
            if not self.tnc.unproto_dest:
                print("UNPROTO not set. Example: UNPROTO CQ VIA WIDE1-1,WIDE2-1")
                return True
            print("*** CONNECTED to CONV (UI) — hit Ctrl-C to return to CMD.")
            self.mode = "CONV"
            try:
                await self.tnc.set_converse(True)
                while True:
                    await asyncio.sleep(3600)
            except KeyboardInterrupt:
                print("\n*** RETURN to CMD")
            finally:
                await self.tnc.set_converse(False)
                self.mode = "CMD"
            return True

        handled, msg = await self.tnc.handle_command(ucmd, " ".join(rest))
        if msg:
            print(msg)
        if not handled:
            print("Eh? (Unknown command). Type HELP.")
        return True

    def print_help(self):
        print(
            "TNC-2 style commands (MVP 0.2):\n"
            "  MYCALL <CALL>                   Set your callsign-SSID (e.g., N0CALL-7)\n"
            "  UNPROTO <DEST> [VIA PATH]       Set UI dest & digipeater path\n"
            "  MONITOR ON|OFF                  Toggle monitor of heard frames\n"
            "  TXDELAY <ms>                    Set TXDELAY (KISS)\n"
            "  BEACON EVERY <sec> TEXT <t>     Periodic UI beacon\n"
            "  CONNECT <CALL> [VIA PATH]       LAPB handshake (SABM/UA) to peer\n"
            "  DISCONNECT                      Send DISC and await UA\n"
            "  CONVERSE (or C)                 Enter converse (UI) mode\n"
            "  HELP                            This list\n"
            "  QUIT                            Exit\n"
        )

async def main():
    host = "127.0.0.1"
    port = 8001
    tnc = TNCState(host=host, port=port)
    await tnc.open()
    shell = Shell(tnc)
    await shell.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        pass
