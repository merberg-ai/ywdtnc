import asyncio

class KissTCP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None

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
        try:
            data = await self.reader.read(1024)
            return data if data else None
        except Exception:
            return None

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
