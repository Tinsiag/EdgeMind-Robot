from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
P=Path(__file__).resolve().parent
OUT=P.parents[2]/'output/flash-interface-steady-20261028'
OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text())
r=json.loads((P/'REVIEW.json').read_text())
s=json.loads((P/'SIMULATION.json').read_text())
expected='e645958d0acabcc83e419cc04dc3fd22ba1ae0144fe64db8746233147519ee7a'
assert b['returncode']==0 and r['passed'] and s['passed']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256'] and sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert r['motor_pads_grounded'] and r['backlight_blinks'] is False
prior=P.parent/'interface-probe'
assert all(sha(P/n)==sha(prior/n) for n in ('probe.cst','probe.sdc','probe.gprj'))
assert all(sha(f)==sha(prior/f.relative_to(P)) for f in (P/'src').rglob('*') if f.is_file())
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(), 'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'sha256':expected, 'bitstream':str(P/'impl/pnr/probe.fs'), 'preflight_passed':True,
 'per_candidate_approval_required':False, 'motor_vm_state':'previous user confirmation retained; no reported change',
 'motor_pads_grounded':True, 'arm_authorized':False,
 'purpose':'Only remove intentional backlight blinking; retain displayed IOBUF/scanner/pins configuration; inspect reported sliding'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS steady probe, exact image/source/simulation/SDF hashes, identical scanner/PLL/CST/SDC; standing authorization applies')
print(r['sta_worst_slack_ns'])
print('LCD margin ns:',r['lcd_margin_ns'])
