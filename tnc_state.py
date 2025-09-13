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
    def __init__(self, host="127.0.0.1", port=8001):
        self.kiss = KISSClient(host, port)
        # Settings (persisted)
        self.mycall = "N0CALL"
        self.unproto_dest = None
        self.unproto_path = []
        self.monitor_on = True
        self.beacon_every: int | None = None
        self.beacon_text: bytes | None = None
        self.txdelay_ms: int | None = None

        # Runtime
        self.converse = False
        self._rx_print_queue = asyncio.Queue()

        # LAPB handshake state
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
        except Exception:
            # ignore config errors; run with defaults
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
            "beacon_text": (self.beacon_text.decode("utf-8", "ignore") if self.beacon_text else "")
        }
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)

    # ----------------- Lifecycle -----------------
    async def open(self):
        await self.kiss.open()
        # Reapply TXDELAY if stored
        if self.txdelay_ms is not None:
            await self.kiss.set_txdelay(self.txdelay_ms)

    async def close(self):
        await self.kiss.close()

    async def set_converse(self, on: bool):
        self.converse = on

    # ----------------- Commands -----------------
    async def handle_command(self, cmd: str, rest: str):
        if cmd == "MYCALL":
            call = rest.strip().upper()
            if not call:
                return True, f"MYCALL: {self.mycall}"
            self.mycall = call
            self._save_config()
            return True, f"MYCALL set to {self.mycall}"

        if cmd == "UNPROTO":
            dest, path = _parse_via(rest)
            if not dest:
                if self.unproto_dest:
                    return True, f"UNPROTO: {self.unproto_dest} VIA {','.join(self.unproto_path) if self.unproto_path else '(none)'}"
                return True, "Usage: UNPROTO <DEST> [VIA digi1,digi2]"
            self.unproto_dest = dest
            self.unproto_path = path
            self._save_config()
            via = f" VIA {','.join(path)}" if path else ""
            return True, f"UNPROTO set: {dest}{via}"

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
            else:
                return True, f"MONITOR is {'ON' if self.monitor_on else 'OFF'}"

        if cmd == "TXDELAY":
            try:
                ms = int(rest.strip())
            except ValueError:
                return True, "Usage: TXDELAY <milliseconds>"
            await self.kiss.set_txdelay(ms)
            self.txdelay_ms = ms
            self._save_config()
            return True, f"TXDELAY set to {ms} ms"

        if cmd == "BEACON":
            if not rest.strip():
                if self.beacon_every:
                    return True, f"BEACON EVERY {self.beacon_every}s TEXT {self.beacon_text.decode('utf-8','ignore') if self.beacon_text else ''}"
                return True, "Usage: BEACON EVERY <sec> TEXT <text>  | BEACON OFF"
            try:
                tokens = shlex.split(rest)
            except ValueError:
                tokens = rest.split()
            if len(tokens) >= 4 and tokens[0].upper() == "EVERY" and tokens[2].upper() == "TEXT":
                try:
                    sec = int(tokens[1])
                except ValueError:
                    return True, "BEACON: invalid seconds"
                text = " ".join(tokens[3:])
                self.beacon_every = max(1, sec)
                self.beacon_text = text.encode("utf-8", "ignore")
                self._save_config()
                return True, f"BEACON set: every {self.beacon_every}s"
            elif tokens and tokens[0].upper() == "OFF":
                self.beacon_every = None
                self.beacon_text = None
                self._save_config()
                return True, "BEACON OFF"
            else:
                return True, "Usage: BEACON EVERY <sec> TEXT <text>  | BEACON OFF"

        if cmd in ("CONNECT", "C"):
            # CONNECT <CALL> [VIA ...]
            dest, path = _parse_via(rest)
            if not dest:
                return True, "Usage: CONNECT <CALL> [VIA digi1,digi2]"
            return True, await self._do_connect(dest, path)

        if cmd in ("DISCONNECT", "D"):
            return True, await self._do_disconnect()

        return False, None

    # ----------------- Converse/UI TX -----------------
    async def send_converse_line(self, line: str):
        if not self.unproto_dest:
            print("UNPROTO not set.")
            return
        info = line.encode("utf-8", "ignore")
        frame = build_ui_frame(self.mycall, self.unproto_dest, self.unproto_path, info)
        await self.kiss.send_data(frame)

    async def beacon_loop(self):
        while self.beacon_every is not None:
            if self.beacon_text and self.unproto_dest:
                frame = build_ui_frame(self.mycall, self.unproto_dest, self.unproto_path, self.beacon_text)
                await self.kiss.send_data(frame)
            await asyncio.sleep(self.beacon_every)

    # ----------------- LAPB Handshake -----------------
    async def _do_connect(self, peer: str, path: list[str]):
        if self.link_up:
            return f"Already connected to {self.link_peer}. Use DISCONNECT first."
        # Send SABM (P=1), wait for UA
        self._ua_event.clear()
        self.link_peer = peer
        self.link_path = path
        sabm = build_u_frame(src=self.mycall, dest=peer, path=path, ctl=CTL_SABM)
        await self.kiss.send_data(sabm)
        try:
            await asyncio.wait_for(self._ua_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            # If a DM arrived, rx loop will have reported it; treat as failure.
            self.link_peer = None
            self.link_path = []
            return "CONNECT timeout (no UA)."
        self.link_up = True
        return f"*** CONNECTED to {peer}{(' VIA ' + ','.join(path)) if path else ''}"

    async def _do_disconnect(self):
        if not self.link_up and not self.link_peer:
            return "Not connected."
        self._disc_ua_event.clear()
        disc = build_u_frame(src=self.mycall, dest=self.link_peer, path=self.link_path, ctl=CTL_DISC)
        await self.kiss.send_data(disc)
        try:
            await asyncio.wait_for(self._disc_ua_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Consider link down anyway
            msg = "*** DISCONNECT (no UA)"
        else:
            msg = "*** DISCONNECTED"
        # Reset link state
        self.link_up = False
        self.link_peer = None
        self.link_path = []
        return msg

    # ----------------- RX/Monitor -----------------
    async def rx_loop(self):
        async for port_id, payload in self.kiss.recv_frames():
            parsed = parse_ax25(payload)
            if not parsed:
                continue

            # Handshake reaction
            if self.link_peer:
                # Is this from peer to us?
                from_peer = (parsed["src"] == self.link_peer and parsed["dest"] == self.mycall)
            else:
                from_peer = False

            ctl = parsed["ctl"]

            # Incoming UA in response to SABM or DISC
            if ctl == CTL_UA and from_peer:
                if not self.link_up:
                    self._ua_event.set()     # UA to our SABM
                else:
                    self._disc_ua_event.set()  # UA to our DISC

            # Incoming DM: peer refuses or not connected
            if ctl == CTL_DM and from_peer:
                print("\n*** DM from peer (connection refused/not connected)")
                self._ua_event.set()  # wake any waiters so CONNECT fails fast
                # leave link_up False
                print("cmd: ", end="", flush=True)
                continue

            # Monitor output
            if self.monitor_on:
                path = f" VIA {','.join(parsed['path'])}" if parsed['path'] else ""
                if ctl == CTL_UI:
                    try:
                        text = parsed['info'].decode('utf-8', 'ignore')
                    except Exception:
                        text = parsed['info'].hex()
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} UI PID=0x{parsed['pid']:02X}")
                    if text:
                        print(f"   {text}")
                elif ctl == CTL_SABM:
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} SABM")
                    # For now, auto-accept inbound SABM and send UA
                    ua = build_u_frame(src=self.mycall, dest=parsed['src'], path=parsed['path'], ctl=CTL_UA)
                    await self.kiss.send_data(ua)
                elif ctl == CTL_UA:
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} UA")
                elif ctl == CTL_DISC:
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} DISC")
                    # Auto UA, drop link if it was with this peer
                    ua = build_u_frame(src=self.mycall, dest=parsed['src'], path=parsed['path'], ctl=CTL_UA)
                    await self.kiss.send_data(ua)
                    if self.link_up and self.link_peer == parsed['src']:
                        self.link_up = False
                        self.link_peer = None
                        self.link_path = []
                        print("*** DISCONNECTED (by peer)")
                elif ctl == CTL_DM:
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} DM")
                else:
                    # Other control types (RR/RNR/I/etc.) not implemented yet
                    print(f"\nM: {parsed['src']} > {parsed['dest']}{path} CTL=0x{ctl:02X}")
                print("cmd: ", end="", flush=True)
