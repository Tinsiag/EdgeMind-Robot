"""Archive successful local checks and source identities, without hardware IO."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]


def main():
    tests = json.loads((ROOT / '.local/tests/results.json').read_text(encoding='utf-8'))
    synthesis = json.loads((ROOT / '.local/synthesis/result.json').read_text(encoding='utf-8'))
    for relative, expected in tests['input_sha256'].items():
        path = ROOT.parent / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('RTL/test changed since successful regression: ' + relative)
    for absolute, expected in synthesis['source_sha256'].items():
        if hashlib.sha256(Path(absolute).read_bytes()).hexdigest() != expected:
            raise RuntimeError('RTL changed since synthesis: ' + absolute)
    if synthesis['returncode'] or synthesis['sources_changed_during_run']:
        raise RuntimeError('Synthesis did not complete on a stable snapshot')
    out = ROOT / 'verification' / '2026-10-18'
    out.mkdir(parents=True, exist_ok=True)
    python_results = []
    for name, folder in [('host', REPO / 'code/fpga/acg720-motion-control/tests'),
                         ('build-guard', ROOT / 'tests'),
                         ('pinmap', REPO / 'code/fpga/tests')]:
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m', 'unittest',
                                 'discover', '-s', str(folder), '-p', 'test_*.py', '-v'],
                                capture_output=True, text=True, encoding='utf-8', timeout=60)
        log = result.stdout + result.stderr
        (out / (name + '.log')).write_text(log, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(name + ' regression failed')
        python_results.append(name)
    shutil.copy2(ROOT / '.local/tests/results.json', out / 'rtl-results.json')
    for test in tests['rtl_cases']:
        shutil.copy2(ROOT / '.local/tests' / (test + '.log'), out / (test + '.log'))
    shutil.copy2(ROOT / '.local/synthesis/result.json', out / 'synthesis-result.json')
    shutil.copy2(ROOT / '.local/synthesis/synthesis.log', out / 'synthesis.log')
    shutil.copy2(ROOT / '.local/synthesis/impl/gwsynthesis/portable_syn.rpt.html', out / 'portable_syn.rpt.html')
    shutil.copy2(ROOT / '.local/legacy-tests/results.json', out / 'legacy-rtl-results.json')
    for path in (ROOT / '.local/legacy-tests').glob('*.log'):
        shutil.copy2(path, out / ('legacy-' + path.name))
    blocked = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/build.py'), 'check'],
                             capture_output=True, text=True, encoding='utf-8', timeout=30)
    if blocked.returncode != 2:
        raise RuntimeError('Expected missing-platform guard to fail closed')
    (out / 'build-blocked.log').write_text(blocked.stdout + blocked.stderr, encoding='utf-8')
    record = {'timestamp': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'rtl_cases': len(tests['rtl_cases']), 'python_suites_passed': python_results,
              'synthesis_passed': True, 'pnr_run': False, 'bitstream_generated': False,
              'hardware_tested': False, 'timing_signed_off': False,
              'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(out.iterdir()) if p.is_file() and p.name != 'manifest.json'}}
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
