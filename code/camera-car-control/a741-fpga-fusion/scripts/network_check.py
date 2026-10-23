"""Reuse the established Ethernet vector/checksum functions, verify A741 schema."""
from pathlib import Path
import struct
import sys
import socket

CAMERA = Path(__file__).resolve().parents[2]
PC_MAC = bytes.fromhex("020000000003")
FPGA_MAC = bytes.fromhex("020000000002")
PC_IP = socket.inet_aton("192.168.0.3")
FPGA_IP = socket.inet_aton("192.168.0.2")
MOTION_HOST = CAMERA.parent / "fpga" / "acg720-motion-control" / "host"
sys.path.insert(0, str(MOTION_HOST))
from protocol import FrameParser, crc16_ccitt, frame
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from telemetry import Snapshot


def checksum(data):
    if len(data) & 1:
        data += b"\0"
    total = sum(struct.unpack("!"+"H"*(len(data)//2), data))
    while total >> 16:
        total = (total & 65535)+(total >> 16)
    return (~total) & 65535


def envelope(kind, number, payload=b"", session=0x12345678):
    body = struct.pack("<4sII", b"EMC1", session, number)+frame(kind, payload, number)
    return body+struct.pack("<H", crc16_ccitt(body))


def udp(payload, sport=5001, dport=5000, src=PC_IP, flags=0x4000):
    length=8+len(payload)
    header=struct.pack("!HHHH",sport,dport,length,0)
    check=checksum(src+FPGA_IP+struct.pack("!BBH",0,17,length)+header+payload) or 65535
    header=header[:6]+struct.pack("!H",check)
    ip=struct.pack("!BBHHHBBH4s4s",0x45,0,length+20,1,flags,64,17,0,src,FPGA_IP)
    ip=ip[:10]+struct.pack("!H",checksum(ip))+ip[12:]
    return FPGA_MAC+PC_MAC+b"\x08\x00"+ip+header+payload


def vectors(path):
    values = []
    def add(data):
        values.extend(b | (0x100 if i == len(data)-1 else 0) for i, b in enumerate(data))
        values.append(0x1000)
    arp = struct.pack("!HHBBH6s4s6s4s", 1, 0x800, 6, 4, 1, PC_MAC, PC_IP, bytes(6), FPGA_IP)
    add(bytes.fromhex("ffffffffffff")+PC_MAC+b"\x08\x06"+arp)
    commands = [(4, b""), (0x40, b""), (0x30, struct.pack("<BI", 6, 74101)),
                (0x44, struct.pack("<I", 6)), (0x41, b""), (2, b""), (0x43, b"")]
    for number, (kind, payload) in enumerate(commands, 1):
        add(udp(envelope(kind, number, payload)))
    add(udp(envelope(2, 3)))  # late request must be rejected by EMC1
    add(udp(envelope(0x20, 8)))
    path.write_text("\n".join(f"{v:04x}" for v in values)+"\n", encoding="ascii")
    return len(values)


def verify(path):
    replies = {}
    snapshots = 0
    arp_count = 0
    for line in path.read_text().splitlines():
        p = bytes.fromhex(line)
        if p[12:14] == b"\x08\x06":
            arp_count += 1
            continue
        assert p[:6] == PC_MAC and p[6:12] == FPGA_MAC
        ip = p[14:34]
        assert checksum(ip) == 0
        size = int.from_bytes(ip[2:4], "big")
        u = p[34:14+size]
        sport, dport, length, _ = struct.unpack_from("!HHHH", u)
        assert len(u) == length
        assert checksum(FPGA_IP+PC_IP+struct.pack("!BBH", 0, 17, length)+u) == 0
        data = u[8:]
        if dport == 6103:
            snap = Snapshot.parse(data)
            assert snap.flags & 7 == 0 and snap.state == 0
            network=snap.network_diagnostics()
            assert network["supported"] and network["rx_good_mod16"]==3
            assert network["rx_bad_fcs_saturated15"]==2
            snapshots += 1
        else:
            assert sport == 5000 and dport == 5001 and data[:4] == b"EMC1"
            assert int.from_bytes(data[-2:], "little") == __import__("protocol").crc16_ccitt(data[:-2])
            parsed = FrameParser().feed(data[12:-2])
            assert len(parsed) == 1
            replies[int.from_bytes(data[8:12], "little")] = parsed[0]
    assert arp_count and snapshots
    assert set(replies) == set(range(1, 9)), replies.keys()
    assert replies[2][0] == 0xc0 and struct.unpack_from("<H", replies[2][2], 4)[0] & 0x10
    assert replies[4][0] == 0xc4 and struct.unpack("<III", replies[4][2]) == (6, 74101, 74101)
    assert replies[5][0] == 0xc1 and len(replies[5][2]) == 32
    assert replies[6][2][0] == 0 and replies[8][2][0] == 0
    print("PASS host decoded A741 Ethernet checksums, capability/config/sensors, stale replay and EMS1")
