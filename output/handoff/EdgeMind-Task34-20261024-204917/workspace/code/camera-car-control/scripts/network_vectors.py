"""Ethernet-level integration vectors and independent output verification."""
import socket
import struct
import sys

from check_fpga import ROOT

sys.path.insert(0, str(ROOT / 'host'))
from legacy import frame, STOP, ARM, SET_WHEEL_SPEED, GET_CAPABILITIES
from protocol import crc16_ccitt, FrameParser, decode_capabilities, decode_status
from video import FrameAssembler

PC_MAC = bytes.fromhex('020000000003')
FPGA_MAC = bytes.fromhex('020000000002')
PC_IP = socket.inet_aton('192.168.0.3')
FPGA_IP = socket.inet_aton('192.168.0.2')
SESSION = 0x12345678


def checksum(data):
    if len(data) & 1:
        data += b'\0'
    total = sum(struct.unpack('!' + 'H'*(len(data)//2), data))
    while total >> 16:
        total = (total & 65535) + (total >> 16)
    return (~total) & 65535


def envelope(kind, number, payload=b'', session=SESSION):
    body = struct.pack('<4sII', b'EMC1', session, number) + frame(kind, payload, number)
    return body + struct.pack('<H', crc16_ccitt(body))


def udp(payload, sport=5001, dport=5000, src=PC_IP, flags=0x4000):
    length = 8 + len(payload)
    udp_header = struct.pack('!HHHH', sport, dport, length, 0)
    check = checksum(src + FPGA_IP + struct.pack('!BBH', 0, 17, length) + udp_header + payload) or 65535
    udp_header = udp_header[:6] + struct.pack('!H', check)
    ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, length+20, 1, flags, 64, 17, 0, src, FPGA_IP)
    ip = ip[:10] + struct.pack('!H', checksum(ip)) + ip[12:]
    return FPGA_MAC + PC_MAC + b'\x08\x00' + ip + udp_header + payload


def make_vectors(path):
    values = []
    def add(data):
        values.extend(byte | (0x100 if i == len(data)-1 else 0) for i, byte in enumerate(data))
        values.append(0x1000)
    arp = struct.pack('!HHBBH6s4s6s4s', 1, 0x0800, 6, 4, 1, PC_MAC, PC_IP, b'\0'*6, FPGA_IP)
    add(b'\xff'*6 + PC_MAC + b'\x08\x06' + arp)
    add(udp(envelope(STOP, 1)))
    add(udp(envelope(GET_CAPABILITIES, 2)))
    add(udp(envelope(ARM, 3)))
    values.append(0x2000)
    add(udp(envelope(1, 4)))
    add(udp(envelope(SET_WHEEL_SPEED, 5, struct.pack('<ii', 100, 100))))
    values.append(0x3000)
    add(udp(envelope(STOP, 6)))
    values.append(0x4000)
    # Late/duplicate datagrams and a foreign session must never restart motion.
    add(udp(envelope(SET_WHEEL_SPEED, 5, struct.pack('<ii', 100, 100))))
    add(udp(envelope(ARM, 7, session=0x87654321)))
    corrupt = bytearray(envelope(ARM, 8))
    corrupt[-1] ^= 1
    add(udp(bytes(corrupt)))
    add(udp(envelope(ARM, 9), sport=5002))
    add(udp(envelope(ARM, 10), src=socket.inet_aton('192.168.0.4')))
    values.append(0x4000)
    # Read-only status after invalid traffic proves recovery and stopped state.
    add(udp(envelope(1, 11)))
    values.append(0xFFFF)
    path.write_text('\n'.join(f'{n:04x}' for n in values)+'\n', encoding='ascii')
    return len(values)


def verify_output(path):
    replies = {}
    frames = []
    assembler = FrameAssembler()
    arp_count = 0
    for line in path.read_text().splitlines():
        packet = bytes.fromhex(line)
        if packet[12:14] == b'\x08\x06':
            arp_count += 1
            continue
        assert packet[:6] == PC_MAC and packet[6:12] == FPGA_MAC
        assert packet[12:14] == b'\x08\x00'
        ip = packet[14:34]
        assert checksum(ip) == 0 and ip[9] == 17
        assert ip[12:16] == FPGA_IP and ip[16:20] == PC_IP
        length = int.from_bytes(ip[2:4], 'big')
        content = packet[34:14+length]
        sport, dport, udp_len, _ = struct.unpack('!HHHH', content[:8])
        assert len(content) == udp_len
        assert checksum(FPGA_IP + PC_IP + struct.pack('!BBH', 0, 17, udp_len) + content) == 0
        payload = content[8:]
        if dport == 5001:
            assert sport == 5000 and payload[:4] == b'EMC1'
            assert crc16_ccitt(payload[:-2]) == int.from_bytes(payload[-2:], 'little')
            session, number = struct.unpack_from('<II', payload, 4)
            assert session == SESSION
            response = FrameParser().feed(payload[12:-2])
            assert len(response) == 1
            replies[number] = response[0]
        elif dport == 6102:
            result = assembler.feed(payload, 0)
            if result:
                frames.append(result)
        else:
            raise AssertionError('Unexpected destination port')
    assert arp_count >= 1
    assert set(replies) == {1, 2, 3, 4, 6, 11}, replies.keys()
    assert decode_capabilities(replies[2][2]).bridge_fixed
    # A723 samples the pre-command state for the immediate ARM/STOP reply.
    # Explicit status queries, as used by the real host, confirm the new state.
    assert decode_status(replies[4][2]).state == 1
    assert decode_status(replies[11][2]).state == 0
    assert len(frames) == 1 and frames[0][3] == b'\xf8\x00' * 8
    print('PASS Ethernet/ARP/IPv4/UDP checksums, EMC1 session/replay/STOP, EMV1 video')
