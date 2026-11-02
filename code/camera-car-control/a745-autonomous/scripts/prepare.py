"""Explicit single-profile A745 file list and board constraints."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CAMERA=ROOT.parent
def put(p,b):
 if not p.exists() or p.read_bytes()!=b:p.write_bytes(b)
def prepare():
 out=ROOT/'.local/platform';out.mkdir(parents=True,exist_ok=True);previous=ROOT/'vendor/board';vendor=[];origins=[]
 for name in sorted(p.name for p in previous.glob('*.v')):
  src=previous/name;dst=out/name;raw=src.read_bytes();generated=raw
  if name=='ethernet_pll_mod.v':
   old=b'defparam PLLA_inst.ODIV1_SEL = 6;'
   assert raw.count(old)==1
   generated=raw.replace(old,b'defparam PLLA_inst.ODIV1_SEL = 3;')
   generated=generated.replace(b'CLKOUT1 = 750/6 = 125 MHz (RGMII/MAC);',b'CLKOUT1 = 750/3 = 250 MHz (dedicated CLKDIV/2 -> RGMII/MAC);')
  put(dst,generated);vendor.append(dst);origins.append({'source':str(src),'sha256':hashlib.sha256(raw).hexdigest(),'generated_sha256':hashlib.sha256(generated).hexdigest(),'transform':'ODIV1 6 -> 3; dedicated CLKDIV/2 restores 125MHz' if generated!=raw else 'byte-identical'})
 eth=CAMERA/'third_party/verilog-ethernet/rtl';vendor += [eth/n for n in ['axis_async_fifo.v','axis_async_fifo_adapter.v','axis_gmii_rx.v','axis_gmii_tx.v','eth_mac_1g.v','eth_mac_1g_fifo.v','lfsr.v']]
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
 put(out/'provenance.json',(json.dumps({'vendor_inputs':origins,'parameters':values,'config_crc':crc,'network':'IPv4/UDP video/telemetry TX; ED10 display-only RX; no motion commands','motor_pads_dynamic':True,'arm_on_boot':False},indent=2)+'\n').encode())
 return list(dict.fromkeys(files)),out
