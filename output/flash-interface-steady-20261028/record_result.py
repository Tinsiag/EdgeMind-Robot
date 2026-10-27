from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
OUT=Path(__file__).resolve().parent
RUN=OUT/'20261027T173410.261585Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='e645958d0acabcc83e419cc04dc3fd22ba1ae0144fe64db8746233147519ee7a'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert '0x30000460' in (RUN/'read_status.console.log').read_text()
status={'recorded_utc':datetime.now(timezone.utc).isoformat(), 'status':'flash_verified_application_failed_white_screen',
 'bitstream_sha256':expected,'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'status_register':'0x30000460',
 'user_screen_report':'又变成全白或没有图案','user_led_report':'D3亮，D4闪，D5亮',
 'previous_blinking_image_clarification':'滚动的彩色色条，不是正确固定八色块',
 'application_verified':False,'cold_boot_verified':False,'panel_size':[800,480],'pixel_clock_mhz':33,
 'backlight_blinks':False,'backlight_startup_seconds':0.2,
 'camera_sensors_network_active':False,'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,
 'standing_programming_authorization':True,'per_candidate_approval_required':False,'retry_attempted':False,
 'root_cause':'not established; check actual module user-interface vs raw-panel pin definitions before further changes'}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS exact flash image/log evidence; display failed, pad activity observed; no full application/cold boot acceptance')
