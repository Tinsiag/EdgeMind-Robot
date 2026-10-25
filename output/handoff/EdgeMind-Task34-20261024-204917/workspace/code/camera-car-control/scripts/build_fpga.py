"""Compile the core or a supplied ACG720 board platform with Gowin."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from check_fpga import ROOT, sources

PART = 'GW5AT-LV60PG484AC1/I0'
ROLES = {'board_top', 'camera_init', 'rgmii_phy', 'clocking', 'pins', 'timing'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def platform_files(path):
    if not path.is_file():
        raise ValueError('Missing board platform manifest: ' + str(path) +
                         '; need board_top, camera_init, rgmii_phy, clocking, CST and SDC')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('part') != PART or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', data.get('top', '')):
        raise ValueError('Platform must name the GW5AT-60B part and a real physical top module')
    roles = set()
    files = []
    for entry in data['files']:
        source = (path.parent / entry['path']).resolve()
        if not source.is_file() or digest(source).lower() != entry['sha256'].lower():
            raise ValueError('Missing or changed platform file: ' + str(source))
        roles.update(entry.get('roles', []))
        files.append((source, entry['type']))
    if ROLES - roles:
        raise ValueError('Missing platform roles: ' + ', '.join(sorted(ROLES - roles)))
    if sum(kind == 'file.cst' for _, kind in files) != 1 or not any(kind == 'file.sdc' for _, kind in files):
        raise ValueError('Board build requires exactly one complete CST and at least one SDC')
    return data['top'], files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('synth', 'build', 'check'))
    parser.add_argument('--gowin', default='C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--platform', type=lambda p: Path(p).resolve(),
                        default=ROOT / '.local/platform/manifest.json')
    args = parser.parse_args()
    core = sources()
    files = [(path, 'file.verilog') for path in core]
    top = 'camera_ethernet_core'
    if args.mode in ('build', 'check'):
        try:
            top, extra = platform_files(args.platform)
        except (ValueError, KeyError, OSError) as exc:
            print('BLOCKED: ' + str(exc), file=sys.stderr)
            return 2
        files += extra
        if args.mode == 'check':
            print('PASS: complete platform file list and hashes')
            return 0
    if any(not path.is_file() for path, _ in files):
        raise ValueError('One or more core sources are missing')
    output = ROOT / '.local' / ('gowin-core' if args.mode == 'synth' else 'gowin-board')
    output.mkdir(parents=True, exist_ok=True)
    hashes = {str(p): digest(p) for p, _ in files}
    project = ET.Element('Project')
    ET.SubElement(project, 'Template').text = 'FPGA'
    ET.SubElement(project, 'Version').text = '5'
    ET.SubElement(project, 'Device', name='GW5AT-60B', pn=PART).text = 'gw5at60b-002'
    listing = ET.SubElement(project, 'FileList')
    for path, kind in files:
        ET.SubElement(listing, 'File', path=path.as_posix(), type=kind, enable='1')
    ET.ElementTree(project).write(output / 'camera_car.gprj', encoding='utf-8', xml_declaration=True)
    tcl = ['cd [file dirname [file normalize [info script]]]', 'open_project camera_car.gprj',
           'set_option -top_module ' + top, 'set_option -output_base_name camera_car',
           'set_option -verilog_std sysv2017']
    if args.mode == 'build':
        tcl += ['set_option -use_sspi_as_gpio 1', 'set_option -use_cpu_as_gpio 1', 'set_option -user_code 0000A740',
                'set_option -bit_security 0']
    tcl += ['run syn' if args.mode == 'synth' else 'run all', '']
    script = output / 'build.tcl'
    script.write_text('\n'.join(tcl), encoding='utf-8')
    log_path = output / 'build.log'
    timed_out = False
    with log_path.open('w', encoding='utf-8') as log:
        try:
            result = subprocess.run([args.gowin, str(script)], cwd=output, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=args.timeout)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = -1
    changed = any(digest(p) != hashes[str(p)] for p, _ in files)
    netlist = output / 'impl/gwsynthesis/camera_car.vg'
    bitstream = output / 'impl/pnr/camera_car.fs'
    log_text = log_path.read_text(encoding='utf-8', errors='replace')
    failed = returncode != 0 or changed or any(line.lstrip().startswith(('ERROR', 'FATAL'))
                                                     for line in log_text.splitlines())
    record = {'mode': args.mode, 'top': top, 'part': PART, 'compiler_returncode': returncode, 'timed_out': timed_out,
              'compile_passed': not failed and (netlist.is_file() if args.mode == 'synth' else bitstream.is_file()),
              'sources_changed': changed, 'pnr_run': args.mode == 'build',
              'bitstream_generated': args.mode == 'build' and not failed and bitstream.is_file(),
              'hardware_programmed': False, 'timing_signed_off': False, 'source_sha256': hashes}
    timing = output / 'impl/pnr/camera_car.tr'
    if args.mode == 'build' and not failed and timing.is_file():
        timing_text = timing.read_text(encoding='utf-8', errors='replace')
        record['timing_violated_endpoints'] = {
            name.lower(): int(value) for name, value in re.findall(
                r'<Numbers of (Setup|Hold) Violated Endpoints>:(\d+)', timing_text)}
    if record['compile_passed']:
        artifact = netlist if args.mode == 'synth' else bitstream
        record['artifact'] = str(artifact)
        record['artifact_sha256'] = digest(artifact)
    (output / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(('PASS' if record['compile_passed'] else 'FAIL') + ': ' + args.mode)
    print('Log: ' + str(log_path))
    return 0 if record['compile_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
