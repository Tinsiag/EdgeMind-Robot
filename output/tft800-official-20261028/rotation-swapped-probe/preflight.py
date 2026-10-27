from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
P=Path(__file__).resolve().parent;OUT=P.parents[2]/'output/flash-rotation-swapped-20261028';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text());r=json.loads((P/'REVIEW.json').read_text());s=json.loads((P/'SIMULATION.json').read_text())
expected='2733c1ea9b04b421ff639bd8765ec90519c3738a56610cc2cf5f107fcf324912'
assert b['returncode']==0 and r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256'] and sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert len(r['windows'])==19 and 'TFT_pwm' in r['windows'] and 'TFT_de' not in r['windows']
assert r['rotation_clockwise_degrees']==90 and r['AB21_driven_with_DE'] and r['AB22_driven_high']
prior=P.parent/'rotation-probe-v2'
assert all(sha(P/n)==sha(prior/n) for n in ('probe.cst','probe.sdc','probe.gprj'))
assert all(sha(f)==sha(prior/f.relative_to(P)) for f in (P/'src').rglob('*') if f.is_file())
assert not re.search(r'\b(?:WARN|ERROR)\b',(P/'build.log').read_text())
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'user_latest_direction':'是不是得交换 DE／背光','sha256':expected,'bitstream':str(P/'impl/pnr/probe.fs'),
 'preflight_passed':True,'per_candidate_approval_required':False,'motor_vm_state':'previous user confirmation retained; no reported change',
 'motor_pads_grounded':True,'arm_authorized':False,'purpose':'Exact same rotated800x480/480x800 raster with onlyDE/BL output roles exchanged; no permanent mapping conclusion'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS exact image/source/simulation/SDF hashes; scanner/PLL/CST/SDC unchanged from rotation-v2; onlyDE/BL output roles swapped; standing authorization')
