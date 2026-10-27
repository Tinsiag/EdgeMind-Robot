from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T175940.148023Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='7b218658353e5aea6d0d1a5708862742a6b750aaad10c92864006bacad25168d'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert '0x30000460' in (RUN/'read_status.console.log').read_text()
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'flash_verified_both_rotation_geometries_white_screen',
 'bitstream_sha256':expected,'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'status_register':'0x30000460',
 'application_verified':False,'cold_boot_verified':False,'pixel_clock_mhz':33,
 'rotation_clockwise_degrees':90,'expected_pattern':[['yellow','green','red','black'],['white','cyan','purple','blue']],
 'user_request':'方向搞反了，长宽对调了，你顺时针旋转90度试试',
 'user_connector_confirmation':'接的是用户接口 FPC接口','user_screen_report':'全是白屏','mode_seconds':8.064,
 'modes':[{'D6':False,'D7':False,'active':[800,480],'total':[1056,525],'rotation_scaled_to_landscape':True,'observation':'white screen'},
          {'D6':True,'D7':False,'active':[480,800],'total':[525,1056],'complete_axis_transpose':True,'observation':'white screen'}],
 'backlight_blinks':False,'de_backlight_mapping':'official AB22=DE AB21=constant-high',
 'portrait_raster_matches_confirmed_panel_datasheet':False,
 'camera_sensors_network_active':False,'main_project_source_preserved':True,
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,
 'standing_programming_authorization':True,'per_candidate_approval_required':False,'retry_attempted':False,
 'root_cause':'not established; user-directed rotation and axis-transpose comparison only'}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS staged SHA, Flash54/verify/reload/status; user reports both rotation geometries white; cold boot pending')
