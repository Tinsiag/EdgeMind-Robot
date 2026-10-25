"""Serial and transparent TCP transports for the existing byte protocol."""
import ipaddress
import serial
import secrets
import socket
import struct
import time

from legacy import frame
from protocol import crc16_ccitt

CONTROL_HEADER = struct.Struct('<4sII')


class UdpControlPort:
    """One outstanding request, with a session and monotonic datagram number."""
    def __init__(self, address, port=5000, local_port=5001):
        self.peer = (str(ipaddress.IPv4Address(address)), int(port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('0.0.0.0', int(local_port)))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.timeout = 0.02
        self.session = secrets.randbits(32)
        self.number = 0
        self.buffer = bytearray()

    def write(self, data):
        self.number = (self.number + 1) & 0xFFFFFFFF
        self.buffer.clear()
        body = CONTROL_HEADER.pack(b'EMC1', self.session, self.number) + data
        self.socket.sendto(body + struct.pack('<H', crc16_ccitt(body)), self.peer)
        return len(data)

    def receive(self):
        while True:
            try:
                data, source = self.socket.recvfrom(2048)
            except BlockingIOError:
                return
            if source != self.peer or len(data) < CONTROL_HEADER.size + 2:
                continue
            magic, session, number = CONTROL_HEADER.unpack_from(data)
            if (magic != b'EMC1' or session != self.session or number != self.number
                    or crc16_ccitt(data[:-2]) != int.from_bytes(data[-2:], 'little')):
                continue
            self.buffer.extend(data[CONTROL_HEADER.size:-2])

    @property
    def in_waiting(self):
        self.receive()
        return len(self.buffer)

    def read(self, size=1):
        deadline = time.monotonic() + self.timeout
        while True:
            self.receive()
            if self.buffer or time.monotonic() >= deadline:
                result = bytes(self.buffer[:size])
                del self.buffer[:size]
                return result
            time.sleep(0.001)

    def close(self):
        self.socket.close()


def open_control(mode, address, tcp_port=5000):
    if mode == 'UDP':
        if not 1 <= int(tcp_port) <= 65535:
            raise ValueError('UDP 端口须为 1~65535')
        return UdpControlPort(address.strip(), int(tcp_port))
    elif mode == 'TCP':
        host = str(ipaddress.IPv4Address(address.strip()))
        port = int(tcp_port)
        if not 1 <= port <= 65535:
            raise ValueError('TCP 端口须为 1~65535')
        url = f'socket://{host}:{port}'
    elif mode == 'UART':
        if not address.strip() or '://' in address:
            raise ValueError('请输入有效的 COM 串口名称')
        url = address.strip()
    else:
        raise ValueError('请选择 UDP、UART 或 TCP')
    return serial.serial_for_url(url, baudrate=115200, timeout=0.02, write_timeout=0.2)
