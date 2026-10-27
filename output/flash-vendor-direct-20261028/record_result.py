from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T180951.853657Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='39352f551ef022aaac90608eb79614d189565b56c68a01675225f7deab1490a6'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
status_text=(RUN/'read_status.console.log').read_text()
import re
code=re.search(r'Status Code is:\s*(0x[0-9a-fA-F]+)',status_text);assert code
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'original_vendor_flash_verified_display_failed_white_screen',
 'bitstream_sha256':expected,'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'status_register':code[1],
 'no_recompile':True,'no_rtl_changes':True,'no_constraint_changes':True,'no_bitstream_changes':True,
 'original_vendor_zip_matches':True,'application_verified':False,'cold_boot_verified':False,
 'user_request':'你先直接先把官方的烧进去得了，看看能不能显示，能显示了再考虑差异',
 'user_screen_report':'仍然全白或无图案','reset_and_complete_power_cycle_result':'用户确认：两步都做了，仍然全白',
 'user_performed_complete_power_cycle':True,'cold_boot_display_check_passed':False,
 'post_cold_boot_readonly_verification':{'status_register':'0x70026020','user_code':'0x0000FBC9','configuration_ready':True,'version_matches_original_header':True,'document':'UG718-1.0.4 table5-1; wakeup bit30 and done_final bit13'},
 'expected_pattern':[['black','blue'],['red','purple'],['green','cyan'],['yellow','white']],
 'camera_sensors_network_active':False,'main_project_source_preserved':True,
 'motor_pads_grounded':False,'unused_pins_vendor_configuration':'input tri-state with pull-up',
 'motor_vm_must_remain_off':True,'arm_sent':False,'motion_started':False,
 'diagnostic_led_map_applicable':False,'standing_programming_authorization':True,
 'per_candidate_approval_required':False,'retry_attempted':False,
 'timing_signoff_for_vendor_artifact_available':False,'qualification':'manufacturer original display trial only; not full application or motion validation'}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS original image/staging/Flash evidence; reset/cold boot display failed per user; later read-only check confirms wakeup/DONE and original UserCode')
