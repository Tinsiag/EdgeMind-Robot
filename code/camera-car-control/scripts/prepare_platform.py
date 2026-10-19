"""Import original ACG720 example dependencies without changing the archives."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from check_fpga import ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', type=Path, default=Path(
        'C:/Users/Administrator/Documents/ACG720-GW5AT60K例程文件/GW5AT60K'))
    args = parser.parse_args()
    target = ROOT / '.local/platform'
    original = target / 'original'
    original.mkdir(parents=True, exist_ok=True)
    provenance = {'archives': {}, 'files': {}, 'adaptations': [
        'Use chapter 47 RGB565 table with 800x480 scaler enabled and DVP test disabled.',
        'Evaluate the constant ROM on addr changes so Icarus and synthesis agree.',
        'Keep TY-OV5640 P7 wiring from the verified DDR3 project; do not use example P4 pins.',
        'RX_CTL is rising DV, rising XOR falling error; original example exposed raw halves.',
        'Keep manufacturer PLL and MDIO implementation; MAC supports 1Gbps only.'
    ]}
    selected = {47: ['src/camera_init/ov5640_init_table_rgb.v'],
                59: ['src/gowin_pll/gowin_pll.v', 'src/gowin_pll/gowin_pll_mod.v',
                     'src/pll_init.v', 'src/mdio/mdio_bit_shift.v', 'src/mdio/phy_reg_config.v',
                     'src/gmii_rgmii_gmii/gmii_to_rgmii.v']}
    for chapter, names in selected.items():
        archive = next(args.examples.glob(f'第{chapter}章*/*.zip'))
        provenance['archives'][str(chapter)] = {'path': str(archive), 'sha256': sha(archive.read_bytes())}
        with ZipFile(archive) as z:
            for name in names:
                data = z.read(name)
                dest = original / f'ch{chapter}' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                provenance['files'][name] = {'chapter': chapter, 'sha256': sha(data)}
    raw_rom = (original / 'ch47/src/camera_init/ov5640_init_table_rgb.v').read_bytes()
    try:
        rom = raw_rom.decode('utf-8-sig')
    except UnicodeDecodeError:
        rom = raw_rom.decode('gb18030')
    rom = rom.replace('\r\n', '\n').replace('\r', '\n')
    if rom.count("24'h5001_83") != 1 or rom.count("24'h503D_00") != 1:
        raise SystemExit('Unexpected original RGB565 table')
    rom = rom.replace("24'h5001_83", "24'h5001_a3")
    rom = re.sub(r'always\s*@\s*\(\s*\*\s*\)', 'always @(addr)', rom)
    rom = re.sub(r'(rom\s*\[)252(:0\])', r'\g<1>253\2', rom)
    rom = rom.replace("rom[252] = 24'h503D_00;", "rom[253] = 24'h4741_00;\n    rom[252] = 24'h503D_00;")
    # Preserve original comments and provenance in a local generated dependency.
    adapted = target / 'ov5640_init_table_rgb.v'
    adapted.write_text(rom, encoding='utf-8')
    provenance['adapted_rom_sha256'] = sha(adapted.read_bytes())
    (target / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    roles = {
        ROOT / 'rtl/acg720_camera_car_top.v': ['board_top'],
        ROOT / 'rtl/ov5640_board_init.v': ['camera_init'],
        ROOT / 'rtl/acg720_rgmii_rx.v': ['rgmii_phy'],
        adapted: ['camera_init'],
        ROOT.parent / 'fpga/acg720-ddr3/rtl/camera_init/ov5640_ctrl.v': ['camera_init'],
        ROOT.parent / 'fpga/acg720-ddr3/rtl/camera_init/sccb_master.v': ['camera_init'],
    }
    for path in (original / 'ch59').rglob('*.v'):
        roles[path] = ['clocking'] if 'pll' in str(path).lower() else ['rgmii_phy']
    roles[ROOT / 'constraints/acg720_camera_car.cst'] = ['pins']
    roles[ROOT / 'constraints/acg720_camera_car.sdc'] = ['timing']
    files = []
    import os
    for path, entry_roles in roles.items():
        if not path.is_file():
            raise SystemExit(f'Missing integration source: {path}')
        kind = {'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}[path.suffix]
        files.append({'path': Path(os.path.relpath(path, target)).as_posix(), 'type': kind,
                      'sha256': sha(path.read_bytes()), 'roles': entry_roles})
    manifest = {'part':'GW5AT-LV60PG484AC1/I0','top':'acg720_camera_car_top','files':files}
    (target / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding='utf-8')
    print('Prepared manufacturer platform and verified file hashes: ' + str(target))


if __name__ == '__main__':
    main()
