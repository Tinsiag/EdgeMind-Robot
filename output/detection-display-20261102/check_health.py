"""Audit passive wire/telemetry evidence after programming FW74512."""
import argparse
import hashlib
import json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('capture',type=Path)
    args=ap.parse_args()
    r=json.loads(args.capture.read_text(encoding='utf-8'))
    s=r['statuses'];a=r['attitudes']
    assert r['read_only'] and r['motion_packets_sent']==0
    assert len(s)>=250 and len(a)>=250
    assert all(x['revision']==74512 and x['state']==0 and x['faults']==0 and
               not x['armed'] and x['targets']==[0,0] and x['speeds']==[0,0] for x in s)
    assert all(x['camera_ready'] and x['ddr_ready'] and x['frame_ready'] and
               not x['video_error'] and x['camera_error']==0 and x['imu_valid'] and
               x['gyro_valid'] and x['imu_errors']==0 for x in s)
    assert all(x['cpu_alive'] and not x['cpu_fault'] and x['tilt_valid'] for x in a)
    assert a[-1]['cpu_progress']>a[0]['cpu_progress']
    assert not r['invalid_return_frames'] and r['wire_return_count']>=120
    assert abs(r['accepted_delta']-r['wire_return_count'])<=5
    assert 4<=r['inference_hz']<=5.5 and r['camera_hz']>=25 and r['web_hz']>=12
    begin=r['web_start'];end=r['web_end']
    for field in ('bad_packets','partial_frames','missing_rows'):
        assert end[field]==begin[field],field
    assert not end['error'] and not end['display_error']
    result=dict(passed=True,firmware_revision=74512,status_count=len(s),attitude_count=len(a),
                elapsed_seconds=r['elapsed_seconds'],accepted_delta=r['accepted_delta'],
                return_frames=r['wire_return_count'],camera_hz=r['camera_hz'],
                inference_hz=r['inference_hz'],web_hz=r['web_hz'],
                inference_runs=end['infer_runs']-begin['infer_runs'],
                checksum_offload_pending=sum(x.get('nic_checksum_completion_pending',False) for x in r['return_frames']),
                checksum_note='Outgoing local capture may precede NIC checksum completion. FPGA acceptance validates nonzero UDP checksum and MAC FCS.',
                armed=False,motion_packets_sent=0,hardware_display_observed=False,
                capture_sha256=hashlib.sha256(args.capture.read_bytes()).hexdigest(),
                audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    dest=args.capture.with_name(args.capture.stem+'-review.json')
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
