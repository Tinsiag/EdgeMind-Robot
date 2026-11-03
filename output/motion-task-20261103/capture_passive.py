"""Passive UDP listener and HTTP reader; never sends a robot command."""
import argparse,json,socket,time,urllib.request
from pathlib import Path
from receiver import decode_status,decode_attitude

def web(path):
    with urllib.request.urlopen('http://127.0.0.1:8090/'+path,timeout=3) as f:return json.load(f)

def main():
    a=argparse.ArgumentParser();a.add_argument('--seconds',type=float,default=60);a.add_argument('--out',required=True)
    p=a.parse_args();s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1048576)
    s.bind(('',6103));s.settimeout(.2)
    statuses=[];attitudes=[];tasks=[];radars=0;bad=0;accepted=0;previous=None
    start=web('status.json');task_start=web('task/status.json');t=time.monotonic()
    while time.monotonic()-t<p.seconds:
        try:data,peer=s.recvfrom(2048)
        except socket.timeout:continue
        if peer!=('192.168.0.2',6103):continue
        try:
            if data[:4]==b'EMS1':
                value=decode_status(data);value['received_seconds']=time.monotonic()-t
                value['detection_accepted_mod256']=data[23];statuses.append(value)
                if previous is not None:accepted+=(data[23]-previous)&255
                previous=data[23]
            elif data[:4]==b'EMF1':attitudes.append(decode_attitude(data))
            elif data[:4]==b'EMT1':tasks.append(dict(hex=data.hex(),received_seconds=time.monotonic()-t))
            elif data[:4]==b'EML1':radars+=1
        except (ValueError,IndexError):bad+=1
    end=web('status.json');task_end=web('task/status.json');elapsed=time.monotonic()-t
    result=dict(read_only=True,motion_packets_sent=0,elapsed_seconds=elapsed,statuses=statuses,attitudes=attitudes,
                task_packets=tasks,radar_packets=radars,invalid_packets=bad,accepted_delta=accepted,
                web_start=start,web_end=end,task_start=task_start,task_end=task_end,
                inference_hz=(end['infer_runs']-start['infer_runs'])/elapsed,
                camera_hz=(end['frames']-start['frames'])/elapsed,
                web_hz=(end['rendered_frames']-start['rendered_frames'])/elapsed)
    Path(p.out).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('statuses','attitudes','task_packets','web_start','web_end','task_start','task_end')},indent=2))
if __name__=='__main__':main()
