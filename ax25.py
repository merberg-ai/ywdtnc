CTL_UI   = 0x03
PID_NOPROTO = 0xF0  # No layer 3 (text)

# LAPB/AX.25 control values (mod-8, 1-byte controls)
CTL_SABM = 0x2F  # Set Asynchronous Balanced Mode (P=1)
CTL_UA   = 0x63  # Unnumbered Acknowledge (F=1 typical in response)
CTL_DISC = 0x43  # Disconnect
CTL_DM   = 0x0F  # Disconnected Mode

def _pack_addr(callsign: str, last: bool) -> bytes:
    if "-" in callsign:
        call, ssid_str = callsign.split("-", 1)
        try:
            ssid = int(ssid_str)
        except ValueError:
            ssid = 0
    else:
        call, ssid = callsign, 0
    call = (call.upper() + "      ")[:6]
    b = bytearray()
    for ch in call:
        b.append(ord(ch) << 1)
    ssid_byte = 0x60 | ((ssid & 0x0F) << 1)
    if last:
        ssid_byte |= 0x01
    b.append(ssid_byte)
    return bytes(b)

def _addr_block(src: str, dest: str, path: list[str] | None, ctl_last: bool = True) -> bytes:
    if path is None:
        path = []
    addrs = bytearray()
    all_calls = [dest, src] + path
    for i, call in enumerate(all_calls):
        last = (i == len(all_calls) - 1)
        addrs.extend(_pack_addr(call, last=last if ctl_last else False))
    return bytes(addrs)

def build_ui_frame(src: str, dest: str, path: list[str] | None, info: bytes) -> bytes:
    return _addr_block(src, dest, path, ctl_last=True) + bytes([CTL_UI, PID_NOPROTO]) + info

def build_u_frame(src: str, dest: str, path: list[str] | None, ctl: int) -> bytes:
    # Unnumbered frames (U) have only a control byte after address block; no PID, no info.
    return _addr_block(src, dest, path, ctl_last=True) + bytes([ctl])

def _unpack_one_addr(b: bytes, off: int):
    raw = b[off:off+7]
    if len(raw) < 7:
        return None, off
    call = "".join(chr((raw[i] >> 1) & 0x7F) for i in range(6)).strip()
    ssid = (raw[6] >> 1) & 0x0F
    last = bool(raw[6] & 0x01)
    if ssid:
        call = f"{call}-{ssid}"
    return call, off + 7, last

def parse_ax25(frame: bytes):
    off = 0
    addrs = []
    last = False
    while off + 7 <= len(frame):
        call, off, last = _unpack_one_addr(frame, off)
        if call is None:
            break
        addrs.append(call)
        if last:
            break
    if len(addrs) < 2 or off + 1 > len(frame):
        return None
    dest = addrs[0]; src = addrs[1]
    path = addrs[2:] if len(addrs) > 2 else []

    ctl = frame[off]
    # If UI (I/G?), expect PID
    if ctl == CTL_UI:
        if off + 2 > len(frame):
            pid = None
            info = b""
        else:
            pid = frame[off+1]
            info = frame[off+2:] if off+2 <= len(frame) else b""
    else:
        pid = None
        info = frame[off+1:] if off+1 <= len(frame) else b""

    return {"dest": dest, "src": src, "path": path, "ctl": ctl, "pid": pid, "info": info}
