"""Wire-level Ethernet vectors for the integrated fusion/control/map channels."""
import struct
from network_check import PC_MAC,FPGA_MAC,PC_IP,FPGA_IP,checksum,udp,envelope
from protocol import crc16_ccitt,FrameParser


def vectors(path):
    values=[]
    def add(packet):
        values.extend(b|(0x100 if i==len(packet)-1 else 0) for i,b in enumerate(packet))
        values.extend([0x1000]*3)
    def map_packet(number,kind,payload):
        body=struct.pack("<4sIBB",b"EMM1",number,kind,len(payload))+payload
        return udp(body+struct.pack("<H",crc16_ccitt(body)),6104,6104)
    arp=struct.pack("!HHBBH6s4s6s4s",1,0x800,6,4,1,PC_MAC,PC_IP,bytes(6),FPGA_IP)
    add(bytes.fromhex("ffffffffffff")+PC_MAC+b"\x08\x06"+arp)
    for number,kind in enumerate((4,0x40,0x57,0x55),1):
        add(udp(envelope(kind,number)))
    add(map_packet(100,0x50,b"\0"))
    add(map_packet(101,0x51,struct.pack("<BHB",1,0,1)+b"\x55"))
    add(map_packet(102,0x51,struct.pack("<BHB",0,0,1)))
    # No motion packet is ever accepted by the map endpoint.
    add(map_packet(103,0x55,b""))
    add(udp(envelope(0x57,5)))
    path.write_text("\n".join(f"{v:04x}" for v in values)+"\n",encoding="ascii")
    return len(values)


def verify(path):
    control={};mapping={};fusion=0
    for line in path.read_text().splitlines():
        packet=bytes.fromhex(line)
        if packet[12:14]==b"\x08\x06":
            continue
        assert packet[:6]==PC_MAC and packet[6:12]==FPGA_MAC
        ip=packet[14:34];assert checksum(ip)==0
        u=packet[34:14+int.from_bytes(ip[2:4],"big")]
        sport,dport,length,_=struct.unpack_from("!HHHH",u)
        assert length==len(u) and checksum(FPGA_IP+PC_IP+struct.pack("!BBH",0,17,length)+u)==0
        data=u[8:]
        if dport==6103:
            if data[:4]==b"EMF1":
                assert len(data)==48 and data[16]==1 and data[19]==0
                fusion+=1
            continue
        assert crc16_ccitt(data[:-2])==int.from_bytes(data[-2:],"little")
        if dport==5001:
            assert sport==5000 and data[:4]==b"EMC1"
            parsed=FrameParser().feed(data[12:-2]);assert len(parsed)==1
            control[int.from_bytes(data[8:12],"little")]=parsed[0]
        else:
            assert sport==dport==6104 and data[:4]==b"EMM1" and len(data)==44
            mapping[int.from_bytes(data[4:8],"little")]=data[10:42]
    assert set(control)=={1,2,3,4,5},control.keys()
    assert control[2][0]==0xc0 and int.from_bytes(control[2][2][4:6],"little")&0x800
    assert control[3][0]==control[4][0]==control[5][0]==0xd0
    assert control[4][2][0]==1
    assert set(mapping)=={100,101,102} and all(v[0]==0 for v in mapping.values())
    assert mapping[102][4]==0x55 and fusion
    print("PASS Ethernet EMC1 navigation lock, EMM1 map roundtrip and EMF1 under backpressure; motor outputs stay zero")
