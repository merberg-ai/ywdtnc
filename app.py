#!/usr/bin/env python3
import asyncio
import sys
import signal
from tnc_state import TNCState

BANNER = "MFJ-1270 Python Emulator (MVP) 0.5 — CMD mode. Type HELP."

class Shell:
    def __init__(self, tnc: TNCState):
        self.tnc = tnc
        self.mode = "CMD"
        self._beacon_task = None
        self._rx_task = None

    async def start(self):
        print(BANNER)
        await self.tnc.open()
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
                elif self.mode == "CONV":
                    line = await self._ainput("")
                    await self.tnc.send_converse_line(line)
                elif self.mode == "LINKED":
                    line = await self._ainput("")
                    await self.tnc.send_linked_line(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                if self.mode in ("CONV", "LINKED"):
                    print("\n*** RETURN to CMD")
                    self.mode = "CMD"
                else:
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
            if isinstance(msg, dict):
                print(msg["msg"])
                if msg.get("linked"):
                    print("*** LINKED session active — hit Ctrl-C to return to CMD.")
                    self.mode = "LINKED"
            else:
                print(msg)
        if ucmd == "DISCONNECT":
            self.mode = "CMD"
        if not handled:
            print("Eh? (Unknown command). Type HELP.")
        return True

    def print_help(self):
        print(
            "TNC-2 style commands (MVP 0.5):\n"
            "  MYCALL <CALL>                   Set your callsign-SSID (e.g., N0CALL-7)\n"
            "  UNPROTO <DEST> [VIA PATH]       Set UI dest & digipeater path\n"
            "  UNPROTO <message>               Send one UI frame using current UNPROTO path\n"
            "  CONNECT <CALL> [VIA PATH]       Start LAPB link, enter LINKED mode on success\n"
            "  DISCONNECT                      Send DISC, return to CMD mode\n"
            "  MONITOR ON|OFF                  Toggle monitor of heard frames\n"
            "  MONITOR DETAIL ON|OFF           Toggle hex dump alongside decoded text\n"
            "  TXDELAY <ms>                    Set TXDELAY (KISS)\n"
            "  BEACON EVERY <sec> TEXT <t>     Periodic UI beacon\n"
            "  CONVERSE (or C)                 Enter converse (UI) mode\n"
            "  RECONNECT                       Reconnect to Direwolf using mfj1270.ini\n"
            "  HELP                            This list\n"
            "  QUIT                            Exit\n"
        )

async def main():
    tnc = TNCState()
    shell = Shell(tnc)
    await shell.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        pass
