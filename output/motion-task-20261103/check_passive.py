"""Check actual FW74513 idle capture; no physical-motion acceptance implied."""
import hashlib,json,struct
from pathlib import Path

def main():
    path=Path(__file__).with_name('HEALTH-74513.json');d=json.loads(path.read_text())
    s=d['statuses'];a=d['attitudes'];packets=d['task_packets']
    assert d['read_only'] and d['motion_packets_sent']==0 and d['invalid_packets']==0
    assert len(s)>=400 and len(a)>=400 and len(packets)>=400
    assert all(x['revision']==74513 and x['state']==0 and x['faults']==0 and not x['armed'] and
               x['targets']==[0,0] and x['speeds']==[0,0] for x in s)
    assert all(x['camera_ready'] and x['camera_error']==0 and x['ddr_ready'] and x['frame_ready'] and
               not x['video_error'] and x['imu_valid'] and x['gyro_valid'] and x['imu_errors']==0 for x in s)
    assert all(x['cpu_alive'] and not x['cpu_fault'] and x['tilt_valid'] for x in a)
    assert a[-1]['cpu_progress']>a[0]['cpu_progress']
    for p in packets:
        b=bytes.fromhex(p['hex']);assert len(b)==64 and b[:4]==b'EMT1'
        assert struct.unpack_from('<HHI',b,4)==(1,64,74513)
        assert b[24:28]==bytes([0,1,0,0]) and struct.unpack_from('<i',b,28)[0]==0
    start,end=d['web_start'],d['web_end']
    assert all(end[k]==start[k] for k in ['bad_packets','partial_frames','missing_rows'])
    assert not end['error'] and not end['display_error']
    assert abs(d['accepted_delta']-(end['display_sent']-start['display_sent']))<=3
    assert d['camera_hz']>=25 and d['web_hz']>=12 and 4<=d['inference_hz']<=5.5
    result=dict(passed=True,firmware_revision=74513,read_only=True,motion_packets_sent=0,
        status_count=len(s),attitude_count=len(a),mission_packet_count=len(packets),
        elapsed_seconds=d['elapsed_seconds'],camera_hz=d['camera_hz'],web_hz=d['web_hz'],
        inference_hz=d['inference_hz'],detection_accepted_delta=d['accepted_delta'],
        new_bad_packets=0,new_partial_frames=0,new_missing_rows=0,
        hardware_display_observed=False,motion_verified=False,cold_boot_verified=False,
        task_approach_verified=False,target_calibration_verified=False,
        capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        review_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path.with_name('HEALTH-74513-REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
