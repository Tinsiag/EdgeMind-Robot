from pathlib import Path
BASE=Path(__file__).resolve().parent
t=(BASE/'review_official480_9_probe.py').read_text().replace(" / 'official480-9mhz-probe'", " / 'stable480-meter-probe-v2'")
start=t.index('pad_inputs={}');end=t.index('windows={}',start)
t=t[:start]+'''pad_inputs={}
for name,(kind,ports) in logic.items():
 if kind!='IOBUF':continue
 assert ports['OEN']=='GND'
 ff='clock_sync_0_s0' if name=='clock_pad' else 'read_s1_'+str(19 if name=='bl_pad' else 18 if name=='de_pad' else 17 if name=='hs_pad' else 16 if name=='vs_pad' else int(re.search(r'\\[(\\d+)\\]',name)[1]))+'_s0'
 assert logic[ff][1]['D']==ports['O'],(name,ff,ports,logic[ff])
 pad_inputs[name]={'input_net':ports['O'],'first_sampler':ff}
 ports['O']=ports['IO']
assert len(pad_inputs)==21
assert logic['bl_pad'][1]['I']=='VCC'
''' + t[end:]
t=t.replace("p['O']=='TFT_clk'", "p['O'] in ('TFT_clk','TFT_pwm')")
t=t.replace('len(windows)==20','len(windows)==19').replace('margin=min(setup,hold)-8-1-.3','margin=min(setup,hold)-10-1-.3')
t=t.replace("'required_setup_hold_ns':8", "'required_setup_hold_ns':10,'receiver_budget_basis':'AT043TN24 PDF pages11/12; panel model still a hypothesis'")
t=t.replace("'mapping_mode_frames':480,'mapping_mode_seconds':480*525*286/9000000,", "'mapping':'fixed official AB22=DE and AB21=high','meter_window_reference_cycles':50000000,")
t=t.replace("'resolution_hypothesis_trial':True", "'resolution_hypothesis_trial':True,'independent_pad_meters':True")
t=t.replace("'motor_pads_grounded':True,", "'motor_pads_grounded':True,'prior_meter_attempt_failed_output_maxdelay_and_not_programmed':True,")
(BASE/'review_stable480_meter.py').write_text(t)
