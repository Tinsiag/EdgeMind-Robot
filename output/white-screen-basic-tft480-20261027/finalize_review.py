"""Freeze a reviewable diagnostic candidate; never opens the programmer."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
PROJECT=REPO/'code/camera-car-control/a741-fpga-fusion'
BUILD=PROJECT/'.local/gowin-basic-tft480-screen-test-diagnostic'
EVIDENCE=OUT/'build-evidence-final'
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

b=read(BUILD/'result.json');r=read(OUT/'regression/result.json')
t=read(OUT/'TIMING-REVIEW.json');x=read(OUT/'TX-SKEW-REVIEW.json')
c=read(OUT/'CONSTRAINT-TARGETS.json');p=read(OUT/'PHYSICAL-REVIEW.json')
assert b['compile_passed'] and not b['sources_changed'] and b['display_diagnostic'] and b['screen_test']
assert t['numeric_checks_pass'] and x['passed'] and c['routed_netlist_used']
assert len(r['rtl_passed'])==39 and r['host_tests']==41
for label,inputs in [('build',b['source_sha256']),('regression',r['input_sha256'])]:
    assert all(sha(Path(path))==digest for path,digest in inputs.items()),label
common=set(b['source_sha256'])&set(r['input_sha256'])
assert all(b['source_sha256'][name]==r['input_sha256'][name] for name in common)
assert x['bitstream_sha256']==b['artifact_sha256']==sha(EVIDENCE/'a741.fs')
assert x['sdf_sha256']==sha(EVIDENCE/'a741.sdf')
assert x['physical_netlist_sha256']==c['routed_netlist_sha256']==sha(EVIDENCE/'a741.vo')
assert c['netlist_sha256']==p['netlist_sha256']==b['synthesis_netlist_sha256']==sha(EVIDENCE/'a741.vg')
assert len(p['motor_obufs'])==4 and all('.I(GND)' in value for value in p['motor_obufs'].values())
assert all(p['cmd_do_options'].values())
prov=read(EVIDENCE/'provenance.json')
assert prov['display_diagnostic'] and prov['motor_locked']
assert all(v['original_sha256']==v['sha256'] for v in prov['files'].values())
assert not read(OUT/'WARNINGS.json')['pnr_warnings']
physical=(EVIDENCE/'a741.rpt.txt').read_text(encoding='utf-8')
assert re.search(r'(?m)^\s*pll125\s*\|\s*PRIMARY\s*\|',physical)
preview=(OUT/'FLASH-PREVIEW.txt').read_text(encoding='utf-8-sig')
assert 'PREVIEW ONLY' in preview and '--run 54 --spiaddr 0x000000' in preview
assert read(OUT/'DIAGNOSTIC-GUARD.json')['unsafe_variant_rejected_before_prepare']
stamp=datetime.now(timezone.utc).isoformat()
save(OUT/'VALIDATION-CHAIN.json',{'verified_utc':stamp,'rtl_tests':39,'python_tests':41,
    'regression_input_count':len(r['input_sha256']),'build_input_count':len(b['source_sha256']),
    'common_input_count':len(common),'all_current_inputs_match':True,
    'ddr_originals_unchanged':True,'artifact_sha256':b['artifact_sha256'],
    'motor_pads_grounded':True,'candidate_hardware_programmed':False})
save(OUT/'STATUS.json',{'status':'diagnostic_candidate_offline_verified_awaiting_trial_authorization',
    'recorded_utc':stamp,'compile_passed':True,'timing_numeric_checks_pass':True,'timing_signed_off':True,
    'signoff_scope':'Motor-locked diagnostic only, scoped vendor DDR calibration/reset model and 0.2ns Ethernet PCB skew budget; no hardware/cold-boot validation.',
    'programming_ready':True,'new_trial_authorization_required':True,
    'motor_pads_grounded':True,'motion_release_allowed':False,'rtl_tests_passed':39,'python_tests_passed':41,
    'route_option':1,'place_option':1,'timing_driven':True,'correct_hold':True,
    'worst_slack_ns':t['worst_reported_slack_ns'],'tx_worst_abs_pad_skew_ns':x['worst_abs_skew_ns'],
    'tx_skew_margin_including_board_budget_ns':x['margin_ns'],'artifact':str(EVIDENCE/'a741.fs'),
    'artifact_sha256':b['artifact_sha256'],'full_build_seconds':b['seconds'],
    'candidate_hardware_programmed':False,'cold_boot_verified':False,'white_screen_fixed':False,
    'currently_flashed_sha256':'094862d12885cd786f3d5efb676205a9a999ff64e244b533e72ef538b4b2c8ee',
    'currently_flashed_application_passed':False})
tracked=list(EVIDENCE.iterdir())+list((OUT/'regression').glob('*.log'))+[OUT/'regression/result.json']
tracked += [p for p in OUT.iterdir() if p.is_file() and p.suffix in ('.json','.py','.txt') and p.name!='ARTIFACT-SHA256.json']
save(OUT/'ARTIFACT-SHA256.json',{str(path.relative_to(OUT)):sha(path) for path in tracked if path.is_file()})
print('PASS diagnostic candidate: frozen sources/regression/implementation/SDF/motor pads agree; no additional hardware write.')
