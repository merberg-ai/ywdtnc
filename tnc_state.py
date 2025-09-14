import asyncio, configparser, os
from kiss import KISSClient
from ax25 import (
    build_ui_frame, build_u_frame, build_i_frame,
    parse_ax25, CTL_UI, CTL_SABM, CTL_UA, CTL_DISC, CTL_DM
)

CFG_FILE = "mfj1270.ini"

class TNCState:
    def __init__(self):
        self.kiss_host, self.kiss_port = "127.0.0.1", 8001
        self.kiss: KISSClient | None = None
        self.mycall = "N0CALL"
        self.unproto_dest, self.unproto_path = None, []
        self.monitor_on, self.monitor_detail = True, False
        self.beacon_every, self.beacon_text, self.txdelay_ms = None, None, None
        self.converse = False
        self.link_up, self.link_peer, self.link_path = False, None, []
        self._ua_event, self._disc_ua_event = asyncio.Event(), asyncio.Event()
        self._send_ns = 0
        self._load_config()

    def _load_config(self):
        cfg = configparser.ConfigParser()
        if os.path.exists(CFG_FILE):
            cfg.read(CFG_FILE)
            sect = cfg.get("tnc", {})
            self.mycall = cfg.get("tnc", "mycall", fallback=self.mycall)
            self.unproto_dest = cfg.get("tnc", "unproto_dest", fallback=None) or None
            p = cfg.get("tnc", "unproto_path", fallback="")
            self.unproto_path = [x for x in p.split(",") if x] if p else []
            self.monitor_on = cfg.getboolean("tnc", "monitor_on", fallback=True)
            self.monitor_detail = cfg.getboolean("tnc", "monitor_detail", fallback=False)
            self.txdelay_ms = cfg.getint("tnc", "txdelay_ms", fallback=None)
            be = cfg.get("tnc", "beacon_every", fallback="").strip()
            self.beacon_every = int(be) if be else None
            bt = cfg.get("tnc", "beacon_text", fallback=None)
            self.beacon_text = bt.encode() if bt else None
            self.kiss_host = cfg.get("tnc", "kiss_host", fallback=self.kiss_host)
            self.kiss_port = cfg.getint("tnc", "kiss_port", fallback=self.kiss_port)

    def _save_config(self):
        cfg = configparser.ConfigParser()
        cfg["tnc"] = {
            "mycall": self.mycall,
            "unproto_dest": self.unproto_dest or "",
            "unproto_path": ",".join(self.unproto_path),
            "monitor_on": str(self.monitor_on).lower(),
            "monitor_detail": str(self.monitor_detail).lower(),
            "txdelay_ms": str(self.txdelay_ms or ""),
            "beacon_every": str(self.beacon_every or ""),
            "beacon_text": self.beacon_text.decode() if self.beacon_text else "",
            "kiss_host": self.kiss_host, "kiss_port": str(self.kiss_port),
        }
        with open(CFG_FILE,"w") as f: cfg.write(f)

    async def open(self):
        try:
            self.kiss = KISSClient(self.kiss_host,self.kiss_port)
            await self.kiss.open()
            if self.txdelay_ms: await self.kiss.set_txdelay(self.txdelay_ms)
            print(f"*** Connected to Direwolf {self.kiss_host}:{self.kiss_port}")
            return True
        except Exception as e:
            print(f"*** ERROR: Cannot connect to Direwolf: {e}")
            self.kiss=None; return False

    async def close(self): 
        if self.kiss: await self.kiss.close(); self.kiss=None
    async def reconnect(self): await self.close(); self._load_config(); return await self.open()
    async def set_converse(self,on:bool): self.converse=on

    async def handle_command(self,cmd:str,rest:str):
        if cmd=="UNPROTO":
            parts=rest.split()
            if not parts: return True,"Usage: UNPROTO <DEST> [VIA DIGI1,...]"
            self.unproto_dest=parts[0].upper()
            if len(parts)>=2 and parts[1].upper()=="VIA":
                self.unproto_path=[p.strip().upper().rstrip(",") for p in parts[2:]]
            self._save_config()
            return True,f"UNPROTO set {self.unproto_dest} via {','.join(self.unproto_path)}"
        if cmd=="RECONNECT":
            ok=await self.reconnect()
            return True,"*** Reconnected" if ok else "*** Reconnect failed"
        if cmd=="CONNECT":
            self.link_peer=rest.split()[0].upper() if rest else None
            self._ua_event.clear(); sabm=build_u_frame(self.mycall,self.link_peer,[],CTL_SABM)
            if not self.kiss: return True,"KISS not connected"
            for _ in range(3):
                await self.kiss.send_data(sabm)
                try:
                    await asyncio.wait_for(self._ua_event.wait(),timeout=5)
                    self.link_up=True
                    return True,{"msg":f"*** CONNECTED to {self.link_peer}","linked":True}
                except asyncio.TimeoutError: continue
            return True,"*** CONNECT failed"
        if cmd=="DISCONNECT":
            if not self.link_up: return True,"*** No active connection"
            self._disc_ua_event.clear()
            disc=build_u_frame(self.mycall,self.link_peer,[],CTL_DISC)
            if not self.kiss: return True,"KISS not connected"
            await self.kiss.send_data(disc)
            try:
                await asyncio.wait_for(self._disc_ua_event.wait(),timeout=5)
                peer=self.link_peer; self.link_up=False; self.link_peer=None
                return True,f"*** DISCONNECTED from {peer}"
            except asyncio.TimeoutError: return True,"*** DISCONNECT timeout"
        return False,None

    async def send_linked_line(self,line:str):
        if not self.link_up: print("*** Not connected"); return
        info=line.encode(); ns=self._send_ns; nr=0; self._send_ns=(self._send_ns+1)%8
        frame=build_i_frame(self.mycall,self.link_peer,[],ns,nr,info)
        if self.kiss: await self.kiss.send_data(frame)

    async def send_converse_line(self,line:str):
        if not self.unproto_dest: print("UNPROTO not set."); return
        frame=build_ui_frame(self.mycall,self.unproto_dest,self.unproto_path,line.encode())
        if self.kiss: await self.kiss.send_data(frame)

    async def beacon_loop(self):
        while self.beacon_every:
            if self.beacon_text and self.unproto_dest and self.kiss:
                frame=build_ui_frame(self.mycall,self.unproto_dest,self.unproto_path,self.beacon_text)
                await self.kiss.send_data(frame)
            await asyncio.sleep(self.beacon_every)

    async def rx_loop(self):
        if not self.kiss: return
        async for _,payload in self.kiss.recv_frames():
            p=parse_ax25(payload)
            if not p: continue
            ctl=p["ctl"]
            if ctl==CTL_UA and p["src"]==self.link_peer:
                self.link_up=True; self._ua_event.set(); self._disc_ua_event.set()
            elif (ctl&0x01)==0 and p["src"]==self.link_peer:
                self.link_up=True; self._ua_event.set()
            if ctl==CTL_DM and p["src"]==self.link_peer:
                self._disc_ua_event.set()
            if self.monitor_on:
                label,seq="",""
                if ctl==CTL_UI: label="UI"
                elif ctl==CTL_SABM: label="SABM"
                elif ctl==CTL_UA: label="UA"
                elif ctl==CTL_DISC: label="DISC"
                elif ctl==CTL_DM: label="DM"
                else:
                    if ctl&0x01==0: label="I"; seq=f" N(S)={(ctl>>1)&7} N(R)={(ctl>>5)&7}"
                    elif ctl&0x03==1: label="S"; seq=f" N(R)={(ctl>>5)&7}"
                    else: label=f"CTL=0x{ctl:02X}"
                header=f"\nM: {p['src']} > {p['dest']}{' VIA '+','.join(p['path']) if p['path'] else ''} {label}{seq}"
                print(header)
                if p["info"]:
                    text=p["info"].decode("latin-1","replace").replace("\r","\n").rstrip()
                    if text: [print("   "+ln) for ln in text.splitlines()]
                    if self.monitor_detail: print("   [hex] "+p["info"].hex())
                print("cmd: ",end="",flush=True)
