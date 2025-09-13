import asyncio
import shlex
import configparser
import os
from kiss import KISSClient
from ax25 import build_ui_frame, build_u_frame, parse_ax25, CTL_UI, CTL_SABM, CTL_UA, CTL_DISC, CTL_DM

def _parse_via(rest: str):
    parts = rest.strip().split()
    if not parts:
        return None, []
    dest = parts[0].upper()
    path = []
    if len(parts) >= 2 and parts[1].upper() == "VIA":
        path = [p.strip().upper().rstrip(",") for p in parts[2:]]
        path = [p for p in (",".join(path)).split(",") if p]
    return dest, path

CFG_FILE = "mfj1270.ini"

class TNCState:
    def __init__(self):
        self.kiss_host = "127.0.0.1"
        self.kiss_port = 8001
        self.kiss: KISSClient | None = None

        self.mycall = "N0CALL"
        self.unproto_dest = None
        self.unproto_path = []
        self.monitor_on = True
        self.beacon_every: int | None = None
        self.beacon_text: bytes | None = None
        self.txdelay_ms: int | None = None

        self.converse = False
        self.link_up = False
        self.link_peer = None
        self.link_path = []
        self._ua_event = asyncio.Event()
        self._disc_ua_event = asyncio.Event()

        self._load_config()

    # ----------------- Config persistence -----------------
    def _load_config(self):
        cfg = configparser.ConfigParser()
        if not os.path.exists(CFG_FILE):
            return
        try:
            cfg.read(CFG_FILE)
            sect = cfg["tnc"]
            self.mycall = sect.get("mycall", self.mycall)
            self.unproto_dest = sect.get("unproto_dest", fallback=None) or None
            path_str = sect.get("unproto_path", fallback="")
            self.unproto_path = [p for p in path_str.split(",") if p] if path_str else []
            self.monitor_on = sect.getboolean("monitor_on", fallback=True)
            self.txdelay_ms = sect.getint("txdelay_ms", fallback=None)
            if sect.get("beacon_every", fallback="").strip():
                self.beacon_every = sect.getint("beacon_every", fallback=None)
            bt = sect.get("beacon_text", fallback=None)
            self.beacon_text = bt.encode("utf-8") if bt else None
            self.kiss_host = sect.get("kiss_host", self.kiss_host)
            self.kiss_port = sect.getint("kiss_port", fallback=self.kiss_port)
        except Exception:
            pass

    def _save_config(self):
        cfg = configparser.ConfigParser()
        cfg["tnc"] = {
            "mycall": self.mycall,
            "unproto_dest": self.unproto_dest or "",
            "unproto_path": ",".join(self.unproto_path) if self.unproto_path else "",
            "monitor_on": "true" if self.monitor_on else "false",
            "txdelay_ms": str(self.txdelay_ms) if self.txdelay_ms is not None else "",
            "beacon_every": str(self.beacon_every) if self.beacon_every is not None else "",
            "beacon_text": (self.beacon_text.decode("utf-8", "ignore") if self.beacon_text else ""),
            "kiss_host": self.kiss_host,
            "kiss_port": str(self.kiss_port)
        }
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)

    # ----------------- Lifecycle -----------------
    async def open(self):
        try:
            self.kiss = KISSClient(self.kiss_host, self.kiss_port)
            await self.kiss.open()
            if self.txdelay_ms is not None:
                await self.kiss.set_txdelay(self.txdelay_ms)
            print(f"*** Connected to Direwolf KISS at {self.kiss_host}:{self.kiss_port}")
        except Exception as e:
            print(f"*** ERROR: Could not connect to Direwolf KISS server at {self.kiss_host}:{self.kiss_port}")
            print(f"*** {e}")

    async def close(self):
        if self.kiss:
            await self.kiss.close()
            self.kiss = None

    async def reconnect(self):
        await self.close()
        self._load_config()
        await self.open()

    async def set_converse(self, on: bool):
        self.converse = on

    # ----------------- Commands -----------------
    async def handle_command(self, cmd: str, rest: str):
        if cmd == "RECONNECT":
            await self.reconnect()
            return True, f"Reconnected to {self.kiss_host}:{self.kiss_port}"

        # ... (other commands remain unchanged, MYCALL/UNPROTO/TXDELAY/BEACON/CONNECT/DISCONNECT etc.)

        return False, None

    # ----------------- Other methods -----------------
    # (send_converse_line, beacon_loop, _do_connect, _do_disconnect, rx_loop remain unchanged)
