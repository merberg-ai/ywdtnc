import asyncio, sys, signal
from tnc_state import TNCState

HELP_TEXT = """Available commands:
  UNPROTO <DEST> [VIA DIGI...]   Set UNPROTO path
  RECONNECT                      Reconnect to Direwolf
  CONNECT <CALL>                 Establish link
  DISCONNECT                     Disconnect current link
  MONITOR ON|OFF                 Toggle monitor
  MONITOR DETAIL ON|OFF          Toggle hex dump
  CONVERSE                       Enter converse (UNPROTO send)
  CMD                            Return to command mode
  HELP                           Show this help
  EXIT                           Quit
"""

class Shell:
    def __init__(self,tnc): self.tnc=tnc; self.mode="CMD"; self._rx_task=None
    async def start(self):
        self._rx_task=asyncio.create_task(self.tnc.rx_loop())
        loop=asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT,self._sigint)
        while True:
            if self.mode=="CMD": line=await asyncio.to_thread(lambda: input("cmd: "))
            else: line=await asyncio.to_thread(sys.stdin.readline)
            line=line.strip()
            if not line: continue
            if self.mode=="CMD": await self._handle_cmd(line)
            elif self.mode=="CONV": await self._handle_conv(line)
            elif self.mode=="LINKED": await self._handle_linked(line)
    def _sigint(self): self.mode="CMD"; print("\n*** Break to CMD")
    async def _handle_cmd(self,line):
        parts=line.split(); cmd=parts[0].upper(); rest=" ".join(parts[1:])
        if cmd=="EXIT": await self.tnc.close(); sys.exit(0)
        if cmd=="HELP": print(HELP_TEXT); return
        if cmd=="CONVERSE": self.mode="CONV"; print("*** CONVERSE, ^C to exit"); return
        handled,msg=await self.tnc.handle_command(cmd,rest)
        if msg:
            if isinstance(msg,dict): print(msg["msg"]); 
            else: print(msg)
            if isinstance(msg,dict) and msg.get("linked"): 
                self.mode="LINKED"; print("*** LINKED, ^C to exit")
        if not handled and cmd=="MONITOR":
            arg=rest.upper()
            if arg=="ON": self.tnc.monitor_on=True; print("*** Monitor ON")
            elif arg=="OFF": self.tnc.monitor_on=False; print("*** Monitor OFF")
            elif arg.startswith("DETAIL"):
                if "ON" in arg: self.tnc.monitor_detail=True; print("*** Monitor DETAIL ON")
                else: self.tnc.monitor_detail=False; print("*** Monitor DETAIL OFF")
            else: print("Usage: MONITOR ON|OFF|DETAIL ON|OFF")
    async def _handle_conv(self,line): await self.tnc.send_converse_line(line)
    async def _handle_linked(self,line): await self.tnc.send_linked_line(line)

async def main():
    tnc=TNCState()
    if not await tnc.open(): return
    shell=Shell(tnc)
    await shell.start()

if __name__=="__main__": asyncio.run(main())
