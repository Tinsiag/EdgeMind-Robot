from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent
RUN=OUT/'20261027T174627.948084Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text())
expected='14ebf7bd68522b0cc13a710f325d5a1ecde147afd3766c53f35affc7dd32b22f'
assert a['sha256']==sha(RUN/'image.fs')==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert '0x30000460' in (RUN/'read_status.console.log').read_text()
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'flash_verified_all_mapping_modes_failed_correct_pattern',
 'bitstream_sha256':expected,'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'status_register':'0x30000460',
 'application_verified':False,'cold_boot_verified':False,'panel_size':[800,480],'pixel_clock_mhz':33,
 'user_connector_confirmation':'接的是用户接口 FPC接口',
 'user_screen_report':'D6、D7都灭：屏幕变亮，色块滑动；仅D6亮：色块固定且每次固定的色块随机，屏幕变暗一点；仅D7亮：色块滑动且屏幕变暗',
 'mode_seconds':8.064,
 'modes':[{'D7':False,'D6':False,'AB22':'DE','AB21':'high','observation':'brighter, moving colour blocks'},
          {'D7':False,'D6':True,'AB22':'high','AB21':'DE','observation':'dimmer, static but random blocks each visit'},
          {'D7':True,'D6':False,'AB22':'DE','AB21':'DE','observation':'dimmer, moving blocks'}],
 'camera_sensors_network_active':False,'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,
 'standing_programming_authorization':True,'per_candidate_approval_required':False,'retry_attempted':False,
 'root_cause':'not established; AB21 brightness follows expected BL duty; holding AB22 high stops movement without correct pixels, not proof of swapped pins; check sync/panel timing'}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS staged SHA, Flash54/verify/reload/status; all three mapping modes fail correct stable pattern per user')
