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


def points(data,include_invalid=False):
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
        usable=distance!=0 and confidence>=20
        if not usable and not include_invalid:continue
        body=(27000-angle)%36000
        left,right=LIMITS[body//500]
        yield dict(raw_angle=angle,body_degrees=body/100,distance_mm=distance,confidence=confidence,
                   left_limit_mm=left,right_limit_mm=right,left_blocked=usable and distance<=left,right_blocked=usable and distance<=right)


class NearQualifier:
    """Diagnostic mirror of the FW74505 two-point-lookahead filter."""
    def __init__(self):self.history=[]
    def push(self,point):
        self.history=(self.history+[point])[-5:]
        if len(self.history)<3:return
        center=len(self.history)-3;p=self.history[center]
        usable=lambda q:q['distance_mm']>0 and q['confidence']>=20
        def joined(a,b):
            return (usable(a) and usable(b) and a['distance_mm']<5000 and b['distance_mm']<5000 and
                    0<(b['raw_angle']-a['raw_angle'])%36000<=250 and
                    abs(b['distance_mm']-a['distance_mm'])*100<=a['distance_mm']*3)
        supported=any(start>=0 and start+2<len(self.history) and
                      joined(self.history[start],self.history[start+1]) and
                      joined(self.history[start+1],self.history[start+2])
                      for start in range(center-2,center+1))
        p['qualified_confidence']=p['confidence'] if usable(p) and (
            p['distance_mm']>=5000 or p['confidence']>=220 or supported) else 0


def scan_report(current,filtered):
    raw_left=[p for p in current if p['left_blocked']]
    raw_right=[p for p in current if p['right_blocked']]
    left=[p for p in raw_left if p.get('qualified_confidence',0)>=20] if filtered else raw_left
    right=[p for p in raw_right if p.get('qualified_confidence',0)>=20] if filtered else raw_right
    nearest=lambda values:sorted(values,key=lambda p:p['distance_mm'])[:12]
    return dict(received_utc=datetime.now(timezone.utc).isoformat(),points=len(current),
                uses_neighbor_filter=filtered,left_blocks=nearest(left),right_blocks=nearest(right),
                raw_left_blocks=nearest(raw_left),raw_right_blocks=nearest(raw_right))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=int,default=45)
    ap.add_argument('--output',type=Path,default=Path(__file__).with_name('TURNING-74504-BLOCK-POINTS.json'));args=ap.parse_args()
    receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'packets_sent':0,'status':[],
             'attitude':[],'scans':[],'radar_packets':0,'invalid_packets':0}
    last_angle=None;current=[];previous_scan=None;qualifier=NearQualifier()
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
                    for point in points(data,include_invalid=True):
                        qualifier.push(point)
                        if last_angle is not None and point['raw_angle']<last_angle:
                            # Wait another full turn so the last two points have
                            # their lookahead, even across the raw zero crossing.
                            if previous_scan is not None:
                                filtered=bool(receipt['status'] and receipt['status'][-1]['revision']>=74505)
                                receipt['scans'].append(scan_report(previous_scan,filtered))
                            previous_scan=current
                            current=[]
                        current.append(point);last_angle=point['raw_angle']
            except ValueError:receipt['invalid_packets']+=1
    receipt['ended_utc']=datetime.now(timezone.utc).isoformat()
    path=args.output
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status_count':len(receipt['status']),'last_status':receipt['status'][-1:],
                      'last_attitude':receipt['attitude'][-1:],'last_scan':receipt['scans'][-1:],
                      'invalid_packets':receipt['invalid_packets'],'packets_sent':0},indent=2))


if __name__=='__main__':main()
