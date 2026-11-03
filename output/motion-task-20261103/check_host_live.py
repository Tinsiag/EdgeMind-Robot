"""Exercise web target selection with motors unpowered, without local ARM."""
import hashlib,json,time,urllib.request
from pathlib import Path

def request(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request('http://127.0.0.1:8090/'+path,data=data,
        headers={'Content-Type':'application/json'} if data else {})
    with urllib.request.urlopen(req,timeout=4) as f:return json.load(f)

def main():
    deadline=time.monotonic()+20
    while True:
        try:
            before=request('task/status.json')
            if before.get('status'):break
        except (OSError,urllib.error.URLError):pass
        if time.monotonic()>deadline:raise RuntimeError('video/telemetry service not ready')
        time.sleep(.5)
    assert not before['status']['armed']
    original=before['label'];changes=[]
    for label in ['chair',original]:
        changes.append(request('task/config',{'label':label}));time.sleep(.5)
        current=request('task/status.json');assert current['label']==label
        assert current['action']==0 and not current['status']['armed'] and current['status']['targets']==[0,0]
    try:request('task/config',{'label':'red bottle'})
    except urllib.error.HTTPError as e:assert e.code==400
    else:raise AssertionError('non-COCO category accepted')
    one=request('status.json');time.sleep(10);two=request('status.json')
    assert two['infer_runs']>one['infer_runs'] and two['frames']>one['frames']
    assert not two['error'] and not two['display_error']
    final=request('task/status.json');assert not final['status']['armed'] and final['action']==0
    names=['vision_task.py','test_vision_task.py','fpga_video_yolo_web.py','receiver.py']
    clean=all(two[k]==one[k] for k in ('bad_packets','missing_rows','partial_frames'))
    result=dict(passed=clean,local_arm_used=False,web_target_selection_passed=True,
                invalid_class_rejected=True,start=one,end=two,task_before=before,task_after=final,
                host_sha256={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in names})
    Path('task-host-live.json').write_text(json.dumps(result,indent=2)+'\n')
    assert clean, {k:two[k]-one[k] for k in ('bad_packets','missing_rows','partial_frames')}
    print(json.dumps(dict(passed=True,revision=final['status']['revision'],armed=False,
                         camera_fps=two['fps'],inference_runs=two['infer_runs']-one['infer_runs'],
                         web_fps=two['stream_fps'],preview_confirmed=final['preview_confirmed'],
                         calibrated=final['calibrated'])))
if __name__=='__main__':main()
