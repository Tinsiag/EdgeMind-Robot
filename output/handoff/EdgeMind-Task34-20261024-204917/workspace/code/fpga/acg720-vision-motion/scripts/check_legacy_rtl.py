"""Run existing motion RTL tests without changing the baseline engineering files."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MOTION = ROOT.parent / 'acg720-motion-control'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', required=True)
    parser.add_argument('--vvp', required=True)
    args = parser.parse_args()
    out = ROOT / '.local' / 'legacy-tests'
    out.mkdir(parents=True, exist_ok=True)
    sources = sorted((MOTION / 'rtl').glob('*.v'))
    passed = []
    for test in sorted((MOTION / 'tests').glob('*_tb.v')):
        binary = out / (test.stem + '.vvp')
        compile_command = [args.iverilog, '-g2012', '-s', test.stem, '-o', str(binary)]
        compile_command += [str(p) for p in sources] + [str(test)]
        built = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
        log = built.stdout + built.stderr
        if built.returncode == 0:
            run = subprocess.run([args.vvp, str(binary)], capture_output=True, text=True, timeout=120)
            log += run.stdout + run.stderr
            good = run.returncode == 0 and 'PASS' in run.stdout and 'FAIL' not in log and 'ERROR:' not in log
        else:
            good = False
        (out / (test.stem + '.log')).write_text(log, encoding='utf-8')
        if not good:
            print(log)
            return 1
        passed.append(test.stem)
        print('PASS', test.stem, flush=True)
    (out / 'results.json').write_text(json.dumps({'legacy_cases': passed}, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
