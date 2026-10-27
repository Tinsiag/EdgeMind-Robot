from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, html
P=Path(__file__).resolve().parent;ROOT=P.parents[2]
OUT=ROOT/'output/flash-stable480-meter-detail-20261028';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'result.json').read_text());r=json.loads((P/'REVIEW.json').read_text());s=json.loads((P/'SIMULATION.json').read_text())
expected='5409ed97b235a6f54a71cdf274e83875e2ba1ef755863c3aafb131a6673d6863'
assert b['returncode']==0 and r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['artifact_sha256']==r['bitstream_sha256']==sha(P/'impl/pnr/probe.fs')==expected
assert all(sha(P/f)==h for f,h in b['source_sha256'].items())
assert all(sha(Path(f))==h for f,h in s['input_sha256'].items())
assert sha(P/'impl/pnr/probe.sdf')==r['sdf_sha256'] and sha(P/'impl/pnr/probe.vo')==r['vo_sha256']
assert all(v is not None and v>0 for v in r['sta_worst_slack_ns'].values())
assert len(r['windows'])==19 and len(r['pad_input_buffers_verified'])==21
assert r['required_setup_hold_ns']==10 and r['lcd_margin_ns']>0
assert r['external_sample_edge_hypothesis']=='falling'
prior=P.parent/'official480-9mhz-probe'
assert all(sha(f)==sha(prior/f.relative_to(P)) for f in (P/'src').rglob('*') if f.is_file())
assert all(sha(P/f)==sha(prior/f) for f in ('probe.cst','probe.gprj'))
assert sha(P/'wrapper.v')==sha(P.parent/'stable480_meter_wrapper.v')
assert all(0.4*1000/9<=1000/18+r['clock_arrival_ns'][0][i]-r['clock_arrival_ns'][1][i]<=0.6*1000/9 for i in range(3))
vo=(P/'impl/pnr/probe.vo').read_text()
for name,value in (('IDIV_SEL',2),('MDIV_SEL',36),('ODIV0_SEL',100)):
 assert re.search(r'defparam\s+\\official/Gowin_PLL/u_pll/PLLA_inst\s+\.'+name+'='+str(value)+';',vo)
assert '//UserCode: 0x0000a731' in (P/'impl/pnr/probe.fs').read_text()
assert not re.search(r'\b(?:WARN|ERROR)\b',(P/'build.log').read_text())
pins={'TFT_clk':'AB20','TFT_hs':'V19','TFT_vs':'Y19','TFT_de':'AB22','TFT_pwm':'AB21','left_in1':'A18','left_in2':'A19','right_in1':'F13','right_in2':'F14'}
pins.update({f'TFT_rgb[{i}]':v for i,v in enumerate('R18 R14 P14 U18 U17 N13 R16 P15 P17 N17 T18 L6 N15 R17 P16 N14'.split())})
rows=[list(map(html.unescape,re.findall(r'<td[^>]*>(.*?)</td>',row,re.S))) for row in re.findall(r'<tr>(.*?)</tr>',(P/'impl/pnr/probe.pin.html').read_text(),re.S)]
for port,pin in pins.items():
 assert any(row and row[0]==port and any(cell.split('/')[0]==pin for cell in row) for row in rows),(port,pin)
evidence=['result.json','REVIEW.json','SIMULATION.json','simulation.log','build.log','impl/pnr/probe.tr','impl/pnr/probe.sdf','impl/pnr/probe.vo','impl/pnr/probe.pin.html','impl/pnr/cmd.do','impl/pnr/device.cfg']
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_standing_authorization':'烧录，然后修改这个规定，你可以不用我授权直接烧写',
 'sha256':expected,'bitstream':str(P/'impl/pnr/probe.fs'),'preflight_passed':True,'per_candidate_approval_required':False,
 'motor_vm_state':'previous user confirmation retained; no reported change','motor_pads_grounded':True,'arm_authorized':False,
 'change':'Fixed official AB22=DE/AB21=high, actual21 pad readback, 50MHz-referenced 9MHz/line/frame/DE counters, stable-window RGB/control comparisons',
 'physical_panel_resolution_confirmed':False,'sample_edge_hypothesis':'falling','main_project_modified':False,
 'previous_failed_meter_build':'stable480-meter-probe: output delays exceeded original10ns constraint; not programmed. v2 removes output FF fanout so IO packing is restored; same constraint passes.',
 'actual_pin_map':pins,'evidence_sha256':{f:sha(P/f) for f in evidence},
 'programming_script_sha256':sha(ROOT/'scripts/fpga/program_flash.py'),
 'configuration_verification':'wait for documented wakeup/DONE and verify UserCode0x0000A731; no rewrite or SRAM fallback'}
(OUT/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS source/image/STA/SDF/21IOBUF paths, fault-injection tests, motorGND, official pin map and actual PLL9MHz; SHA',expected)
