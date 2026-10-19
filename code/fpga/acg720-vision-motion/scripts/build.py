"""Fail-closed board build. Does not download to FPGA or write configuration Flash."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT.parent / 'acg720-motion-control' / 'rtl'
PART = 'GW5AT-LV60PG484AC1/I0'
ROLES = {'ddr3_phy', 'clock_pll', 'tmds', 'camera_init', 'board_wrapper'}
EXPECTED = {'clk': 'Y18', 'stop_n': 'F15', 'uart_rx': 'J21', 'uart_tx': 'M15',
            'left_in1': 'A18', 'left_in2': 'A19', 'left_enc_a': 'A15', 'left_enc_b': 'A16',
            'right_in1': 'F13', 'right_in2': 'F14', 'right_enc_a': 'E13', 'right_enc_b': 'E14',
            'camera_reset_n': 'C14', 'camera_sclk': 'B13', 'camera_sdat': 'D15',
            'camera_pclk': 'B18', 'camera_href': 'D14', 'camera_vsync': 'C13'}
EXPECTED.update({f'camera_data[{i}]': b for i, b in enumerate(['C15', 'B15', 'B16', 'D17', 'C17', 'E16', 'D16', 'B17'])})
EXPECTED.update({f'led[{i}]': b for i, b in enumerate(['M22', 'N22', 'L21', 'K21', 'K22', 'J22', 'H22', 'M21'])})
SHARED_NAMES = ('quadrature_decoder', 'encoder_counter', 'wheel_speed_estimator',
                'wheel_pi_controller', 'differential_drive', 'rotate_controller', 'uart_rx', 'uart_tx')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(path):
    """All physical facts come from reviewed board support, never invented defaults."""
    if not path.is_file():
        raise ValueError('Missing board support manifest: ' + str(path) +
                         '\nRestore DDR3/PLL/TMDS/camera initialization and verified ToF pin mapping; see platform.example.json.')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('device') != 'GW5AT-60B' or data.get('part') != PART:
        raise ValueError('Board support must target GW5AT-60B / ' + PART)
    if data.get('top_module') != 'acg720_vision_motion_board':
        raise ValueError('Expected board top acg720_vision_motion_board')
    if data.get('io_reviewed') is not True:
        raise ValueError('Physical IO/bank voltage review is missing')
    files = []
    roles = set()
    for item in data.get('files', []):
        candidate = (path.parent / item['path']).resolve()
        if not candidate.is_file():
            raise ValueError('Missing dependency: ' + str(candidate))
        if not re.fullmatch('[0-9a-fA-F]{64}', item.get('sha256', '')) or digest(candidate) != item['sha256'].lower():
            raise ValueError('Missing/mismatched dependency hash: ' + str(candidate))
        roles.add(item.get('role'))
        files.append((candidate, item.get('type', 'file.verilog'), item.get('role')))
    if not ROLES <= roles:
        raise ValueError('Missing platform roles: ' + ', '.join(sorted(ROLES - roles)))
    constraints = [p for p, t, _ in files if t == 'file.cst']
    timing_files = [p for p, t, _ in files if t == 'file.sdc']
    if len(constraints) != 1 or not timing_files:
        raise ValueError('Require exactly one reviewed board CST and at least one SDC')
    cst = constraints[0].read_text(encoding='utf-8-sig')
    # Ignore comments before scanning; actual routed ports are audited after P&R.
    cst = re.sub(r'//[^\n]*', '', cst)
    matches = re.findall(r'IO_LOC\s+"([^"]+)"\s+(\w+)\s*;', cst)
    pins = dict(matches)
    if len(pins) != len(matches) or len(set(pins.values())) != len(pins):
        raise ValueError('Duplicate IO port or package ball')
    for port, ball in EXPECTED.items():
        if pins.get(port) != ball:
            raise ValueError(f'Wrong/missing established pin: {port} -> {ball}')
    tof_pins = data.get('tof_pins', {})
    for port in ('tof_sda', 'tof_scl', 'tof_xshut'):
        ball = tof_pins.get(port)
        if not ball or pins.get(port) != ball:
            raise ValueError('Unconfirmed ToF pin: ' + port)
    evidence = data.get('io_review_evidence', {})
    evidence_path = (path.parent / evidence.get('path', '__missing__')).resolve()
    if not evidence_path.is_file() or digest(evidence_path) != evidence.get('sha256', '').lower():
        raise ValueError('Missing/changed IO review evidence')
    wrapper = [p for p, _, role in files if role == 'board_wrapper']
    if len(wrapper) != 1 or 'vision_motion_top' not in wrapper[0].read_text(encoding='utf-8-sig'):
        raise ValueError('Board wrapper must instantiate vision_motion_top')
    return data, files, pins


def prepare(manifest):
    data, vendor_files, pins = verify_manifest(manifest)
    out = ROOT / '.local' / 'build'
    out.mkdir(parents=True, exist_ok=True)
    sources = [(p, 'file.verilog', 'portable') for p in sorted((ROOT / 'rtl').glob('*.v'))]
    sources += [(SHARED / (n + '.v'), 'file.verilog', 'motion') for n in SHARED_NAMES]
    sources += vendor_files
    project = ET.Element('Project')
    ET.SubElement(project, 'Template').text = 'FPGA'
    ET.SubElement(project, 'Version').text = '5'
    ET.SubElement(project, 'Device', {'name': 'GW5AT-60B', 'pn': PART}).text = 'gw5at60b-002'
    filelist = ET.SubElement(project, 'FileList')
    for p, t, _ in sources:
        ET.SubElement(filelist, 'File', {'path': p.as_posix(), 'type': t, 'enable': '1'})
    project_path = out / 'acg720_vision_motion.gprj'
    ET.ElementTree(project).write(project_path, encoding='utf-8', xml_declaration=True)
    tcl = '\n'.join(['cd [file dirname [file normalize [info script]]]',
                     'open_project acg720_vision_motion.gprj',
                     'set_option -top_module acg720_vision_motion_board',
                     'set_option -output_base_name acg720_vision_motion',
                     'set_option -use_sspi_as_gpio 1',
                     'set_option -bit_security 0',
                     'set_option -user_code 0000A730', 'run all', ''])
    (out / 'build.tcl').write_text(tcl, encoding='utf-8')
    record = {'manifest_sha256': digest(manifest), 'pins': pins,
              'source_sha256': {p.as_posix(): digest(p) for p, _, _ in sources},
              'timing_signed_off': False, 'hardware_tested': False}
    (out / 'build-inputs.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return out


def audit(out):
    reports = list((out / 'impl' / 'pnr').glob('*tr_content.html'))
    if len(reports) != 1:
        raise ValueError('Missing or ambiguous routed timing report')
    text = reports[0].read_text(encoding='utf-8', errors='replace')
    counts = {}
    for check in ('Setup', 'Hold', 'Recovery'):
        found = re.search(rf'Numbers of {check} Violated Endpoints</td>\s*<td>(\d+)</td>', text, re.I)
        if not found:
            raise ValueError('Missing timing check: ' + check + '; manual review required')
        counts[check] = int(found[1])
        if counts[check]:
            raise ValueError(f'{check} has {counts[check]} violated endpoints')
    bitstream = out / 'impl' / 'pnr' / 'acg720_vision_motion.fs'
    header = bitstream.read_bytes()[:4096].decode('ascii', errors='ignore')
    if PART not in header or '0x0000a730' not in header.lower():
        raise ValueError('Bitstream part/User Code mismatch')
    # Timing summaries alone are not a routed-pin/CDC signoff.
    result = {'timing_summary_violations': counts, 'bitstream_sha256': digest(bitstream),
              'timing_signed_off': False, 'hardware_tested': False,
              'remaining_review': ['routed pinout versus build-inputs.json', 'CDC exceptions and reset recovery detail']}
    (out / 'build-audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'prepare', 'build', 'audit'))
    parser.add_argument('--manifest', type=Path, default=ROOT / '.local' / 'platform' / 'manifest.json')
    parser.add_argument('--gowin', default=os.environ.get('GOWIN_GW_SH', 'gw_sh'))
    args = parser.parse_args()
    try:
        if args.action == 'check':
            verify_manifest(args.manifest)
            print('Platform dependencies and declared pin mapping verified; no hardware action.')
        elif args.action == 'audit':
            audit(ROOT / '.local' / 'build')
        else:
            out = prepare(args.manifest)
            if args.action == 'build':
                result = subprocess.run([args.gowin, str(out / 'build.tcl')], cwd=out)
                if result.returncode:
                    return result.returncode
                audit(out)
            else:
                print(out)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print('BUILD BLOCKED: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
