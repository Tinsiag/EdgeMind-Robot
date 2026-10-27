from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
OUT=Path(__file__).resolve().parent
RUN=OUT/'20261027T165845.165609Z'
a=json.loads((RUN/'audit.json').read_text())
assert a['sha256']=='d5e558ad68ac665f889fcec651262714e52e40774853e5368c51f0fc2a1ad62b'
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed'))
assert len(a['steps'])==3 and all(s['returncode']==0 for s in a['steps'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(RUN/'image.fs')==a['sha256']
record={'status':'flash_verified_application_failed_white_screen','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'bitstream_sha256':a['sha256'],'log_directory':str(RUN),'flash_program_verify_completed':True,'reload_completed':True,
 'status_read_completed':True,'device':'GW5AT-60B','idcode':'0x0001481B','status_register':'0x30000460',
 'panel_size':[800,480],'pixel_clock_mhz':33,'application_verified':False,'cold_boot_verified':False,
 'user_display_report':'仍然全白','led_report_pending':True,'motor_vm_confirmed_off':True,
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,'automatic_retry_attempted':False}
(OUT/'STATUS.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json'] if p.is_file()},indent=2)+'\n')
print(record['status'])
