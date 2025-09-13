import asyncio

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

class KissTCP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.buffer = bytearray()

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            return False

    async def send(self, data: bytes):
        self.writer.write(data)
        await self.writer.drain()

    async def receive(self):
        while True:
            chunk = await self.reader.read(1024)
            if not chunk:
                return None
            self.buffer.extend(chunk)
            while FEND in self.buffer:
                start = self.buffer.find(FEND)
                end = self.buffer.find(FEND, start + 1)
                if end == -1:
                    break
                raw_frame = self.buffer[start + 1:end]
                del self.buffer[:end + 1]
                frame = bytearray()
                i = 0
                while i < len(raw_frame):
                    if raw_frame[i] == FESC:
                        if i + 1 < len(raw_frame):
                            if raw_frame[i + 1] == TFEND:
                                frame.append(FEND)
                            elif raw_frame[i + 1] == TFESC:
                                frame.append(FESC)
                            i += 2
                        else:
                            break
                    else:
                        frame.append(raw_frame[i])
                        i += 1
                if frame and frame[0] == 0x00:
                    return frame[1:]
