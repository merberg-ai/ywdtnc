def decode_callsign(raw: bytes) -> str:
    call = ""
    for i in range(6):
        call += chr(raw[i] >> 1)
    ssid = (raw[6] >> 1) & 0x0F
    if ssid:
        return f"{call.strip()}-{ssid}"
    return call.strip()

def parse_ax25(frame: bytes) -> dict:
    if len(frame) < 17:
        return {"error": "Frame too short"}
    dst = decode_callsign(frame[0:7])
    src = decode_callsign(frame[7:14])
    ctrl = frame[14]
    pid = frame[15]
    payload = frame[16:]
    return {
        "src": src,
        "dst": dst,
        "ctrl": ctrl,
        "pid": pid,
        "payload": payload
    }
