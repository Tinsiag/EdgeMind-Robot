from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T180428.643947Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='2733c1ea9b04b421ff639bd8765ec90519c3738a56610cc2cf5f107fcf324912'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert '0x30000460' in (RUN/'read_status.console.log').read_text()
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'flash_verified_rotated_swapped_white_screen_brightness_changes_only',
 'bitstream_sha256':expected,'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'status_register':'0x30000460',
 'application_verified':False,'cold_boot_verified':False,'pixel_clock_mhz':33,
 'rotation_clockwise_degrees':90,'expected_pattern':[['yellow','green','red','black'],['white','cyan','purple','blue']],
 'user_latest_direction':'是不是得交换 DE／背光','user_connector_confirmation':'接的是用户接口 FPC接口',
 'user_screen_report':'还是全白，唯一不同的是每几秒屏幕变暗，变亮','mode_seconds':8.064,
 'modes':[{'D6':False,'D7':False,'active':[800,480],'total':[1056,525],'rotation_scaled_to_landscape':True,'observation':None},
          {'D6':True,'D7':False,'active':[480,800],'total':[525,1056],'complete_axis_transpose':True,'observation':None}],
 'de_backlight_mapping':'swapped AB21=DE AB22=constant-high',
 'portrait_raster_matches_confirmed_panel_datasheet':False,
 'camera_sensors_network_active':False,'main_project_source_preserved':True,
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,
 'standing_programming_authorization':True,'per_candidate_approval_required':False,'retry_attempted':False,
 'root_cause':'not established; user-directed swapped control lines applied to unchanged rotation comparison'}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS staged SHA, Flash54/verify/reload/status; user reports white screen with brightness changes; no display acceptance')
