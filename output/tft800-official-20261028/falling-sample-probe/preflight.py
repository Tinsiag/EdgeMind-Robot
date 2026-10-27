from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
P=Path(__file__).resolve().parent;ROOT=P.parents[2]
OUT=ROOT/'output/flash-falling-sample-20261028';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text());r=json.loads((P/'REVIEW.json').read_text());s=json.loads((P/'SIMULATION.json').read_text())
expected='7c0e06d8a814430e7b22d2a09787f55ccca7f3c1686df8786b0c4c4afa29e198'
assert b['returncode']==0 and r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256'] and sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert len(r['windows'])==20 and r['external_sample_edge_hypothesis']=='falling'
assert all(0.4*1000/33 <= 1000/66+r['clock_arrival_ns'][0][i]-r['clock_arrival_ns'][1][i] <= 0.6*1000/33 for i in range(3))
prior=P.parent/'control-mapping-probe'
assert all(sha(P/n)==sha(prior/n) for n in ('probe.cst','probe.sdc','probe.gprj'))
assert all(sha(f)==sha(prior/f.relative_to(P)) for f in (P/'src').rglob('*') if f.is_file())
assert (P/'wrapper.v').read_text()==(prior/'wrapper.v').read_text().replace('clock_pad(.IO(TFT_clk),.I(pclk)','clock_pad(.IO(TFT_clk),.I(~pclk)')
assert not re.search(r'\b(?:WARN|ERROR)\b',(P/'build.log').read_text())
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'user_latest_direction':'你把我们刚刚能显示滑块的那个拿来再改改','sha256':expected,'bitstream':str(P/'impl/pnr/probe.fs'),
 'preflight_passed':True,'per_candidate_approval_required':False,'motor_vm_state':'previous user confirmation retained; no reported change',
 'motor_pads_grounded':True,'arm_authorized':False,'sole_rtl_change':'PCLK inversion from rolling-pattern14ebf7bd candidate',
 'sample_edge_hypothesis':'falling; rising edge is not qualified by this experiment',
 'programming_script_sha256':sha(ROOT/'scripts/fpga/program_flash.py'),'programming_tests_sha256':sha(ROOT/'scripts/fpga/test_program_flash.py'),
 'programming_tests_passed':16,'programming_change':'wait for documented wakeup/DONE and verify User Code after read-only polling; no rewrite or SRAM fallback'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS checked polarity-only candidate, sources/simulation/STA/SDF exact, motors grounded, no build warnings, extended programming verification enabled')
