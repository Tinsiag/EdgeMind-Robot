"""Bounded EMV1 UDP reassembly. Only complete, committed frames are published."""
from dataclasses import dataclass, field
import ipaddress
import queue
import socket
import struct
import threading
import time

import numpy as np
from PIL import Image

HEADER = struct.Struct('<4sIHHHHHH')
MAGIC = b'EMV1'
COMMIT, ABORT = 1, 2
MAX_WIDTH, MAX_HEIGHT = 1920, 1080
MAX_PIXELS_PER_PACKET = 640


def packet(frame_id, width, height, row=0, offset=0, pixels=b'', flags=0):
    if len(pixels) % 2:
        raise ValueError('RGB565 pixel data must contain pairs of bytes')
    return HEADER.pack(MAGIC, frame_id, width, height, row, offset,
                       len(pixels) // 2, flags) + pixels


@dataclass
class PendingFrame:
    width: int
    height: int
    created: float
    data: bytearray = field(init=False)
    seen: bytearray = field(init=False)
    received: int = 0
    committed: bool = False

    def __post_init__(self):
        self.data = bytearray(self.width * self.height * 2)
        self.seen = bytearray(self.width * self.height)


def newer(candidate, previous):
    return 0 < ((candidate - previous) & 0xFFFFFFFF) < 0x80000000


class FrameAssembler:
    def __init__(self, timeout=0.5):
        self.timeout = timeout
        self.pending = {}
        self.latest = None
        self.completed = self.dropped = self.invalid = 0
        self.blocked = {}

    def expire(self, now):
        for key in list(self.pending):
            if now - self.pending[key].created > self.timeout:
                del self.pending[key]
                self.blocked[key] = now
                self.dropped += 1
        self.blocked = {k: t for k, t in self.blocked.items() if now - t < 2}
        # A sender may reboot with frame_id=0; permit a new epoch after silence.
        if self.latest is not None and now - self.last_complete > 2:
            self.latest = None

    def feed(self, data, now=None):
        now = time.monotonic() if now is None else now
        self.expire(now)
        if len(data) < HEADER.size:
            self.invalid += 1
            return None
        magic, fid, width, height, row, offset, count, flags = HEADER.unpack_from(data)
        if (magic != MAGIC or not 1 <= width <= MAX_WIDTH or not 1 <= height <= MAX_HEIGHT
                or flags not in (0, COMMIT, ABORT)
                or len(data) != HEADER.size + count * 2
                or (flags and (count or row or offset))
                or (not flags and (not 1 <= count <= MAX_PIXELS_PER_PACKET
                                   or row >= height or offset + count > width))):
            self.invalid += 1
            return None
        if fid in self.blocked or (self.latest is not None and not newer(fid, self.latest)):
            return None
        if flags == ABORT:
            self.pending.pop(fid, None)
            self.blocked[fid] = now
            self.dropped += 1
            return None
        if fid not in self.pending:
            if len(self.pending) >= 2:
                old = min(self.pending, key=lambda k: self.pending[k].created)
                del self.pending[old]
                self.blocked[old] = now
                self.dropped += 1
            self.pending[fid] = PendingFrame(width, height, now)
        target = self.pending[fid]
        if (width, height) != (target.width, target.height):
            self.pending.pop(fid)
            self.blocked[fid] = now
            self.invalid += 1
            return None
        if flags == COMMIT:
            target.committed = True
        else:
            start = row * width + offset
            content = data[HEADER.size:]
            # Duplicates are legal, conflicting overlaps poison the whole frame.
            known = target.seen[start:start + count]
            if any(known):
                for index, seen in enumerate(known):
                    p = start + index
                    if seen and target.data[2*p:2*p+2] != content[2*index:2*index+2]:
                        self.pending.pop(fid)
                        self.blocked[fid] = now
                        self.invalid += 1
                        return None
            target.received += count - sum(known)
            target.seen[start:start + count] = b'\x01' * count
            target.data[2*start:2*(start+count)] = content
        if target.committed and target.received == width * height:
            self.latest, self.last_complete = fid, now
            self.pending = {k: f for k, f in self.pending.items() if newer(k, fid)}
            self.completed += 1
            return fid, width, height, bytes(target.data)
        return None


def rgb565_image(width, height, data):
    words = np.frombuffer(data, dtype='>u2').reshape(height, width)
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    red, green, blue = words >> 11, (words >> 5) & 63, words & 31
    rgb[..., 0] = (red << 3) | (red >> 2)
    rgb[..., 1] = (green << 2) | (green >> 4)
    rgb[..., 2] = (blue << 3) | (blue >> 2)
    return Image.fromarray(rgb)


def latest_put(target, value):
    try:
        target.put_nowait(value)
    except queue.Full:
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        try:
            target.put_nowait(value)
        except queue.Full:
            pass


class VideoReceiver(threading.Thread):
    def __init__(self, bind_ip, port, source_ip, frames, events):
        super().__init__(daemon=True, name='camera-udp')
        self.bind_ip, self.port = bind_ip, port
        self.source_ip = str(ipaddress.IPv4Address(source_ip))
        self.frames, self.events = frames, events
        self.halt = threading.Event()
        self.assembler = FrameAssembler()
        self.bound = threading.Event()

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                sock.bind((self.bind_ip, self.port))
                self.address = sock.getsockname()
                sock.settimeout(0.1)
                self.bound.set()
                self.events.put(('video_connected', f'{self.address[0]}:{self.address[1]}'))
                report_at = time.monotonic()
                while not self.halt.is_set():
                    try:
                        data, sender = sock.recvfrom(65535)
                    except socket.timeout:
                        self.assembler.expire(time.monotonic())
                    else:
                        if sender[0] != self.source_ip:
                            continue
                        result = self.assembler.feed(data)
                        if result:
                            fid, width, height, pixels = result
                            latest_put(self.frames, (rgb565_image(width, height, pixels),
                                                     fid, time.monotonic()))
                    if time.monotonic() >= report_at:
                        self.events.put(('video_stats', (self.assembler.completed,
                                                        self.assembler.dropped, self.assembler.invalid)))
                        report_at = time.monotonic() + 1
        except Exception as exc:
            self.events.put(('error', f'视频接收失败：{exc}'))
        finally:
            self.events.put(('video_disconnected', None))

    def stop(self):
        self.halt.set()
