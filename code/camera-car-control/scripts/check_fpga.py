"""Elaborate the integration core; intentionally does not build a board bitstream."""
import argparse
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sources():
    motion = ROOT.parent / 'fpga/acg720-motion-control'
    vision = ROOT.parent / 'fpga/acg720-vision-motion/rtl'
    project = ET.parse(motion / 'acg720_motion_sync.gprj')
    files = [motion / node.attrib['path'] for node in project.findall('.//File')
             if node.attrib.get('type') == 'file.verilog']
    files += [vision / name for name in ('reset_sync.v', 'dvp_capture_continuous.v',
                                       'capture_tokens.v', 'async_fifo.v')]
    files += [ROOT / 'rtl/video_udp_packetizer.v', ROOT / 'rtl/camera_motion_core.v']
    files += [ROOT / 'rtl' / name for name in ('udp_uart_control.v', 'ethernet_udp_router.v', 'camera_ethernet_core.v')]
    files += sorted((ROOT / 'third_party/verilog-ethernet/rtl').glob('*.v'))
    return files


def tool(name, supplied=None):
    value = supplied or shutil.which(name)
    local = REPO / 'tmp/vision-motion-tools/bin' / (name + '.exe')
    if not value and local.is_file():
        value = str(local)
    if not value:
        raise SystemExit(f'{name} not found; supply --{name} with the executable path')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--top', default='camera_ethernet_core')
    args = parser.parse_args()
    files = sources()
    for path in files:
        if not path.is_file():
            raise SystemExit(f'Missing source: {path}')
    if args.list:
        print('\n'.join(map(str, files)))
        return
    output = ROOT / '.local/rtl/core.vvp'
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([tool('iverilog', args.iverilog), '-g2012', '-Wall', '-s', args.top,
                    '-o', str(output), *map(str, files)], check=True)
    print('PASS: integration core elaborated. No board bitstream or hardware operation.')


if __name__ == '__main__':
    main()
