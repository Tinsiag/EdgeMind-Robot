from pathlib import Path
import json,shutil,subprocess,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
previous=ROOT/'output/white-screen-basic-tft480-20261027'
for name in ('inspect_implementation.py','audit_constraint_targets.py','audit_tx_sdf.py','finalize_review.py'):
    text=(previous/name).read_text(encoding='utf-8').replace('gowin-basic-tft480','gowin-basic-tft800')
    if name=='inspect_implementation.py':
        text=text.replace('"tx125m": 125}', '"tx125m": 125, "display33m":33}')
    if name=='finalize_review.py':
        text=text.replace("len(r['rtl_passed'])==39", "len(r['rtl_passed'])==43").replace("'rtl_tests':39", "'rtl_tests':43").replace("'rtl_tests_passed':39", "'rtl_tests_passed':43")
        text=text.replace("t=read(OUT/'TIMING-REVIEW.json');", "lcd=read(OUT/'TFT-PAD-TIMING.json');assert lcd['passed']\nt=read(OUT/'TIMING-REVIEW.json');")
        text=text.replace("assert x['sdf_sha256']==sha(EVIDENCE/'a741.sdf')", "assert x['sdf_sha256']==lcd['sdf_sha256']==sha(EVIDENCE/'a741.sdf')")
        text=text.replace("'tx_worst_abs_pad_skew_ns':x['worst_abs_skew_ns'],", "'tft_min_setup_ns':lcd['minimum_setup_ns'],'tft_min_hold_ns':lcd['minimum_hold_ns'],\n    'tft_margin_ns':lcd['margin_ns'],'tx_worst_abs_pad_skew_ns':x['worst_abs_skew_ns'],")
        text=text.replace('094862d12885cd786f3d5efb676205a9a999ff64e244b533e72ef538b4b2c8ee','7434d07af48de4ad1814326e26c67485aca8da5b7e4f4eed5064a1f84fddf2ea')
        text=text.replace('0.2ns Ethernet PCB skew budget;', '0.2ns Ethernet PCB skew budget, 8ns TFT receiver setup/hold with1ns unmeasured LCD interconnect skew +0.3ns clock reserve;')
        text=text.replace("'status':'diagnostic_candidate_offline_verified_awaiting_trial_authorization'", "'status':'tft800_33mhz_candidate_offline_verified_awaiting_trial_authorization','panel_size':[800,480],'pixel_clock_mhz':33")
    (OUT/name).write_text(text,encoding='utf-8')
cmd=[sys.executable,'-X','utf8',str(ROOT/'code/camera-car-control/a741-fpga-fusion/scripts/build.py'),'prepare','--display-diagnostic']
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
assert r.returncode==2 and '--display-diagnostic requires --screen-test' in r.stderr
(OUT/'DIAGNOSTIC-GUARD.json').write_text(json.dumps({'command':cmd,'returncode':r.returncode,'stderr':r.stderr,'unsafe_variant_rejected_before_prepare':True},indent=2),encoding='utf-8')
