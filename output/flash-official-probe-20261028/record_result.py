from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
OUT=Path(__file__).resolve().parent
RUN=OUT/'20261027T171645.948638Z'
a=json.loads((RUN/'audit.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert a['sha256']=='5f1c436e422728ed56d8b6f22c27134a7d9fe8f7831a9709fb38ba0990f9d250'
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
assert sha(RUN/'image.fs')==a['sha256']
status={'status':'flash_verified_application_failed_white_screen','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'bitstream_sha256':a['sha256'],'log_directory':str(RUN),'flash_program_verify_completed':True,
 'reload_completed':True,'status_read_completed':True,'device':'GW5AT-60B','status_register':'0x30000460',
 'panel_size':[800,480],'pixel_clock_mhz':33,'diagnostic':'official chapter28 eight colour blocks with reset/output retiming adapter',
 'main_project_source_preserved':True,'camera_sensors_network_active':False,
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,'retry_attempted':False,
 'application_verified':False,'cold_boot_verified':False,'user_screen_report':'仍然全白',
 'standing_programming_authorization':True,'per_candidate_approval_required':False,
 'led_map':{'D0':'constant-on candidate marker, not PLL status','D1':'50MHz system counter heartbeat','D2':'16-frame heartbeat','D3-D7':'off'}}
(OUT/'STATUS.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
tracked=[*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',OUT/'AGENTS-before-authorization-change.md']
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in tracked if p.is_file()},indent=2)+'\n')
print('PASS Flash54/verify/reload/status and exact staged SHA; visual/cold-boot pending')
