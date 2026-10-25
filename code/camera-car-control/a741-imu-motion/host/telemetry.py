"""Bounded EMS1/EML1 receiver; gaps discard partial lidar revolutions."""
from dataclasses import dataclass
import socket
import struct
import threading
import time
from collections import deque


def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ (0x4d if crc & 0x80 else 0)) & 255
    return crc


def lidar_points(raw):
    if len(raw) != 47 or raw[:2] != b"\x54\x2c" or crc8(raw[:-1]) != raw[-1]:
        raise ValueError("Invalid LD06 packet/CRC")
    start = struct.unpack_from("<H", raw, 4)[0]
    end = struct.unpack_from("<H", raw, 42)[0]
    span = (end - start) % 36000
    if start >= 36000 or end >= 36000 or span > 3600:
        raise ValueError("Invalid LD06 angles")
    return [((start + span * i // 11) % 36000, *struct.unpack_from("<HB", raw, 6 + 3*i))
            for i in range(12)]


@dataclass(frozen=True)
class Snapshot:
    seq: int
    ms: int
    revision: int
    flags: int
    state: int
    faults: int
    left_target: int
    right_target: int
    left_speed: int
    right_speed: int
    left_count: int
    right_count: int
    yaw_raw: int
    gyro_raw: int
    tof_mm: int
    tof_status: int
    front_mm: int
    left_mm: int
    right_mm: int
    imu_ms: int
    tof_ms: int
    lidar_ms: int
    imu_errors: int
    tof_errors: int
    lidar_errors: int
    dropped: int
    gyro_ms: int
    gyro_bias: int
    imu_seq: int
    tof_seq: int
    lidar_seq: int
    network_status: int = 0

    def network_diagnostics(self):
        if not self.flags & 0x8000:
            return {"supported":False}
        value=self.network_status
        states=("RECEIVE","CHECK_CRC","VALIDATE","SEND","WAIT_BUSY","WAIT_DONE",
                "REPLY","MAKE_CRC","TRANSMIT")
        state=(value>>8)&15
        return {"supported":True,"rx_good_mod16":value&15,"rx_bad_fcs_saturated15":(value>>4)&15,
                "bridge_state":states[state] if state<len(states) else str(state),
                "rejected_mod16":(value>>12)&15}

    @classmethod
    def parse(cls, data):
        if len(data) != 112 or data[:4] != b"EMS1" or struct.unpack_from("<HH", data, 4) != (1, 112):
            raise ValueError("Invalid EMS1 snapshot")
        # 0..19 header; 20 flags,22 state,23 ToF status,24 faults,26 reserved.
        seq, ms, rev = struct.unpack_from("<III", data, 8)
        flags, state, status, faults = struct.unpack_from("<HBBH", data, 20)
        wheels = struct.unpack_from("<iiiiii", data, 28)
        yaw, gyro, tof, front, left, right = struct.unpack_from("<hhHHHH", data, 52)
        times_errors = struct.unpack_from("<IIIIIII", data, 64)
        gyro_ms, bias = struct.unpack_from("<Ih", data, 92)
        sequences = struct.unpack_from("<III", data, 100)
        return cls(seq, ms, rev, flags, state, faults, *wheels, yaw, gyro, tof, status,
                   front, left, right, *times_errors, gyro_ms, bias, *sequences,
                   struct.unpack_from("<H",data,26)[0])


class ScanAssembler:
    def __init__(self):
        self.points = []
        self.current = []
        self.last_angle = None
        self.last_seq = None
        self.last_time = None
        self.started = False
        self.received = None
        self.completed_at = None
        self.errors = 0
        self.gaps = 0
        self.last_step = 0
        self.completed_id = 0
        self.completed_stamp = None
        self.discontinuities = 0
        self.last_discontinuity = ""

    def invalidate(self, reason="扫描数据无效"):
        self.discontinuities += 1
        self.last_discontinuity = reason
        self.points.clear()
        self.current.clear()
        self.started = False
        self.completed_at = None
        self.last_angle = None
        self.last_step = 0
        self.completed_stamp = None

    def feed(self, packet, now=None):
        now = time.monotonic() if now is None else now
        if len(packet) != 64 or packet[:4] != b"EML1" or struct.unpack_from("<HH", packet, 4) != (1, 64):
            self.errors += 1
            self.invalidate("EML1帧头/长度错误")
            return
        seq, stamp = struct.unpack_from("<II", packet, 8)
        try:
            points = lidar_points(packet[16:63])
        except ValueError:
            self.errors += 1
            self.invalidate("LD06 CRC/角度校验失败")
            return
        gap = self.last_seq is not None and ((seq-self.last_seq) & 0xffffffff) != 1
        age = None if self.last_time is None else (stamp-self.last_time) & 0xffffffff
        stale = self.received is not None and now-self.received > .3
        if gap or (age is not None and age > 100) or stale:
            self.gaps += 1
            reason = "FPGA包序号缺口" if gap else "FPGA雷达时间间隔超过100ms" if age is not None and age > 100 else "主机雷达接收间隔超过300ms"
            self.invalidate(reason)
        self.last_seq, self.last_time, self.received = seq, stamp, now
        if self.last_angle is not None and ((points[0][0]-self.last_angle) % 36000) > max(100, self.last_step*3):
            self.gaps += 1
            self.invalidate("扫描内角度跳变")
        self.last_step = ((points[-1][0]-points[0][0]) % 36000) / 11
        for angle, distance, confidence in points:
            if self.last_angle is not None:
                delta = (angle-self.last_angle) % 36000
                if delta > 3600:
                    self.invalidate("相邻点角度跳变")
                elif angle < self.last_angle and self.last_angle-angle > 18000:
                    if self.started and self.current:
                        self.points = self.current
                        self.completed_at = now
                        self.completed_id += 1
                        self.completed_stamp = stamp
                    self.current = []
                    self.started = True
            self.last_angle = angle
            if self.started:
                self.current.append((angle, distance, confidence))
                if len(self.current) > 10000:
                    self.errors += 1
                    self.invalidate()

    def visible(self, now=None):
        now = time.monotonic() if now is None else now
        if self.received is not None and now-self.received > .3 and (self.started or self.completed_at is not None or self.last_angle is not None):
            self.invalidate("雷达数据断流超过300ms")
        elif self.completed_at is not None and now-self.completed_at > .3:
            self.invalidate("完整扫描过期超过300ms")
        return tuple(self.points) if self.completed_at is not None else ()


class TelemetryReceiver:
    def __init__(self, peer="192.168.0.2", port=6103):
        self.peer = peer
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        # The UI can still read diagnostics while disconnect closes the socket.
        self.receive_buffer_bytes = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        self.socket.bind(("", port))
        self.socket.settimeout(.1)
        self.lock = threading.Lock()
        self.snapshot = None
        self.phy_diagnostic = None
        self.updated = None
        self.scan = ScanAssembler()
        self.errors = 0
        self.bytes = 0
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.history = deque(maxlen=100)
        self.mapping_queue = deque(maxlen=3)
        self.mapping_dropped = 0
        self.thread.start()

    def run(self):
        while not self.closed.is_set():
            try:
                data, source = self.socket.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            if source != (self.peer, 6103):
                continue
            with self.lock:
                self.ingest(data)

    def queue_mapping(self, sample, now):
        if len(self.mapping_queue) == self.mapping_queue.maxlen:
            self.mapping_dropped += 1
            self.mapping_queue.clear()
            self.mapping_queue.append(((None, None, (), None, "建图接收队列积压，跳过不完整输入"), now))
        self.mapping_queue.append((sample, now))

    def ingest(self, data, now=None):
        """Called by the socket owner under lock; also usable without board I/O."""
        now = time.monotonic() if now is None else now
        self.bytes += len(data)
        try:
            if data[:4] == b"EMS1":
                snap = Snapshot.parse(data)
                if self.snapshot and not 0 < ((snap.seq-self.snapshot.seq) & 0xffffffff) < 0x80000000:
                    return
                self.snapshot, self.updated = snap, now
                self.history.append((snap, now))
            elif data[:4] == b"EMP1":
                if len(data) != 32 or struct.unpack_from("<HH", data, 4) != (1, 32):
                    raise ValueError("Invalid EMP1 PHY diagnostic")
                self.phy_diagnostic = {
                    "seq": struct.unpack_from("<I", data, 8)[0],
                    "fpga_ms": struct.unpack_from("<I", data, 12)[0],
                    "reset_ms": data[31], "settle_ms": data[30],
                    "phy_address": data[29], "fault": data[28],
                    "error": bool(data[27]), "ready": bool(data[26]),
                    "bmsr_current": struct.unpack_from("<H", data, 24)[0],
                    "bmsr_initial": struct.unpack_from("<H", data, 22)[0],
                    "bmcr": struct.unpack_from("<H", data, 20)[0],
                    "identity": struct.unpack_from("<I", data, 16)[0],
                }
            else:
                previous = self.scan.completed_id
                broken = self.scan.discontinuities
                self.scan.feed(data, now)
                if self.scan.discontinuities != broken:
                    self.queue_mapping((None, None, (), None, self.scan.last_discontinuity), now)
                if self.scan.completed_id != previous and self.scan.completed_stamp is not None:
                    stamp = self.scan.completed_stamp
                    difference = lambda s: abs(((s.ms-stamp+0x80000000) & 0xffffffff)-0x80000000)
                    recent = [s for s, received in self.history if now-received <= .3]
                    closest = min(recent, key=difference) if recent else None
                    if closest is None or difference(closest) > 100:
                        self.queue_mapping((None, None, (), None, "完整扫描没有100ms内有效遥测"), now)
                    else:
                        self.queue_mapping((self.scan.completed_id, stamp, tuple(self.scan.points), closest), now)
        except ValueError:
            self.errors += 1

    def read(self):
        with self.lock:
            now = time.monotonic()
            snap = self.snapshot if self.updated is not None and now-self.updated < .15 else None
            discontinuities = self.scan.discontinuities
            points = self.scan.visible(now)
            if self.scan.discontinuities != discontinuities:
                self.queue_mapping((None, None, (), None, self.scan.last_discontinuity), now)
            return snap, points

    def close(self):
        self.closed.set()
        self.socket.close()
        self.thread.join(timeout=.5)

    def mapping_samples(self):
        with self.lock:
            now = time.monotonic()
            samples = [sample if now-received <= .3 else (None, None, (), None, "上位机处理队列中扫描已过期")
                       for sample, received in self.mapping_queue]
            self.mapping_queue.clear()
            return samples

    def diagnostics(self):
        with self.lock:
            return {"host_bad_packets":self.scan.errors,"scan_gaps":self.scan.gaps,
                    "discontinuities":self.scan.discontinuities,"last_reason":self.scan.last_discontinuity,
                    "completed_scans":self.scan.completed_id,"mapping_queue_dropped":self.mapping_dropped,
                    "receive_buffer_bytes":self.receive_buffer_bytes,
                    "phy":getattr(self,"phy_diagnostic",None)}
