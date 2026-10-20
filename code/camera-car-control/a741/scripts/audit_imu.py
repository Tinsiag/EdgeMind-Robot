"""Audit the compiled IMU test variant without connecting to hardware."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re

from check import ROOT


class PinRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag == 'td' and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = ROOT / '.local/gowin-imu-test'
    result = json.loads((build / 'result.json').read_text(encoding='utf-8'))
    if not result['compile_passed'] or result['sources_changed'] or not result['motor_locked'] or not result['imu_enabled']:
        raise RuntimeError('No completed, unchanged, motor-locked IMU build')
    for name, expected in result['source_sha256'].items():
        if sha(Path(name)) != expected:
            raise RuntimeError('Compiler input changed: '+name)
    if sha(Path(result['artifact'])) != result['artifact_sha256']:
        raise RuntimeError('Bitstream changed')
    netlist = build / 'impl/gwsynthesis/a741.vg'
    if sha(netlist) != result['synthesis_netlist_sha256']:
        raise RuntimeError('Synthesis netlist changed')
    text = netlist.read_text(encoding='utf-8')
    motors = ('left_in1', 'left_in2', 'right_in1', 'right_in2')
    for name in motors:
        pattern = r'OBUF '+name+r'_obuf\s*\(\s*\.O\('+name+r'\),\s*\.I\(GND\)\s*\);'
        if not re.search(pattern, text):
            raise RuntimeError('Motor pin not tied to GND: '+name)
    for name in ('imu_scl', 'imu_sda'):
        pattern = r'IOBUF '+name+r'_iobuf\s*\(\s*\.O\([^)]*\),\s*\.IO\('+name+r'\),\s*\.I\(GND\),\s*\.OEN\([^)]*\)\s*\);'
        if not re.search(pattern, text):
            raise RuntimeError('I2C output is not open drain: '+name)
    pin_file = build / 'impl/pnr/a741.pin.html'
    table = PinRows()
    table.feed(pin_file.read_text(encoding='utf-8'))
    expected = {'imu_scl': ('L18', '5', 'io'), 'imu_sda': ('M20', '5', 'io'),
                'imu_ad0': ('M17', '5', 'in'), 'imu_xda': ('A1', '11', 'in'),
                'imu_xcl': ('B2', '11', 'in'), 'imu_int': ('B1', '11', 'in')}
    checked = {}
    for name, (ball, bank, direction) in expected.items():
        rows = [row for row in table.rows if len(row)>17 and row[0]==name]
        if len(rows)!=1:
            raise RuntimeError('Missing or duplicate physical pin report: '+name)
        row = rows[0]
        if row[2] != ball+'/'+bank or row[4] != direction or row[7] != 'LVCMOS33' or row[9] != 'NONE' or row[17] != '3.3':
            raise RuntimeError('Unexpected physical pin configuration: '+str(row))
        checked[name] = {'ball': ball, 'bank': int(bank), 'direction': direction,
                         'io_standard': row[7], 'pull_mode': row[9], 'configured_vccio': 3.3}
    record = {'variant': result['variant'], 'bitstream_sha256': result['artifact_sha256'],
              'netlist_sha256': sha(netlist), 'pin_report_sha256': sha(pin_file),
              'motor_outputs_constant_zero': list(motors), 'i2c_open_drain_verified': True,
              'physical_assignments': checked, 'hardware_tested': False,
              'bank_voltages_measured': False, 'timing_signed_off': False}
    path = ROOT / 'verification/imu-test-output-audit.json'
    path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print('PASS compiled motor lock, open-drain buffers, six physical pin/direction assignments and bitstream hash')


if __name__ == '__main__':
    main()
