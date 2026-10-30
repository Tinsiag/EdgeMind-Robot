"""Explicit single-profile A745 file list and board constraints."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CAMERA=ROOT.parent
def put(p,b):
 if not p.exists() or p.read_bytes()!=b:p.write_bytes(b)
def prepare():
 out=ROOT/'.local/platform';out.mkdir(parents=True,exist_ok=True);previous=ROOT/'vendor/board';vendor=[];origins=[]
 for name in sorted(p.name for p in previous.glob('*.v')):
  src=previous/name;dst=out/name;raw=src.read_bytes();put(dst,raw);vendor.append(dst);origins.append({'source':str(src),'sha256':hashlib.sha256(raw).hexdigest()})
 eth=CAMERA/'third_party/verilog-ethernet/rtl';vendor += [eth/n for n in ['axis_async_fifo.v','axis_gmii_tx.v','lfsr.v']]
 files=sorted((ROOT/'rtl').glob('*.v'))+sorted((ROOT/'lib').glob('*.v'))+sorted((ROOT/'vendor').glob('*.v'))+vendor
 for source,name in [('board.cst','a745.cst'),('timing.sdc','a745.sdc')]:put(out/name,(ROOT/'constraints'/source).read_bytes())
 sys.path.insert(0,str(ROOT/'host'));from board_config import compiled_parameters
 calibration=json.loads((ROOT/'config/calibration.json').read_text());geometry=json.loads((ROOT/'config/geometry.json').read_text())
 from generate_turn_envelope import check_current
 check_current(geometry)
 values,crc=compiled_parameters(geometry,calibration)
 if not calibration.get('motion_user_authorized'):raise ValueError('Motion authorization lock is not set')
 if any(not 100<=v<=20000 for v in calibration['wheel_cpr']):raise ValueError('Wheel CPR out of range')
 if any(not 10000<=v<=200000 for v in calibration['wheel_diameter_um']):raise ValueError('Wheel diameter out of range')
 values.update(LEFT_CPR=calibration['wheel_cpr'][0],RIGHT_CPR=calibration['wheel_cpr'][1],LEFT_DIAMETER=calibration['wheel_diameter_um'][0],RIGHT_DIAMETER=calibration['wheel_diameter_um'][1])
 params=''.join(f'defparam core.{k}={v};\n' for k,v in values.items())+f"defparam core.FUSION_CONFIG_CRC=32'h{crc:08x};\n";generated=out/'a745_top.v';put(generated,(ROOT/'rtl/a745_top.v').read_text(encoding='utf-8').replace('endmodule',params+'endmodule').encode());files=[p for p in files if p.name!='a745_top.v']+[generated]
 put(out/'provenance.json',(json.dumps({'vendor_inputs':origins,'parameters':values,'config_crc':crc,'network':'IPv4/UDP broadcast TX only; no command receiver','motor_pads_dynamic':True,'arm_on_boot':False},indent=2)+'\n').encode())
 return list(dict.fromkeys(files)),out
