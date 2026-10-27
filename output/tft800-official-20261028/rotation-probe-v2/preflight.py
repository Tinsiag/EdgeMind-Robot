from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
P=Path(__file__).resolve().parent
OUT=P.parents[2]/'output/flash-rotation-probe-20261028';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text());r=json.loads((P/'REVIEW.json').read_text());s=json.loads((P/'SIMULATION.json').read_text())
expected='7b218658353e5aea6d0d1a5708862742a6b750aaad10c92864006bacad25168d'
assert b['returncode']==0 and r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256'] and sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert sha(P/'src/rotation_scan.v')==sha(P.parent/'rotation_scan.v')
assert len(r['windows'])==19 and r['rotation_clockwise_degrees']==90 and not r['backlight_blinks']
prior=P.parent/'interface-probe'
assert all(sha(P/n)==sha(prior/n) for n in ('probe.cst','probe.sdc'))
assert all(sha(P/'src'/n)==sha(prior/'src'/n) for n in ('gowin_pll/gowin_pll.v','gowin_pll/gowin_pll_mod.v','pll_init.v'))
assert not re.search(r'\b(?:WARN|ERROR)\b',(P/'build.log').read_text())
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'user_rotation_request':'不用了，我可以肯定的是你的方向搞反了，长宽对调了，你顺时针旋转90度试试',
 'sha256':expected,'bitstream':str(P/'impl/pnr/probe.fs'),'preflight_passed':True,'per_candidate_approval_required':False,
 'user_connector_confirmation':'接的是用户接口 FPC接口','motor_vm_state':'previous user confirmation retained; no reported change',
 'motor_pads_grounded':True,'arm_authorized':False,'purpose':'90degree clockwise image and480x800 transposed raster comparison; normal DE/BL mapping, constant BL, no power/wiring changes'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS exact image/source/simulation/SDF hashes, unchanged PLL/CST/SDC, no build warnings/errors; rotation experiment authorized')
print(r['sta_worst_slack_ns'])
