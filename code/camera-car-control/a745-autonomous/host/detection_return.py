"""ED10 display metadata; no ARM/configuration/motion commands."""
import os
import socket
import struct
import time

def encode(sequence, boxes, classes):
    records = []
    for box in sorted(boxes, key=lambda b: b['score'], reverse=True):
        x1, y1, x2, y2 = map(int, box['box'])
        if not (0 <= x1 < x2 < 640 and 0 <= y1 < y2 < 480):
            continue
        label = classes.index(box['cls'])
        score = max(1, min(255, round(box['score'] * 255)))
        records.append(struct.pack('<HHHHBBH', x1, y1, x2, y2, label, score, 0))
        if len(records) == 8:
            break
    return struct.pack('<4sIBBHHH', b'ED10', sequence & 0xffffffff,
                       len(records), 0, 640, 480, 0) + b''.join(records)

class DetectionReturn:
    def __init__(self, classes):
        self.classes = classes
        self.sock = None
        self.sent = 0
        self.error = ''
        self.last_send = 0
        self.sequence = int(time.time()) & 0xffffffff
        self.enabled = os.environ.get('FPGA_DETECTION_RETURN', '1') == '1'

    def send(self, boxes):
        if not self.enabled:
            return
        try:
            if self.sock is None:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('192.168.0.3', 6105))
                self.sock.settimeout(0.1)
            packet = encode(self.sequence, boxes, self.classes)
            self.sock.sendto(packet, ('192.168.0.2', 6105))
            self.sequence = (self.sequence + 1) & 0xffffffff
            self.sent += 1
            self.last_send = time.monotonic()
            self.error = ''
        except (OSError, ValueError) as exc:
            self.error = str(exc)
            if self.sock is not None:
                self.sock.close()
                self.sock = None
