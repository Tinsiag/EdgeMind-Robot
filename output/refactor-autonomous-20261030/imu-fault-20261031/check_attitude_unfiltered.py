"""Prove the isolated-shock regression fails with the previous direct-publish path.

This is a synthetic fault injection, not replay of unavailable fault-time raw IMU.
Only a generated fixture is changed; project RTL and board hardware are untouched.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'code/camera-car-control/a745-autonomous'
sys.path.insert(0, str(PROJECT / 'scripts'))
from check import linux, sources


def main():
    source = PROJECT / 'lib/a741_attitude.v'
    bench = PROJECT / 'tests/attitude_session_tb.v'
    out = PROJECT / '.local/attitude-unfiltered-regression'
    out.mkdir(exist_ok=True)
    # Restore only the previous direct publication behavior in the fixture.
    text = source.read_text()
    text, count = re.subn(r'(?s)      if\(history_count==0\) begin.*?      roll_old<=roll_prev;',
                          '      roll<=roll_q;pitch<=nz[15:0];\n      roll_old<=roll_prev;', text)
    assert count == 1
    fixture = out / 'unfiltered.v'
    fixture.write_text(text)
    product = out / 'test.vvp'
    prefix = ['wsl.exe', '-d', 'Ubuntu-26.04', '--cd', linux(PROJECT), '--exec']
    inputs = [p for p in sources() if p != source] + [fixture, bench]
    compiled = subprocess.run(prefix + ['iverilog', '-g2012', '-s', 'attitude_session_tb',
                                         '-o', linux(product), *map(linux, inputs)],
                              capture_output=True, text=True, errors='replace', timeout=60)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    run = subprocess.run(prefix + ['vvp', linux(product)], capture_output=True,
                         text=True, errors='replace', timeout=60)
    expected = 'single-sample attitude spike caused a stop'
    assert run.returncode != 0 and expected in run.stdout, run.stdout + run.stderr
    (out / 'expected-failure.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    receipt = dict(passed=True, synthetic_injection=True, physical_raw_replay=False,
                   unfiltered_path_reproduces_false_fault=True,
                   expected_failure=expected, returncode=run.returncode,
                   packets_sent=0, hardware_touched=False,
                   input_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in inputs + [source, Path(__file__).resolve()]})
    target = Path(__file__).with_name('74508-unfiltered-regression.json')
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS unfiltered path reproduces ERR0001 on synthetic isolated acceleration; filtered path checked separately')


if __name__ == '__main__':
    main()
