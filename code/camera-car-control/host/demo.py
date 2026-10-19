"""In-process simulation. No network or serial port is opened in demo mode."""
import math
import struct
import time

from PIL import Image, ImageDraw

from legacy import (ARM, CLEAR_FAULT, GET_CAPABILITIES, GET_STATUS, SET_PARAM,
                    SET_WHEEL_SPEED, STOP, DISARM, FrameParser, frame)


class DemoPort:
    def __init__(self):
        self.timeout = 0.02
        self.buffer = bytearray()
        self.parser = FrameParser()
        self.armed = False
        self.counts = [0.0, 0.0]
        self.speeds = [0, 0]
        self.targets = [0, 0]
        self.coast_until = [0, 0]
        self.limit = 0
        self.updated = time.monotonic()

    @property
    def in_waiting(self):
        return len(self.buffer)

    def advance(self):
        now = time.monotonic()
        # Match the planner's demonstration assumptions: 60ms release latency
        # then 800mm/s^2 coast. This is illustrative, not a measured chassis model.
        elapsed = min(1, now - self.updated)
        steps = max(1, math.ceil(elapsed / 0.005))
        dt = elapsed / steps
        for step in range(steps):
            at = now - elapsed + (step + 1)*dt
            for i in range(2):
                before = self.speeds[i]
                if self.targets[i]:
                    self.speeds[i] = self.targets[i]
                elif at >= self.coast_until[i]:
                    self.speeds[i] = math.copysign(max(0, abs(before)-800*dt), before)
                average = (before + self.speeds[i]) / 2
                self.counts[i] += average * dt * (1469, 1471)[i] / (math.pi * 66.3)
        self.updated = now

    def write(self, data):
        self.advance()
        for kind, seq, payload in self.parser.feed(data):
            if kind == GET_CAPABILITIES:
                self.buffer.extend(frame(0xC0, b'EVM1' + struct.pack('<HH', 1, 400), seq))
                continue
            if kind == ARM:
                self.armed = True
            elif kind in (STOP, DISARM):
                self.armed = False
                self.speeds = [0, 0]
                self.targets = [0, 0]
            elif kind == SET_PARAM and payload[0] == 9:
                self.limit = struct.unpack_from('<I', payload, 1)[0]
                if not self.limit:
                    self.speeds = [0, 0]
                    self.targets = [0, 0]
            elif kind == SET_WHEEL_SPEED:
                if self.armed and self.limit:
                    targets = list(struct.unpack('<ii', payload))
                    for i in range(2):
                        if not targets[i] and self.targets[i]:
                            self.coast_until[i] = time.monotonic() + 0.06
                    self.targets = targets
            if kind in (ARM, STOP, DISARM, GET_STATUS, SET_PARAM, CLEAR_FAULT):
                state = 2 if any(self.speeds) else int(self.armed)
                status = struct.pack('<BHiiiiHHH', state, 0, *map(round, self.counts),
                                     *map(round, self.speeds), *(180 if s else 0 for s in self.targets), 0)
                self.buffer.extend(frame(0x80, status, seq))
        return len(data)

    def read(self, size=1):
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        if not result:
            time.sleep(min(self.timeout, 0.01))
        return result

    def close(self):
        self.armed = False
        self.speeds = [0, 0]
        self.targets = [0, 0]


def scene(index, width=800, height=480):
    image = Image.new('RGB', (width, height), '#d9e3e4')
    draw = ImageDraw.Draw(image)
    horizon = height // 3
    draw.rectangle((0, 0, width, horizon), fill='#a8c5bf')
    draw.rectangle((0, horizon, width, height), fill='#c6c9cc')
    for x in range(-width, width*2, 100):
        draw.line((width//2 + (x-width//2)*0.22, horizon, x, height), fill='#e6e8ea', width=2)
    for y in range(horizon+20, height, 45):
        draw.line((0, y, width, y), fill='#e6e8ea', width=2)
    shift = int(55 * math.sin(index / 20))
    draw.polygon(((width//2-6, horizon), (width//2+6, horizon),
                  (width//2+shift+23, height), (width//2+shift-23, height)), fill='#303638')
    draw.rectangle((width*0.72, horizon-32, width*0.84, horizon+45), fill='#178b76')
    draw.line((width//2-18, height//2, width//2+18, height//2), fill='white', width=2)
    draw.line((width//2, height//2-18, width//2, height//2+18), fill='white', width=2)
    draw.rectangle((14, 12, 215, 43), fill='#172523')
    draw.text((24, 20), f'SIMULATED CAMERA  {index:06d}', fill='white')
    return image
