from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T182636.840017Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='7c0e06d8a814430e7b22d2a09787f55ccca7f3c1686df8786b0c4c4afa29e198'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed','configuration_ready','user_code_verified'))
assert all(s['returncode']==0 and s['state']=='completed' for s in a['steps'])
ops=[s['command'][s['command'].index('--run')+1] for s in a['steps']]
assert ops.count('54')==1 and ops.count('1')==1 and ops.count('73')==1 and set(ops)<={'54','1','74','73'}
assert a['read_user_code']==a['expected_user_code']=='0x0000A72E'
assert a['final_status_register']=='0x70022020'
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'flash_ready_version_matched_polarity_change_no_improvement',
 'bitstream_sha256':expected,'parent_bitstream_sha256':'14ebf7bd68522b0cc13a710f325d5a1ecde147afd3766c53f35affc7dd32b22f',
 'log_directory':str(RUN),'flash_program_verify_completed':True,'reload_completed':True,'status_read_completed':True,
 'initial_status_register':a['configuration_status_samples'][0]['raw'],'final_status_register':a['final_status_register'],
 'configuration_ready':True,'user_code_verified':True,'read_user_code':a['read_user_code'],'status_sample_count':len(a['configuration_status_samples']),
 'application_verified':False,'cold_boot_verified':False,'pixel_clock_mhz':33,'panel_size':[800,480],
 'sole_rtl_change':'invert PCLK from observed rolling-block control-mapping candidate',
 'sample_edge_hypothesis':'falling; rising not timing qualified by this candidate',
 'user_request':'你把我们刚刚能显示滑块的那个拿来再改改','user_screen_report':'跟之前一样的结果',
 'comparison_reference':'prior14ebf7bd: normal bright/moving, swapped dim/random static, bothDE dim/moving; user reports no change with invertedPCLK','mode_seconds':8.064,
 'modes':[{'D6':False,'D7':False,'AB22':'DE','AB21':'high','observation':None},
          {'D6':True,'D7':False,'AB22':'high','AB21':'DE','observation':None},
          {'D6':False,'D7':True,'AB22':'DE','AB21':'DE','observation':None}],
 'camera_sensors_network_active':False,'main_project_source_preserved':True,'motor_pads_grounded':True,
 'arm_sent':False,'motion_started':False,'standing_programming_authorization':True,'per_candidate_approval_required':False,
 'rewrite_attempted':False,'status_read_only_polling':True,'programming_tool_offline_tests_passed':16}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS staged image/Flash/ready/UserCode; user reports polarity change has no improvement; application not accepted')
