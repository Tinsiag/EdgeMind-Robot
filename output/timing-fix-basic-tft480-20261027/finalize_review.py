"""Verify the evidence chain and publish offline readiness; no hardware I/O."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
PROJECT=REPO/'code/camera-car-control/a741-fpga-fusion'
BUILD=PROJECT/'.local/gowin-basic-tft480-screen-test'
EVIDENCE=OUT/'build-evidence-final'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

b=read(BUILD/'result.json');r=read(OUT/'regression/result.json')
t=read(OUT/'TIMING-REVIEW.json');x=read(OUT/'TX-SKEW-REVIEW.json')
c=read(OUT/'CONSTRAINT-TARGETS.json');p=read(OUT/'PHYSICAL-REVIEW.json')
assert b['compile_passed'] and b['synthesis_reused'] and not b['sources_changed']
assert t['numeric_checks_pass'] and x['passed'] and c['routed_netlist_used']
assert len(r['rtl_passed'])==37 and r['host_tests']==41
for field,inputs in [('build',b['source_sha256']),('regression',r['input_sha256'])]:
    assert all(sha(Path(path))==digest for path,digest in inputs.items()),field
common=set(b['source_sha256'])&set(r['input_sha256'])
assert all(b['source_sha256'][name]==r['input_sha256'][name] for name in common)
assert x['bitstream_sha256']==b['artifact_sha256']==sha(EVIDENCE/'a741.fs')
assert x['sdf_sha256']==sha(EVIDENCE/'a741.sdf')
assert x['physical_netlist_sha256']==c['routed_netlist_sha256']==sha(EVIDENCE/'a741.vo')
assert c['netlist_sha256']==p['netlist_sha256']==b['synthesis_netlist_sha256']==sha(EVIDENCE/'a741.vg')
initial=read(OUT/'attempt-01-constraint-error/result.json')
assert sha(OUT/'attempt-01-constraint-error/a741.vg')==b['synthesis_netlist_sha256']
# Only SDC/CST and export-only build.py changed after the completed synthesis.
def synthesis_inputs(values):
    return {name:digest for name,digest in values.items() if Path(name).suffix not in ('.cst','.sdc') and Path(name)!=PROJECT/'scripts/build.py'}
assert synthesis_inputs(initial['source_sha256'])==synthesis_inputs(b['source_sha256'])
assert all('.I(GND)' in value for value in p['motor_obufs'].values()) and len(p['motor_obufs'])==4
assert all(p['cmd_do_options'].values())
prov=read(EVIDENCE/'provenance.json')
assert all(v['original_sha256']==v['sha256'] for v in prov['files'].values())
assert not read(OUT/'WARNINGS.json')['pnr_warnings']
physical=(EVIDENCE/'a741.rpt.txt').read_text(encoding='utf-8')
assert re.search(r'(?m)^\s*pll125\s*\|\s*PRIMARY\s*\|',physical)
preview=(OUT/'FLASH-PREVIEW.txt').read_text(encoding='utf-8-sig')
assert 'PREVIEW ONLY' in preview and '--run 54 --spiaddr 0x000000' in preview
stamp=datetime.now(timezone.utc).isoformat()
save(OUT/'VALIDATION-CHAIN.json',{'verified_utc':stamp,'regression_rtl':37,'regression_python':41,
    'regression_input_count':len(r['input_sha256']),'build_input_count':len(b['source_sha256']),
    'common_input_count':len(common),'all_current_inputs_match':True,'same_synthesis_netlist_reused':True,
    'synthesis_origin':'attempt-01-constraint-error/a741.vg (synthesis completed; failure was subsequent SDC parsing)',
    'synthesis_netlist_sha256':b['synthesis_netlist_sha256'],'ddr_originals_unchanged':True,
    'final_artifact_sha256':b['artifact_sha256'],'motor_pads_grounded':True,'hardware_programmed':False})
save(OUT/'STATUS.json',{'status':'offline_checks_passed_ready_for_screen_test_power_confirmation',
    'recorded_utc':stamp,'compile_passed':True,'timing_numeric_checks_pass':True,'timing_signed_off':True,
    'signoff_scope':'This motor-locked screen-test image; scoped vendor DDR calibration/reset model and 0.2ns Ethernet PCB skew budget. Hardware and cold boot unverified.',
    'programming_ready':True,'requires_current_vm_off_and_board_ready_confirmation':True,
    'motion_release_allowed':False,'motor_pads_grounded':True,'rtl_tests_passed':37,'python_tests_passed':41,
    'route_option':1,'place_option':1,'timing_driven':True,'correct_hold':True,
    'worst_slack_ns':t['worst_reported_slack_ns'],'tx_worst_abs_pad_skew_ns':x['worst_abs_skew_ns'],
    'tx_skew_margin_including_board_budget_ns':x['margin_ns'],
    'artifact':str(EVIDENCE/'a741.fs'),'artifact_sha256':b['artifact_sha256'],
    'final_pnr_driver_seconds':b['seconds'],'hardware_programmed':False,'cold_boot_verified':False,
    'camera_ddr_tft_hardware_verified':False,'imu_hardware_verified':False,'network_hardware_verified':False})
tracked=list(EVIDENCE.iterdir())+list((OUT/'regression').glob('*.log'))+[OUT/'regression/result.json']
tracked += [OUT/name for name in ('STATUS.json','TIMING-REVIEW.json','PHYSICAL-REVIEW.json','TX-SKEW-REVIEW.json','CONSTRAINT-TARGETS.json','VALIDATION-CHAIN.json','FLASH-PREVIEW.txt')]
save(OUT/'ARTIFACT-SHA256.json',{str(path.relative_to(OUT)):sha(path) for path in tracked if path.is_file()})
print('PASS: current sources, full regression, reused synthesis, final STA/SDF, motor lock and archived image all agree. No hardware operation.')
