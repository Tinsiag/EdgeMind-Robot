"""Archive the manufacturer's supplied bitstream byte-for-byte; never compile."""
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile
import hashlib,json,re,shutil
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
SRC=Path('C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料/02_例程源码/GW5AT60K/第28章 TFT显示屏驱动设计与验证')
OUT=BASE/'vendor-direct-original';OUT.mkdir(exist_ok=True)
FLASH=ROOT/'output/flash-vendor-direct-20261028';FLASH.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected='39352f551ef022aaac90608eb79614d189565b56c68a01675225f7deab1490a6'
image=SRC/'impl/pnr/tft_ctrl.fs';assert sha(image)==expected
header='\n'.join(image.read_text().splitlines()[:24])
assert '//Device: GW5AT-60' in header and '//Device Version: B' in header
assert '//Part Number: GW5AT-LV60PG484AC1/I0' in header and '//JTAGAsRegularIO: OFF' in header
files=[SRC/'tft_ctrl.gprj',SRC/'impl/project_process_config.json',SRC/'impl/gwsynthesis/tft_ctrl.vg',image,*[p for p in (SRC/'src').rglob('*') if p.is_file()]]
manifest={}
for p in files:
 rel=p.relative_to(SRC);dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(p,dest);assert sha(p)==sha(dest)
 manifest[str(rel)]={'source':str(p),'sha256':sha(p),'copy_identical':True}
zipfile=SRC/'ch28_tft_ctrl.zip';zip_matches={}
with ZipFile(zipfile) as z:
 for name in z.namelist():
  if name.endswith('/impl/pnr/tft_ctrl.fs') or name=='impl/pnr/tft_ctrl.fs':
   zip_matches[name]=hashlib.sha256(z.read(name)).hexdigest()
assert zip_matches and all(h==expected for h in zip_matches.values()),zip_matches
config=json.loads((SRC/'impl/project_process_config.json').read_text())
assert config['TopModule']=='tft_ctrl_test'
assert config['Unused_Pin']=='As_input_tri_stated_with_pull_up'
pins=dict(re.findall(r'IO_LOC "([^"]+)" (\w+);',(SRC/'src/tft_ctrl.cst').read_text()))
assert len(pins)==23 and pins['TFT_clk']=='AB20' and pins['TFT_de']=='AB22' and pins['TFT_pwm']=='AB21'
assert not set(pins.values()) & {'A18','A19','F13','F14'}
record={'recorded_utc':datetime.now(timezone.utc).isoformat(),'source_directory':str(SRC),
 'source_bitstream':str(image),'archived_bitstream':str(OUT/'impl/pnr/tft_ctrl.fs'),'bitstream_sha256':expected,
 'vendor_archive_sha256':sha(zipfile),'zip_bitstream_sha256':zip_matches,'source_files':manifest,
 'tool_version':'vendor V1.9.11.03 (81277)','vendor_build_date':'2025-07-09',
 'target_device':'GW5AT-60B PBGA484A','no_recompile':True,'no_rtl_edits':True,'no_constraint_edits':True,
 'no_bitstream_edits':True,'cpu_gpio_option_in_vendor_config':config['CPU'],'sspi_gpio_option_in_vendor_config':config['SSPI'],
 'security_bit_from_vendor_header':'ON','jtag_regular_io_from_vendor_header':'OFF',
 'unused_pins_from_vendor_config':config['Unused_Pin'],'motor_pads_grounded':False,
 'motor_outputs_not_defined_by_vendor_top':True,'motor_vm_must_remain_off':True,
 'timing_signoff_for_vendor_artifact_available':False,'hardware_qualification':'original manufacturer comparison only; not full application or motion signoff',
 'user_explicit_direction':'你先直接先把官方的烧进去得了，看看能不能显示，能显示了再考虑差异'}
(OUT/'ORIGIN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
auth={'recorded_utc':datetime.now(timezone.utc).isoformat(),'user_request':record['user_explicit_direction'],
 'standing_programming_authorization':True,'per_candidate_approval_required':False,'sha256':expected,
 'bitstream':str(OUT/'impl/pnr/tft_ctrl.fs'),'original_file_and_archive_match':True,'no_source_or_bitstream_changes':True,
 'motor_vm_state':'previous user confirmation retained; reminded to remain off','motor_pads_grounded':False,
 'arm_authorized':False,'vendor_original_trial_only':True}
(FLASH/'AUTHORIZATION.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS exact vendor file equals original ZIP artifact, target GW5AT-60B, original source/CST copied byte-for-byte; NO COMPILE')
print(expected)
