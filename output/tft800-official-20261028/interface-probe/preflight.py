from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
P=Path(__file__).resolve().parent
ROOT=P.parents[2]
OUT=ROOT/'output/flash-interface-probe-20261028';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text());r=json.loads((P/'REVIEW.json').read_text());s=json.loads((P/'SIMULATION.json').read_text())
expected='b7cb31acf792c9650a6e99299a5a077af61f5b6976d7af662ca295d47f13510b'
assert b['returncode']==0 and r['passed'] and s['passed']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert r['sdf_sha256']==sha(P/'impl/pnr/probe.sdf') and r['vo_sha256']==sha(P/'impl/pnr/probe.vo')
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'per_candidate_approval_required':False,'sha256':expected,'bitstream':str(P/'impl/pnr/probe.fs'),
 'preflight_passed':True,'motor_vm_state':'previous user confirmation retained; no reported change',
 'motor_pads_grounded':True,'arm_authorized':False,'purpose':'observe backlight control and realIOBUF pad readback; no new wiring'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS checked interface probe; standing authorization applies')
