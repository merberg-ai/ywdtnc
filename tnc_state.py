import asyncio
import configparser
import os
from kiss import KISSClient
from ax25 import (
    build_ui_frame,
    build_u_frame,
    build_i_frame,
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

def _looks_like_callsign(token: str) -> bool:
    token = token.upper()
    if not token:
        return False
    parts = token.split("-")
    if not parts[0].isalnum():
        return False
    if len(parts[0]) > 6:
        return False
    if len(parts) == 2:
        if not parts[1].isdigit():
            return False
        if int(parts[1]) > 15:
            return False
    if len(parts) > 2:
        return False
    return True

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
        self._send_ns = 0

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
        return await self.open()

    async def set_converse(self, on: bool):
        self.converse = on

    # ----------------- Commands -----------------
    async def handle_command(self, cmd: str, rest: str):
        if cmd == "CONNECT":
            dest, path = _parse_via(rest)
            if not dest:
                return True, "Usage: CONNECT <CALL> [VIA DIGI1,DIGI2,...]"

            self.link_peer = dest
            self.link_path = path
            self._ua_event.clear()
            sabm = build_u_frame(self.mycall, self.link_peer, self.link_path, CTL_SABM)

            if self.kiss:
                # Try up to 3 times, 5s each
                for attempt in range(3):
                    await self.kiss.send_data(sabm)
                    try:
                        await asyncio.wait_for(self._ua_event.wait(), timeout=5.0)
                        self.link_up = True
                        return True, {"msg": f"*** CONNECTED to {self.link_peer}", "linked": True}
                    except asyncio.TimeoutError:
                        if attempt < 2:
                            continue
                        else:
                            self.link_peer = None
                            self.link_path = []
                            return True, "*** CONNECT failed (no UA after 3 tries)"
            else:
                return True, "KISS not connected"

        if cmd == "DISCONNECT":
            if not self.link_up or not self.link_peer:
                return True, "*** No active connection"
            self._disc_ua_event.clear()
            disc = build_u_frame(self.mycall, self.link_peer, self.link_path, CTL_DISC)
            if self.kiss:
                await self.kiss.send_data(disc)
                try:
                    await asyncio.wait_for(self._disc_ua_event.wait(), timeout=5.0)
                    peer = self.link_peer
                    self.link_up = False
                    self.link_peer = None
                    self.link_path = []
                    return True, f"*** DISCONNECTED from {peer}"
                except asyncio.TimeoutError:
                    return True, "*** DISCONNECT failed (timeout)"
            else:
                return True, "KISS not connected"

        return False, None

    # ----------------- Connected-mode TX -----------------
    async def send_linked_line(self, line: str):
        if not self.link_up or not self.link_peer:
            print("*** Not connected")
            return
        info = line.encode("utf-8", "ignore")
        ns = self._send_ns
        nr = 0
        self._send_ns = (self._send_ns + 1) % 8
        frame = build_i_frame(self.mycall, self.link_peer, self.link_path, ns, nr, info)
        if self.kiss:
            await self.kiss.send_data(frame)

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

            # Handle link-layer responses
            if ctl == CTL_UA and parsed["src"] == self.link_peer:
                self._ua_event.set()
                self._disc_ua_event.set()
            if ctl == CTL_DM and parsed["src"] == self.link_peer:
                self._disc_ua_event.set()

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
                    text = parsed["info"].decode("latin-1", "replace")
                    text = text.replace("\r", "\n").rstrip()
                    if text:
                        for line in text.splitlines():
                            print("   " + line)
                    if self.monitor_detail:
                        print("   [hex] " + parsed["info"].hex())

                print("cmd: ", end="", flush=True)
