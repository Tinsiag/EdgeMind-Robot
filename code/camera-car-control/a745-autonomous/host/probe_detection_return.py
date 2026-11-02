"""Read-only end1 wire/EMS/HTTP probe. Run as root; sends no control packets."""
import argparse
import hashlib
import json
import socket
import struct
import time
import urllib.request
from receiver import decode_status, decode_attitude

def checksum(data):
    if len(data) & 1:
        data += b'\0'
    value = sum(struct.unpack('!%dH' % (len(data)//2), data))
    while value >> 16:
        value = (value & 65535) + (value >> 16)
    return value & 65535

def web():
    return json.load(urllib.request.urlopen('http://127.0.0.1:8090/status.json', timeout=3))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=30)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
    # Linux outgoing capture can precede NIC checksum completion. AUXDATA
    # identifies those packets; do not mistake a checksum seed for wire data.
    sock.setsockopt(263,8,1)  # SOL_PACKET, PACKET_AUXDATA
    sock.bind(('end1',0));sock.settimeout(.3)
    start_web = web();start = time.monotonic()
    statuses=[];attitudes=[];returns=[];invalid=[]
    while time.monotonic()-start < args.seconds:
        try:
            p, ancillary, flags, address = sock.recvmsg(4096,128)
        except socket.timeout:
            continue
        if len(p)<42 or p[12:15]!=b'\x08\x00\x45' or p[23]!=17:
            continue
        iplen = struct.unpack_from('!H',p,16)[0]
        src,dst,udplen = struct.unpack_from('!HHH',p,34)
        payload = p[42:14+iplen]
        if src==6103 and dst==6103:
            if payload[:4]==b'EMS1':
                value=decode_status(payload);value['detection_accepted']=payload[23];statuses.append(value)
            elif payload[:4]==b'EMF1':
                attitudes.append(decode_attitude(payload))
        elif dst==6105 and src==6105:
            try:
                assert p[:6]==bytes.fromhex('020000000002')
                assert p[6:12]==bytes.fromhex('48da35600099')
                assert p[26:34]==bytes([192,168,0,3,192,168,0,2])
                assert checksum(p[14:34])==65535
                pseudo=p[26:34]+b'\0\x11'+struct.pack('!H',udplen)
                pending=any(level==263 and kind==8 and len(value)>=4 and
                            struct.unpack_from('I',value)[0] & 8
                            for level,kind,value in ancillary)
                assert struct.unpack_from('!H',p,40)[0]!=0
                if not pending:
                    assert checksum(pseudo+p[34:34+udplen])==65535
                magic,seq,count,res,w,h,res2=struct.unpack_from('<4sIBBHHH',payload)
                assert (magic,res,w,h,res2)==(b'ED10',0,640,480,0)
                assert count<=8 and len(payload)==16+count*12
                boxes=[]
                for i in range(count):
                    box=struct.unpack_from('<HHHHBBH',payload,16+12*i)
                    x1,y1,x2,y2,label,score,res=box
                    assert 0<=x1<x2<640 and 0<=y1<y2<480 and label<80 and score>0 and res==0
                    boxes.append(box)
                returns.append(dict(seq=seq,boxes=boxes,frame_hex=p.hex(),
                                    udp_checksum_verified=not pending,
                                    nic_checksum_completion_pending=pending))
            except (AssertionError,struct.error) as exc:
                invalid.append(dict(frame_hex=p.hex(),error=repr(exc)))
    elapsed=time.monotonic()-start;end_web=web()
    accepted_delta=sum((b['detection_accepted']-a['detection_accepted'])&255 for a,b in zip(statuses,statuses[1:]))
    result=dict(elapsed_seconds=elapsed,statuses=statuses,attitudes=attitudes,
                return_frames=returns,invalid_return_frames=invalid,web_start=start_web,web_end=end_web,
                accepted_delta=accepted_delta,wire_return_count=len(returns),
                inference_hz=(end_web['infer_runs']-start_web['infer_runs'])/elapsed,
                camera_hz=(end_web['frames']-start_web['frames'])/elapsed,
                web_hz=(end_web['rendered_frames']-start_web['rendered_frames'])/elapsed,
                read_only=True,motion_packets_sent=0,
                script_sha256=hashlib.sha256(open(__file__,'rb').read()).hexdigest())
    with open(args.output,'w') as f:
        json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('statuses','attitudes','return_frames')},indent=2))
if __name__=='__main__':
    main()
