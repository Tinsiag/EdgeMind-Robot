"""A serial reader thread. Never calls Tk, never transmits to the LiDAR."""
import queue
import threading
import time


class Receiver(threading.Thread):
    def __init__(self, port: str):
        super().__init__(daemon=True, name="ld06-serial")
        self.port = port
        self.stop_event = threading.Event()
        self.data = queue.Queue(maxsize=128)
        self.events = queue.SimpleQueue()
        self.received_bytes = 0
        self.dropped_chunks = 0

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            import serial
            with serial.Serial(
                self.port, baudrate=230400, bytesize=8, parity="N", stopbits=1,
                timeout=0.04, xonxoff=False, rtscts=False, dsrdtr=False,
            ) as connection:
                self.events.put(("opened", self.port))
                while not self.stop_event.is_set():
                    # Request a real batch. Reading in_waiting (often 0 or 1)
                    # queued nearly every individual byte and overflowed the UI
                    # queue even at the normal LD06 data rate. The timeout
                    # bounds latency while serial keeps collecting bytes.
                    data = connection.read(1024)
                    if not data:
                        continue
                    self.received_bytes += len(data)
                    item = (time.monotonic(), data)
                    try:
                        self.data.put_nowait(item)
                    except queue.Full:
                        try:
                            self.data.get_nowait()
                        except queue.Empty:
                            pass
                        self.dropped_chunks += 1
                        self.data.put_nowait(item)
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        finally:
            self.events.put(("closed", self.port))
