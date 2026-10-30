"""Check the routed DVP bundle, real input-delay cells and zero STA violations."""
import hashlib
import json
import re
from pathlib import Path
from audit_tx_sdf import clean, edge_values

OUT = Path(__file__).resolve().parent
BUILD = OUT.parents[1] / 'code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous'
PNR = BUILD / 'impl/pnr'


def main():
    result = json.loads((BUILD / 'result.json').read_text())
    assert result['compile_passed'] and result['run_state'] == 'completed'
    assert all(v == 0 for v in result['timing_violations'].values())
    vo, sdf = [(PNR / ('a745.' + suffix)).read_text() for suffix in ['vo', 'sdf']]
    assert min((PNR / ('a745.' + s)).stat().st_mtime for s in ['vo', 'sdf', 'tr']) >= result['evidence_freshness_lower_bound_unix']
    logic = {clean(n): (k, {p: clean(v) for p, v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)', body, re.S)})
             for k, n, body in re.findall(r'(?m)^\s*(\w+)\s+(\\?[^\s(]+)\s*\((.*?)\);', vo, re.S)}
    cells = {}
    for block in re.split(r'(?m)^  \(CELL\s*$', sdf)[1:]:
        cells[clean(re.search(r'\(INSTANCE\s*([^)]*)\)', block)[1])] = block
    records = []
    for i in range(10):
        name = f'camera_pads/pads[{i}].delay'
        kind, pins = logic[name]
        assert kind == 'IODELAY'
        port = f'camera_data[{i}]' if i < 8 else 'camera_href' if i == 8 else 'camera_vsync'
        source = [(n, p) for n, (k, p) in logic.items() if k == 'IBUF' and p.get('I') == port]
        assert len(source) == 1 and source[0][1]['O'] == pins['DI'], (port, source)
        destination = [(n, p) for n, (k, p) in logic.items() if k.startswith('DFF') and p.get('D') == pins['DO']]
        assert len(destination) == 1 and destination[0][0].startswith('video/capture/'), destination
        taps = re.findall(r'defparam\s+\\?' + re.escape(name) + r'\s*\.C_STATIC_DLY\s*=\s*(\d+)', vo)
        assert taps == ['96'], (name, taps)
        arc = re.findall(r'\(IOPATH\s+DI\s+DO\s+((?:\([^()]*\)\s*)+)\)', cells[name])
        assert len(arc) == 1
        delay = edge_values(arc[0])
        assert min(v for edge in delay for v in edge) > .821  # rejected -0.621ns + 0.2ns reserve
        records.append({'port': port, 'input_buffer': source[0][0], 'delay_cell': name,
                        'taps': 96, 'capture_ff': destination[0][0], 'sdf_delay_ns': delay})
    sdc = (Path(result['platform_directory']) / 'a745.sdc').read_text()
    assert 'set_input_delay -clock camera_pclk -max 4.000' in sdc
    assert 'set_input_delay -clock camera_pclk -min 0.000' in sdc
    record = {'passed': True, 'input_setup_budget_ns': 4, 'input_hold_budget_ns': 0,
              'bitstream_sha256': result['artifact_sha256'], 'camera_pclk_constraint_mhz': 100,
              'sdf_sha256': hashlib.sha256((PNR / 'a745.sdf').read_bytes()).hexdigest(),
              'method': 'ten pad-to-delay-to-capture-FF paths; STA validates all paths at original budgets',
              'board_signals_measured': False, 'inputs': records}
    (OUT / 'CAMERA-INPUT-REVIEW.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
