"""Portable, bounded RTL regressions; no serial port or programmer access."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT.parent / 'acg720-motion-control' / 'rtl'
NAMES = ('quadrature_decoder', 'encoder_counter', 'wheel_speed_estimator',
         'wheel_pi_controller', 'differential_drive', 'rotate_controller', 'uart_rx', 'uart_tx')


def sources():
    return sorted((ROOT / 'rtl').glob('*.v')) + [SHARED / (n + '.v') for n in NAMES]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iverilog', default=os.environ.get('IVERILOG', 'iverilog'))
    parser.add_argument('--vvp', default=os.environ.get('VVP', 'vvp'))
    parser.add_argument('--only', help='run one testbench/top by name')
    args = parser.parse_args()
    compiler = shutil.which(args.iverilog) or args.iverilog
    runner = shutil.which(args.vvp) or args.vvp
    output = ROOT / '.local' / 'tests'
    output.mkdir(parents=True, exist_ok=True)
    results = []
    input_files = sources() + sorted((ROOT / 'tests').glob('*_tb.v'))
    before = {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in input_files}
    cases = [(p.stem, p) for p in sorted((ROOT / 'tests').glob('*_tb.v'))]
    cases.insert(0, ('vision_motion_top', None))
    if args.only:
        cases = [(top, tb) for top, tb in cases if top == args.only]
        if not cases:
            parser.error('unknown test: ' + args.only)
    for top, tb in cases:
        binary = output / (top + '.vvp')
        command = [str(compiler), '-g2012', '-Wall', '-s', top, '-o', str(binary)]
        command += [str(p) for p in sources()]
        if tb:
            command.append(str(tb))
        if top == 'full_resolution_tb':
            command.append(str(ROOT / 'tests' / 'camera_ddr_pipeline_tb.v'))
        built = subprocess.run(command, capture_output=True, text=True, timeout=60)
        log = built.stdout + built.stderr
        if built.returncode:
            (output / (top + '.log')).write_text(log, encoding='utf-8')
            print(log)
            return 1
        if tb:
            run = subprocess.run([str(runner), str(binary)], capture_output=True, text=True,
                                 timeout=600 if top == 'full_resolution_tb' else 120)
            log += run.stdout + run.stderr
            if run.returncode or 'PASS' not in run.stdout or 'FAIL' in log or 'ERROR:' in log:
                (output / (top + '.log')).write_text(log, encoding='utf-8')
                print(log)
                return 1
        (output / (top + '.log')).write_text(log, encoding='utf-8')
        results.append(top)
        print('PASS', top, flush=True)
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != before[str(p.relative_to(ROOT.parent))]
           for p in input_files):
        raise RuntimeError('Sources changed during tests; rerun on a stable snapshot')
    record = {'rtl_cases': results, 'hardware_tested': False, 'timing_signed_off': False,
              'timestamp': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'compiler': str(Path(compiler).resolve()),
              'input_sha256': before}
    result_name = 'results.json' if not args.only else args.only + '-results.json'
    (output / result_name).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
