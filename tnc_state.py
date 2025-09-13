import asyncio
import shlex
import configparser
import os
from kiss import KISSClient
from ax25 import (
    build_ui_frame,
    build_u_frame,
    parse_ax25,
    CTL_UI,
    CTL_SABM,
    CTL_UA,
    CTL_DISC,
    CTL_DM,
)

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
        self.monitor_detail = False
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
            self.monitor_detail = sect.getboolean("monitor_detail", fallback=False)
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
            "monitor_detail": "true" if self.monitor_detail else "false",
            "txdelay_ms": str(self.txdelay_ms) if self.txdelay_ms is not None else "",
            "beacon_every": str(self.beacon_every) if self.beacon_every is not None else "",
            "beacon_text": (
                self.beacon_text.decode("utf-8", "ignore") if self.beacon_text else ""
            ),
            "kiss_host": self.kiss_host,
            "kiss_port": str(self.kiss_port),
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
            return True
        except Exception as e:
            print(
                f"*** ERROR: Could not connect to Direwolf KISS server at {self.kiss_host}:{self.kiss_port}"
            )
            print(f"*** {e}")
            self.kiss = None
            return False

    async def close(self):
        if self.kiss:
            await self.kiss.close()
            self.kiss = None

    async def reconnect(self):
        await self.close()
        self._load_config()
        success = await self.open()
        return success

    async def set_converse(self, on: bool):
        self.converse = on

    # ----------------- Commands -----------------
    async def handle_command(self, cmd: str, rest: str):
        if cmd == "RECONNECT":
            success = await self.reconnect()
            if success:
                return True, f"*** Reconnected to {self.kiss_host}:{self.kiss_port}"
            else:
                return True, f"*** RECONNECT failed for {self.kiss_host}:{self.kiss_port}"

        if cmd == "MYCALL":
            call = rest.strip().upper()
            if not call:
                return True, f"MYCALL: {self.mycall}"
            self.mycall = call
            self._save_config()
            return True, f"MYCALL set to {self.mycall}"

        if cmd == "UNPROTO":
            if not rest.strip():
                if self.unproto_dest:
                    path = ",".join(self.unproto_path) if self.unproto_path else ""
                    return True, f"UNPROTO {self.unproto_dest} VIA {path}" if path else f"UNPROTO {self.unproto_dest}"
                else:
                    return True, "UNPROTO not set"
            dest, path = _parse_via(rest)
            if not dest:
                return True, "Usage: UNPROTO <DEST> [VIA DIGI1,DIGI2,...]"
            self.unproto_dest = dest
            self.unproto_path = path
            self._save_config()
            if path:
                return True, f"UNPROTO {self.unproto_dest} VIA {','.join(path)}"
            return True, f"UNPROTO {self.unproto_dest}"

        if cmd == "MONITOR":
            arg = rest.strip().upper()
            if arg in ("ON", "1", "TRUE"):
                self.monitor_on = True
                self._save_config()
                return True, "MONITOR ON"
            elif arg in ("OFF", "0", "FALSE"):
                self.monitor_on = False
                self._save_config()
                return True, "MONITOR OFF"
            elif arg.startswith("DETAIL"):
                parts = arg.split()
                if len(parts) == 2 and parts[1] in ("ON", "OFF"):
                    self.monitor_detail = parts[1] == "ON"
                    self._save_config()
                    return True, f"MONITOR DETAIL {'ON' if self.monitor_detail else 'OFF'}"
                return True, f"MONITOR DETAIL is {'ON' if self.monitor_detail else 'OFF'}"
            else:
                return True, f"MONITOR is {'ON' if self.monitor_on else 'OFF'}"

        return False, None

    # ----------------- Converse/UI TX -----------------
    async def send_converse_line(self, line: str):
        if not self.unproto_dest:
            print("UNPROTO not set.")
            return
        info = line.encode("utf-8", "ignore")
        frame = build_ui_frame(self.mycall, self.unproto_dest, self.unproto_path, info)
        if self.kiss:
            await self.kiss.send_data(frame)

    async def beacon_loop(self):
        while self.beacon_every is not None:
            if self.beacon_text and self.unproto_dest and self.kiss:
                frame = build_ui_frame(
                    self.mycall, self.unproto_dest, self.unproto_path, self.beacon_text
                )
                await self.kiss.send_data(frame)
            await asyncio.sleep(self.beacon_every)

    # ----------------- RX/Monitor -----------------
    async def rx_loop(self):
        if not self.kiss:
            return
        async for port_id, payload in self.kiss.recv_frames():
            parsed = parse_ax25(payload)
            if not parsed:
                continue

            ctl = parsed["ctl"]
            path = f" VIA {','.join(parsed['path'])}" if parsed["path"] else ""

            if self.monitor_on:
                label = None
                seq_info = ""
                if ctl == CTL_UI:
                    label = "UI"
                elif ctl == CTL_SABM:
                    label = "SABM"
                elif ctl == CTL_UA:
                    label = "UA"
                elif ctl == CTL_DISC:
                    label = "DISC"
                elif ctl == CTL_DM:
                    label = "DM"
                else:
                    if ctl & 0x01 == 0:
                        ns = (ctl >> 1) & 0x07
                        nr = (ctl >> 5) & 0x07
                        label = "I"
                        seq_info = f" N(S)={ns} N(R)={nr}"
                    elif ctl & 0x03 == 0x01:
                        s_type = (ctl >> 2) & 0x03
                        nr = (ctl >> 5) & 0x07
                        if s_type == 0:
                            label = "RR"
                        elif s_type == 1:
                            label = "RNR"
                        elif s_type == 2:
                            label = "REJ"
                        else:
                            label = "S?"
                        seq_info = f" N(R)={nr}"
                    else:
                        label = f"CTL=0x{ctl:02X}"

                header = f"\nM: {parsed['src']} > {parsed['dest']}{path} {label}{seq_info}"
                if parsed["pid"] is not None and ctl == CTL_UI:
                    header += f" PID=0x{parsed['pid']:02X}"
                print(header)

                if parsed["info"]:
                    # Always show human-readable
                    text = parsed["info"].decode("latin-1", "replace")
                    text = text.replace("\r", "\n").rstrip()
                    if text:
                        for line in text.splitlines():
                            print("   " + line)
                    if self.monitor_detail:
                        print("   [hex] " + parsed["info"].hex())

                print("cmd: ", end="", flush=True)
