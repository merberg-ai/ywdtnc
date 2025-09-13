import asyncio

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

T_DATA = 0x00
T_TXDELAY = 0x01
T_PERSIST = 0x02
T_SLOTTIME = 0x03
T_TXTAIL = 0x04
T_FULLDUP = 0x05
T_SETHW = 0x06
T_RETURN = 0xFF

def _kiss_escape(payload: bytes) -> bytes:
    out = bytearray()
    for b in payload:
        if b == FEND:
            out.extend([FESC, TFEND])
        elif b == FESC:
            out.extend([FESC, TFESC])
        else:
            out.append(b)
    return bytes(out)

def _kiss_unescape(payload: bytes) -> bytes:
    out = bytearray()
    it = iter(payload)
    for b in it:
        if b == FESC:
            n = next(it, None)
            if n == TFEND:
                out.append(FEND)
            elif n == TFESC:
                out.append(FESC)
            elif n is None:
                break
            else:
                out.append(b); out.append(n)
        else:
            out.append(b)
    return bytes(out)

class KISSClient:
    def __init__(self, host="127.0.0.1", port=8001, port_id=0):
        self.host = host
        self.port = port
        self.port_id = port_id
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def open(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def send_data(self, data: bytes):
        if not self.writer:
            raise RuntimeError("KISS not connected")
        cmd = (self.port_id << 4) | T_DATA
        frame = bytes([FEND, cmd]) + _kiss_escape(data) + bytes([FEND])
        self.writer.write(frame)
        await self.writer.drain()

    async def set_txdelay(self, ms: int):
        if not self.writer:
            raise RuntimeError("KISS not connected")
        val = max(0, min(255, ms // 10))
        cmd = (self.port_id << 4) | T_TXDELAY
        frame = bytes([FEND, cmd, val, FEND])
        self.writer.write(frame)
        await self.writer.drain()

    async def recv_frames(self):
        if not self.reader:
            raise RuntimeError("KISS not connected")

        buf = bytearray()
        in_frame = False
        while True:
            chunk = await self.reader.read(1024)
            if not chunk:
                await asyncio.sleep(0.05)
                continue
            for b in chunk:
                if b == FEND:
                    if in_frame and len(buf) >= 1:
                        port_cmd = buf[0]
                        payload = _kiss_unescape(bytes(buf[1:]))
                        if (port_cmd & 0x0F) == T_DATA:
                            yield (port_cmd >> 4), payload
                    buf.clear()
                    in_frame = True
                else:
                    if in_frame:
                        buf.append(b)
