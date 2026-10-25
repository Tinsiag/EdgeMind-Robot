"""Run a synthetic moving-room diagnostic without touching the live build."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, time

IS_WINDOWS_HOST = shutil.which("wsl.exe") is not None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = REPO / 'code/camera-car-control/a741-fpga-fusion'
sys.path.insert(0, str(ROOT / 'scripts'))
from check import sources

def linux(path):
    path = Path(path).resolve().as_posix()
    if not IS_WINDOWS_HOST:
        return path
    return '/mnt/' + path[0].lower() + path[2:]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--override', type=Path)
    parser.add_argument('--bench', type=Path, default=HERE / 'continuous_navigation_tb.v')
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    paths = sources()
    if args.override:
        replacement = args.override.resolve()
        if sum(p.name == replacement.name for p in paths) != 1:
            raise RuntimeError('Override must replace exactly one existing RTL source')
        paths = [replacement if p.name == replacement.name else p for p in paths]
    bench = args.bench.resolve()
    paths += [bench]
    top = bench.stem
    before = {str(p): sha(p) for p in paths + [Path(__file__)]}
    obj = '/var/tmp/edgemind-continuous-' + hashlib.sha256(str(out).encode()).hexdigest()[:12]
    prefix = (
        ['wsl.exe', '-d', 'Ubuntu-26.04', '--cd', linux(ROOT), '--exec']
        if IS_WINDOWS_HOST else []
    )
    started = time.time()
    with (out / 'compile.log').open('w', encoding='utf-8') as log:
        rc = subprocess.run(prefix + ['verilator', '--binary', '--timing', '-j', '4', '-Wno-fatal', '--Mdir', obj,
            '--top-module', top, *map(linux, paths)], stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode
    if rc == 0:
        with (out / 'run.log').open('w', encoding='utf-8') as log:
            rc = subprocess.run(prefix + [obj + '/V'+top], stdout=log,
                stderr=subprocess.STDOUT, timeout=300).returncode
    changed = [p for p, h in before.items() if sha(p) != h]
    log_path = out / ('run.log' if (out / 'run.log').is_file() else 'compile.log')
    run_log = log_path.read_text(encoding='utf-8', errors='replace')
    record = {'returncode': rc, 'seconds': time.time()-started, 'input_sha256': before, 'inputs_changed': changed,
        'passed': rc == 0 and not changed and 'PASS' in run_log, 'synthetic_ideal_plant': True, 'hardware_tested': False}
    (out / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({k: record[k] for k in ('passed', 'returncode', 'seconds', 'inputs_changed')}, indent=2))
    print(run_log[-3500:])
    raise SystemExit(0 if record['passed'] else 1)

if __name__ == '__main__':
    main()
