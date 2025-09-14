# ax25.py — AX.25 frame builder/parser for MFJ-1270 emulator

def _encode_callsign(call: str, last: bool = False) -> bytes:
    call = call.upper()
    if "-" in call:
        base, ssid = call.split("-", 1)
        try:
            ssid = int(ssid)
        except ValueError:
            ssid = 0
    else:
        base, ssid = call, 0
    base = (base + "      ")[:6]
    addr = bytearray()
    for c in base:
        addr.append(ord(c) << 1)
    addr.append(((ssid & 0x0F) << 1) | 0x60 | (0x01 if last else 0x00))
    return bytes(addr)

def _build_header(src: str, dest: str, path: list[str]) -> bytearray:
    frame = bytearray()
    frame.extend(_encode_callsign(dest, last=False))
    if not path:
        frame.extend(_encode_callsign(src, last=True))
    else:
        frame.extend(_encode_callsign(src, last=False))
        for i, digi in enumerate(path):
            frame.extend(_encode_callsign(digi, last=(i == len(path) - 1)))
    return frame

def build_ui_frame(src: str, dest: str, path: list[str], info: bytes) -> bytes:
    frame = _build_header(src, dest, path)
    frame.append(0x03)
    frame.append(0xF0)
    frame.extend(info)
    return bytes(frame)

def build_u_frame(src: str, dest: str, path: list[str], ctl: int) -> bytes:
    frame = _build_header(src, dest, path)
    frame.append(ctl)
    return bytes(frame)

def build_i_frame(src: str, dest: str, path: list[str], ns: int, nr: int, info: bytes) -> bytes:
    frame = _build_header(src, dest, path)
    ctl = (ns << 1) | (nr << 5)
    frame.append(ctl)
    frame.append(0xF0)
    frame.extend(info)
    return bytes(frame)

def parse_ax25(frame: bytes):
    if len(frame) < 16:
        return None
    try:
        addrs = []
        i = 0
        while True:
            raw = frame[i:i+7]
            if len(raw) < 7:
                return None
            call = "".join(chr(b >> 1) for b in raw[:6]).strip()
            ssid = (raw[6] >> 1) & 0x0F
            if ssid:
                call = f"{call}-{ssid}"
            addrs.append(call)
            i += 7
            if raw[6] & 0x01:
                break
        dest = addrs[0]
        src = addrs[1]
        path = addrs[2:] if len(addrs) > 2 else []
        ctl = frame[i]
        i += 1
        pid = None
        info = b""
        if ctl & 0x01 == 0 or ctl == CTL_UI:
            if i < len(frame):
                pid = frame[i]
                i += 1
            if i < len(frame):
                info = frame[i:]
        else:
            if i < len(frame):
                info = frame[i:]
        return {"src": src, "dest": dest, "path": path, "ctl": ctl, "pid": pid, "info": info}
    except Exception:
        return None

CTL_UI = 0x03
CTL_SABM = 0x2F
CTL_UA = 0x63
CTL_DISC = 0x43
CTL_DM = 0x0F
