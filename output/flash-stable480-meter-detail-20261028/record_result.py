from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent;RUN=OUT/'20261027T190600.898056Z'
P=OUT.parent/'tft800-official-20261028/stable480-meter-probe-v3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((RUN/'audit.json').read_text());auth=json.loads((OUT/'AUTHORIZATION.json').read_text(encoding='utf-8'))
expected='5409ed97b235a6f54a71cdf274e83875e2ba1ef755863c3aafb131a6673d6863'
assert a['sha256']==sha(RUN/'image.fs')==sha(P/'impl/pnr/probe.fs')==auth['sha256']==expected
assert all(a[k] for k in ('flash_program_verify_completed','reload_command_completed','status_read_completed','configuration_ready','user_code_verified'))
assert all(s['returncode']==0 and s['state']=='completed' for s in a['steps'])
ops=[s['command'][s['command'].index('--run')+1] for s in a['steps']]
assert ops.count('54')==1 and ops.count('1')==1 and ops.count('73')==1 and set(ops)<={'54','1','74','73'}
assert a['read_user_code']==a['expected_user_code']=='0x0000A731'
assert 'Program and Verify Flash successfully.' in (RUN/'flash_program_verify.console.log').read_text()
assert auth['preflight_passed'] and all(sha(P/f)==h for f,h in auth['evidence_sha256'].items())
status={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'cable_only_passes_screen_reconnected_DE_fails_after_reseat',
 'bitstream_sha256':expected,'parent_bitstream_sha256':'afca1552286593e586758ca26ccc9107d8f45d36a84eb5b400effab8113ed119',
 'log_directory':str(RUN),'flash_program_verify_completed':True,'reload_completed':True,'configuration_ready':True,
 'user_code_verified':True,'read_user_code':a['read_user_code'],'final_status_register':a['final_status_register'],
 'status_sample_count':len(a['configuration_status_samples']),'application_verified':False,'cold_boot_verified':False,
 'pixel_clock_mhz':9,'active_raster_size':[480,272],'total_raster_size':[525,286],'sample_edge_hypothesis':'falling',
 'physical_panel_resolution_confirmed':False,'mapping':'AB22=DE AB21=high; no switching',
 'user_screen_report':'connected screen white; preceding candidate showed unstable color blocks',
 'user_led_report':'7灭，0-3亮，7亮，只有1亮',
 'connected_interpretation':'PLL/PCLK/HS/VS checks pass; DE edge count and duty fail; only DE stable readback mismatches; RGB/HS/VS/BL readback passes',
 'isolation_test':{'user_action':'all power off, disconnect TFT FPC at development board, power FPGA/programmer only; same Flash image',
  'user_result':'拔下屏幕后检查全部通过：D7灭时0～6全亮，D7亮时仅7亮',
  'all_pad_checks_pass':True,'firmware_changed_between_tests':False,
  'conclusion':'DE failure depends on connecting the display; same firmware also passes with cable attached to FPGA and display end open. Screen-end connector, attached cable contact/load, panel DE circuit or mounting contact still need distinction.',
  'cable_only_test':{'all_checks_pass':True,'setup':'original cable connected to FPGA, screen end disconnected'},
  'original_cable_reseated_and_display_connected':{'all_checks_pass':False,'pass_page_lit':[0,1,2,3],'error_page_lit_excluding_D7':[1]},
  'latest_user_report':'不接屏幕全部通过，接了屏幕依旧只有D1，D7同时亮，D7灭就0-3亮',
  'next_pending':'power off, isolate entire display module from metal mounting, reconnect original cable on insulating support, compare same diagnostic pages'},
 'DE_pin_trace':{'FPGA_ball':'AB22','development_board_J1':33,'display_user_FPC_J1':33,'documented_series_network':'RN7 pins1-8,33ohm','bare_panel_J2':34},
 'fpga_only_cold_start_observed':True,
 'led_pages':{'D7_off_lit_means_pass':{'D0':'PLL lock','D1':'PCLK frequency','D2':'HS count','D3':'VS count','D4':'DE edge count','D5':'DE duty samples','D6':'all checks'},
              'D7_on_lit_means_error':{'D0':'BL','D1':'DE','D2':'HS','D3':'VS','D4':'RGB[7:0]','D5':'RGB[15:8]','D6':'any RGB'}},
 'page_seconds':2**28/50000000,'measurement_seconds':1,
 'pad_measurement_boundary':'FPGA input buffers only; not the far cable end or analog integrity',
 'motor_pads_grounded':True,'arm_sent':False,'motion_started':False,'rewrite_attempted':False,
 'camera_sensors_network_active':False,'main_project_source_preserved':True,'standing_programming_authorization':True}
(OUT/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(P/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file() and p.name!='ARTIFACT-SHA256.json'},indent=2)+'\n')
(OUT/'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in [*RUN.iterdir(),OUT/'AUTHORIZATION.json',OUT/'STATUS.json',OUT/'EXTERNAL-DE-ISOLATION.json',OUT/'DE-PIN-TRACE.json',Path(__file__)] if p.is_file()},indent=2)+'\n')
print('PASS original Flash audit; cable-only passes, reseated display still DE-only failure; current image unchanged',a['final_status_register'])
