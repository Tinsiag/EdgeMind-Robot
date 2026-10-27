from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T185643.796440Z'
P=OUT.parent/'tft800-official-20261028/stable480-meter-probe-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text());auth=json.loads((OUT/'AUTHORIZATION.json').read_text(encoding='utf-8'))
expected='afca1552286593e586758ca26ccc9107d8f45d36a84eb5b400effab8113ed119'
assert a['sha256']==sha(RUN/'image.fs')==sha(P/'impl/pnr/probe.fs')==auth['sha256']==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed','configuration_ready','user_code_verified'))
assert all(s['returncode']==0 and s['state']=='completed' for s in a['steps'])
ops=[s['command'][s['command'].index('--run')+1] for s in a['steps']]
assert ops.count('54')==1 and ops.count('1')==1 and ops.count('73')==1 and set(ops)<={'54','1','74','73'}
assert a['read_user_code']==a['expected_user_code']=='0x0000A730'
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert auth['preflight_passed'] and all(sha(P/f)==h for f,h in auth['evidence_sha256'].items())
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'flash_ready_version_matched_fixed480_pad_meter_scan_and_readback_failed',
 'bitstream_sha256':expected,'parent_bitstream_sha256':'163ea290fec887007502fb65886d914a5e893249d9f04e5dde49d22bdec195cc',
 'log_directory':str(RUN),'flash_program_verify_completed':True,'reload_completed':True,'configuration_ready':True,
 'user_code_verified':True,'read_user_code':a['read_user_code'],'final_status_register':a['final_status_register'],
 'status_sample_count':len(a['configuration_status_samples']),'application_verified':False,'cold_boot_verified':False,
 'pixel_clock_mhz':9,'active_raster_size':[480,272],'total_raster_size':[525,286],'sample_edge_hypothesis':'falling',
 'physical_panel_resolution_confirmed':False,'mapping':'AB22=DE AB21=high; no switching','user_screen_report':'全白',
 'user_led_report':['D0,D1,D3,D4亮，1，2闪，6，7灭，全白','D5灭'],
 'interpretation':'PLL/PCLK ratio/BL reported good; HS/VS/DE aggregate scan test and stable RGB/control readback test failed. Individual failing signal not yet identified.',
 'led_meanings':{'D0':'PLL lock','D1':'50MHz heartbeat','D2':'pad VS frame heartbeat','D3':'backlight pad high','D4':'pad pixel clock frequency correct','D5':'pad HS/VS/DE aggregate scan counts correct','D6':'pad RGB/control stable-region comparison correct','D7':'PLL and D4/5/6 all pass'},
 'pad_measurement_boundary':'FPGA pad input buffers only; not the far end of the cable, analog integrity or panel sampling',
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,'rewrite_attempted':False,
 'camera_sensors_network_active':False,'main_project_source_preserved':True,'standing_programming_authorization':True}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(P/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file() and p.name!='ARTIFACT-SHA256.json'},indent=2)+'\n')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS verified Flash/ready/UserCode0xA730; user reports white screen and scan/readback failures',a['final_status_register'])
