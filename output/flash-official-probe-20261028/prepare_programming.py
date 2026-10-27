from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
P=ROOT/'output/tft800-official-20261028/official-probe-v3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text())
r=json.loads((P/'REVIEW.json').read_text())
s=json.loads((P/'SIMULATION.json').read_text())
expected='5f1c436e422728ed56d8b6f22c27134a7d9fe8f7831a9709fb38ba0990f9d250'
assert r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['returncode']==0 and not b['sources_changed']
assert sha(P/'impl/pnr/probe.fs')==b['artifact_sha256']==r['bitstream_sha256']==expected
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256']
assert sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['inputs'].items())
record={'recorded_utc':datetime.now(timezone.utc).isoformat(),
 'user_instruction':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'standing_programming_authorization':True,'per_candidate_approval_required':False,
 'scope':'This project implementation/delivery/diagnostics: checked FPGA bitstreams, external Flash54 at0, verify, Reprogram, Read Status',
 'bitstream':str(P/'impl/pnr/probe.fs'),'sha256':expected,
 'preflight_passed':True,'motor_pads_grounded':True,
 'power_state_source':'Most recent user confirmation in this continuous session: 同意烧录，VM 关闭且设备已通电; no reported change',
 'motor_vm_confirmed_off':True,'fpga_panel_programmer_powered':True,
 'arm_or_motion_authorized':False,'cold_boot_verified':False,
 'agents_before_sha256':sha(OUT/'AGENTS-before-authorization-change.md'),
 'agents_updated_sha256':sha(ROOT/'AGENTS.md')}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS candidate inputs/hash/STA/SDF/motor lock and standing authorization recorded')
