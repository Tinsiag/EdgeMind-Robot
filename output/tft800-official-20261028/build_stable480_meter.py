from pathlib import Path
import hashlib,json,shutil,subprocess,time
BASE=Path(__file__).resolve().parent
SRC=BASE/'official480-9mhz-probe';OUT=BASE/'stable480-meter-probe-v3';OUT.mkdir(exist_ok=True)
shutil.copytree(SRC/'src',OUT/'src',dirs_exist_ok=True)
for name in ('probe.gprj','probe.cst','build.tcl'):shutil.copy2(SRC/name,OUT/name)
shutil.copy2(BASE/'stable480_meter_wrapper.v',OUT/'wrapper.v')
(OUT/'build.tcl').write_text((OUT/'build.tcl').read_text().replace('0000A72F','0000A731'))
(OUT/'probe.sdc').write_text('''create_clock -name sys_clk -period 20 [get_ports {clk50M}]
create_generated_clock -name lcd9m -source [get_ports {clk50M}] -multiply_by 9 -divide_by 50 [get_pins {official/Gowin_PLL/u_pll/PLLA_inst/CLKOUT0}]
set_max_delay 10 -to [get_ports {TFT_rgb[*] TFT_hs TFT_vs TFT_de}]
set_false_path -to [get_pins {official/tft_ready_*/CLEAR}]
set_max_delay 10 -to [get_pins {read_s1_*/D expect_s1_*/D clock_sync_0_s0/D lock_sync_0_s0/D}]
set_false_path -hold -to [get_pins {read_s1_*/D expect_s1_*/D clock_sync_0_s0/D lock_sync_0_s0/D}]
''')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in OUT.rglob('*') if p.is_file() and 'impl' not in p.parts and p.suffix in ('.v','.sdc','.cst','.gprj','.tcl')]
hashes={str(p.relative_to(OUT)):sha(p) for p in files}
start=time.time()
with (OUT/'build.log').open('w',encoding='utf-8') as log:
 r=subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(OUT/'build.tcl')],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
assert r.returncode==0 and all(sha(OUT/f)==h for f,h in hashes.items())
(OUT/'result.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.time()-start,'source_sha256':hashes,'sources_changed':False,
 'artifact_sha256':sha(OUT/'impl/pnr/probe.fs'),'hardware_programmed':False,
 'basis':'previous official480/9MHz inverted PCLK; fixed official mapping plus independent pad frequency/raster/data monitors'},indent=2)+'\n')
print('BUILD COMPLETE; separate STA/SDF, simulation and preflight still required',sha(OUT/'impl/pnr/probe.fs'))
