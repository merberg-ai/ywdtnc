import asyncio

_monitor_task = None
_stop_monitor = False

def stop_monitor():
    global _stop_monitor
    _stop_monitor = True

async def start_monitor(host, port, log_queue):
    global _monitor_task, _stop_monitor
    _stop_monitor = False

    async def monitor_loop():
        try:
            reader, _ = await asyncio.open_connection(host, port)
            log_queue.put(f"Connected to Direwolf at {host}:{port}")
            while not _stop_monitor:
                line = await reader.readline()
                if not line:
                    break
                log_queue.put(line.decode().strip())
        except Exception as e:
            log_queue.put(f"Monitor error: {e}")

    _monitor_task = asyncio.create_task(monitor_loop())
