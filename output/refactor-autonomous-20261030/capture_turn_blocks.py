"""Receive-only diagnosis: report the real points which forbid a left/right turn."""
import argparse,json,re,socket,struct,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code/camera-car-control/a745-autonomous/host'))
from receiver import decode_status,decode_attitude
TABLE=ROOT/'code/camera-car-control/a745-autonomous/rtl/a745_turn_envelope.v'
LIMITS=[(int(l),int(r)) for l,r in re.findall(r"left_limit=9'd(\d+);right_limit=9'd(\d+)",TABLE.read_text())]
assert len(LIMITS)==72


def points(data):
    if len(data)!=64 or data[:4]!=b'EML1' or struct.unpack_from('<HH',data,4)!=(1,64):
        raise ValueError('Invalid EML1')
    raw=data[16:63]
    if raw[:2]!=b'\x54\x2c':raise ValueError('Invalid LD06 header')
    crc=0
    for b in raw[:46]:
        crc^=b
        for _ in range(8):crc=((crc<<1)^0x4d if crc&128 else crc<<1)&255
    if crc!=raw[46]:raise ValueError('Invalid LD06 CRC')
    start,end=struct.unpack_from('<H',raw,4)[0],struct.unpack_from('<H',raw,42)[0]
    span=(end-start)%36000
    if start>=36000 or end>=36000 or span>1500:raise ValueError('Invalid LD06 span')
    for i in range(12):
        angle=(start+span*i//11)%36000
        distance,confidence=struct.unpack_from('<HB',raw,6+3*i)
        if distance==0 or confidence<20:continue
        body=(27000-angle)%36000
        left,right=LIMITS[body//500]
        yield dict(raw_angle=angle,body_degrees=body/100,distance_mm=distance,confidence=confidence,
                   left_limit_mm=left,right_limit_mm=right,left_blocked=distance<=left,right_blocked=distance<=right)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=int,default=45);args=ap.parse_args()
    receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'packets_sent':0,'status':[],
             'attitude':[],'scans':[],'radar_packets':0,'invalid_packets':0}
    last_angle=None;current=[]
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('',6103));sock.settimeout(.2);end=time.monotonic()+args.seconds
        while time.monotonic()<end:
            try:data,source=sock.recvfrom(2048)
            except socket.timeout:continue
            if source!=('192.168.0.2',6103):continue
            try:
                if data[:4]==b'EMS1':receipt['status'].append(decode_status(data))
                elif data[:4]==b'EMF1':receipt['attitude'].append(decode_attitude(data))
                elif data[:4]==b'EML1':
                    receipt['radar_packets']+=1
                    for point in points(data):
                        if last_angle is not None and point['raw_angle']<last_angle:
                            receipt['scans'].append({'received_utc':datetime.now(timezone.utc).isoformat(),
                                'points':len(current),
                                'left_blocks':sorted([p for p in current if p['left_blocked']],key=lambda p:p['distance_mm'])[:12],
                                'right_blocks':sorted([p for p in current if p['right_blocked']],key=lambda p:p['distance_mm'])[:12]})
                            current=[]
                        current.append(point);last_angle=point['raw_angle']
            except ValueError:receipt['invalid_packets']+=1
    receipt['ended_utc']=datetime.now(timezone.utc).isoformat()
    path=Path(__file__).with_name('TURNING-74504-BLOCK-POINTS.json')
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status_count':len(receipt['status']),'last_status':receipt['status'][-1:],
                      'last_attitude':receipt['attitude'][-1:],'last_scan':receipt['scans'][-1:],
                      'invalid_packets':receipt['invalid_packets'],'packets_sent':0},indent=2))


if __name__=='__main__':main()
