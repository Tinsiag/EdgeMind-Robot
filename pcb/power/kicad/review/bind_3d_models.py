"""Bind portable STEP models; preserve every non-model S-expression exactly."""
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime
from collections import Counter

from kicad_tools import ROOT, STEM, Node, parse, children, prop, apply_edits

STOCK = Path(r'D:\KiCad\10.0\share\kicad\3dmodels')
TEMP = Path(r'C:\Users\Shan_\AppData\Local\Temp\codex-power-3d')
MODELS = ROOT / '3dmodels'
LIBRARY = ROOT / 'ProPrj_pow-easyedapro.pretty'


def config(source, name=None, offset=(0,0,0), rotation=(0,0,0), note='KiCad library geometric equivalent'):
    return dict(source=source, file=name or Path(source).name, offset=offset,
                scale=(1,1,1), rotation=rotation, note=note)


MAPPING = {
    'R0603': config('Resistor_SMD.3dshapes/R_0603_1608Metric.step'),
    'C0603': config('Capacitor_SMD.3dshapes/C_0603_1608Metric.step'),
    'C0805': config('Capacitor_SMD.3dshapes/C_0805_2012Metric.step'),
    'LED_0603': config('LED_SMD.3dshapes/LED_0603_1608Metric.step',offset=(-0.05075,-0.0075,0)),
    'SOD-123_L2.7-W1.8-LS3.7-RD': config('Diode_SMD.3dshapes/D_SOD-123.step'),
    'TSOT-23-8_L2.9-W1.6-P0.65-LS2.8-BL': config('Package_TO_SOT_SMD.3dshapes/TSOT-23-8.step',rotation=(0,0,-90)),
    'CONN-TH_LAIL-PZ2.54-8P-L': config('Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x08_P2.54mm_Vertical.step',offset=(-8.89,0,0),rotation=(0,0,-90)),
    'HDR-TH_LAIL-PM2.54-7P-L': config('Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x07_P2.54mm_Vertical.step',offset=(-7.62,0,0),rotation=(0,0,-90)),
    'CONN-TH_6P-P2.50_BX-XH2.54-6PZZ': config('Connector_JST.3dshapes/JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical.step',offset=(-6.25,0,0),note='XH geometry substitute; pin pitch 2.50 mm, not manufacturer-exact'),
    'TYPE-C-SMD_LAIL-TYPE-C-16PIN-08-WT': config('Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step',offset=(0,-1.30,0),note='GCT geometric substitute; shell pins align after PCB-y +1.30 mm offset; not LAIL OEM CAD'),
    'IND-SMD_L7.3-W6.6': config('Inductor_SMD.3dshapes/L_TechFuse_SL0630.step',note='0630 geometric substitute, 7.12 x 6.60 x 3.00 mm; PSA maximum package 7.3 x 6.6 x 3.0 mm, independent of inductance'),
    'SW-TH_SS-12D10L5': config('@author',name='SS-12D10L5.step',rotation=(-90,0,0),note='Public SS-12D10L5 CAD by McFLY; matching +/-4.7 mm terminal positions, not OEM mechanical sign-off'),
    'CONN-TH_XT60PW-M': config('@local',name='XT60PW-M.step',offset=(-12.35,0,4.2),rotation=(-90,0,90),note='Detailed XT60PW-M SolidWorks STEP from Northeastern Rover Electrical Team CADLAB library; original 7 solids, full housing and contacts; body 18.2 x 15.5 x 8.4 mm, both contacts and retention tabs aligned'),
}
for name in ['R0603_R4','R0603_R5','R0603_R8','R0603_R9','R0603_R15']:
    MAPPING[name] = MAPPING['R0603'].copy()
for name in ['C0805_C58','C0805_C59','C0805_C60','C0805_C61']:
    MAPPING[name] = MAPPING['C0805'].copy()


def without_models(node):
    if isinstance(node, Node):
        return [without_models(x) for x in node if not (isinstance(x,Node) and x and x[0]=='model')]
    return str(node)


def model_text(cfg):
    def vec(values):
        return ' '.join(str(v) for v in values)
    return ('(model "${KIPRJMOD}/3dmodels/' + cfg['file'] + '"\n'
            '\t\t(offset (xyz ' + vec(cfg['offset']) + '))\n'
            '\t\t(scale (xyz ' + vec(cfg['scale']) + '))\n'
            '\t\t(rotate (xyz ' + vec(cfg['rotation']) + '))\n\t)')


def edit_model(text, node, cfg):
    models = children(node,'model')
    replacement = model_text(cfg) if cfg else ''
    if models:
        edits = [(models[0].start,models[0].end,replacement)]
        edits += [(m.start,m.end,'') for m in models[1:]]
    else:
        edits = [(node.end-1,node.end-1,'\n\t'+replacement+'\n')] if cfg else []
    return edits


def main():
    MODELS.mkdir(exist_ok=True)
    for cfg in MAPPING.values():
        target = MODELS / cfg['file']
        if cfg['source'] == '@author':
            shutil.copy2(TEMP / 'SS12-author.step',target)
        elif cfg['source'] == '@local':
            assert target.is_file(), target
        else:
            shutil.copy2(STOCK / cfg['source'],target)
    shutil.copy2(TEMP / 'KiCad-LICENSE.md',MODELS / 'KiCad-LICENSE.md')
    paths = [ROOT / (STEM+'.kicad_pcb')] + sorted(LIBRARY.glob('*.kicad_mod'))
    backup = ROOT / 'review' / '3d-backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True,exist_ok=False)
    prepared, rows = [], []
    board_edits = []
    for path in paths:
        data = path.read_bytes()
        text = data.decode('utf-8')
        parsed = parse(text)
        nodes = children(parsed,'footprint') if path.suffix=='.kicad_pcb' else [parsed]
        edits = []
        for node in nodes:
            name = str(node[1]).split(':')[-1]
            if name == 'MountingHole_3mm':
                assert not children(node,'model')
                continue
            cfg = MAPPING[name]
            edits.extend(edit_model(text,node,cfg))
            if path.suffix=='.kicad_pcb':
                rows.append(dict(reference=prop(node,'Reference'),footprint=name,**cfg))
        after = apply_edits(text,edits)
        assert without_models(parsed)==without_models(parse(after)),path
        prepared.append((path,data,after))
    # Refuse to overwrite any file changed by another editor during preparation.
    for path,data,after in prepared:
        assert path.read_bytes()==data, f'Concurrent edit: {path}'
    for path,data,after in prepared:
        target = backup / path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        path.write_text(after,encoding='utf-8',newline='')
    report = dict(physical_footprints=len(rows)+4,model_bindings=len(rows),mechanical_holes_without_models=4,
                  local_library_files=len(paths)-1,unique_models=len({r['file'] for r in rows}),
                  non_model_data_unchanged=True,backup=str(backup),bindings=sorted(rows,key=lambda x:x['reference']))
    (ROOT/'review'/'3d-model-bindings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='bindings'},indent=2))


if __name__=='__main__':
    main()
