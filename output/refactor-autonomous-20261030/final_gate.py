"""Seal executed checks before programming. This script never touches the board."""
import ast
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PROJECT = ROOT / 'code/camera-car-control/a745-autonomous'
BUILD = PROJECT / '.local/gowin-a745-autonomous'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((BUILD / 'result.json').read_text())
    assert result['compile_passed'] and result['run_state'] == 'completed'
    assert not result['sources_changed'] and all(v == 0 for v in result['timing_violations'].values())
    sys.path.insert(0, str(PROJECT / 'scripts'))
    from prepare import prepare
    files, platform = prepare()
    for name, expected in result['source_sha256'].items():
        assert sha(Path(name)) == expected, name
    assert set(map(str, files)) <= set(result['source_sha256'])
    tests = json.loads((PROJECT / '.local/tests/result.json').read_text())
    assert len(tests['passed']) == 23
    for name, expected in tests['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    protocol = json.loads((PROJECT / '.local/tests/protocol-result.json').read_text())
    assert protocol['passed']
    for name, expected in protocol['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    cpu_gate = json.loads((PROJECT / '.local/tests/cpu-gate-result.json').read_text())
    assert cpu_gate['passed'] and cpu_gate['synchronous_register_file_ram_count'] == 0
    for name, expected in cpu_gate['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    geometry = json.loads((PROJECT / '.local/tests/turn-geometry-result.json').read_text())
    assert geometry['passed']
    for name, expected in geometry['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    navigation = json.loads((PROJECT / '.local/tests/navigation-gate-result.json').read_text())
    assert navigation['passed'] and navigation['main_netlist_sha256'] == result['synthesis_netlist_sha256']
    for name, expected in navigation['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    assert 'SDPB cpuregs_cpuregs' not in (BUILD / 'impl/gwsynthesis/a745.vg').read_text()
    timing = json.loads((OUT / 'TIMING-REVIEW.json').read_text())
    assert timing['numeric_checks_pass'] and not timing['inactive_constraints']
    for name in ['TFT-PAD-TIMING.json', 'TX-SKEW-REVIEW.json', 'CAMERA-INPUT-REVIEW.json']:
        review = json.loads((OUT / name).read_text())
        assert review['passed'] and review['bitstream_sha256'] == result['artifact_sha256']
    assert json.loads((OUT / 'CONSTRAINT-TARGETS.json').read_text())['routed_netlist_used']
    ports = (platform / 'a745_top.v').read_text()
    assert not any(name in ports for name in ['rgmii_rxd', 'rgmii_rx_ctl', 'rgmii_rx_clk', 'command_parser', 'network_mode'])
    for host in ['receiver.py', 'app.py']:
        tree = ast.parse((PROJECT / 'host' / host).read_text(encoding='utf-8'))
        assert not any(isinstance(n, ast.Attribute) and n.attr in ['send', 'sendto', 'sendall'] for n in ast.walk(tree))
    artifact = Path(result['artifact'])
    assert sha(artifact) == result['artifact_sha256']
    assert artifact.stat().st_mtime >= result['evidence_freshness_lower_bound_unix']
    revision = int(re.search(r"snapshot\[159:128\]<=32'd(\d+)", (PROJECT/'rtl/a745_core.v').read_text())[1])
    record = {'status': 'review_passed_pending_programming', 'timing_signed_off': True, 'firmware_revision': revision,
              'artifact': str(artifact), 'artifact_sha256': result['artifact_sha256'], 'usercode': '0xA745',
              'hardware_programmed': False, 'hardware_display_verified': False, 'cold_boot_verified': False,
              'armed': False, 'rtl_tests_passed': 23, 'protocol_checks_passed': True,
              'network_control_enabled': False, 'vm_off_confirmed': True,
              'motor_pads_dynamic': True, 'common_ground_must_remain_connected': True,
              'turn_geometry_verified': True, 'navigation_gate_checks_passed': True, 'front_stop_mm': 500,
              'recorded_utc': datetime.now(timezone.utc).isoformat()}
    (OUT / 'STATUS.json').write_text(json.dumps(record, indent=2) + '\n')
    result.update(timing_signed_off=True, review_record=str(OUT / 'STATUS.json'))
    (BUILD / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    shutil.copy2(BUILD / 'result.json', OUT / 'build-evidence-current/result.json')
    for name in ['result.json', 'protocol-result.json', 'cpu-gate-result.json', 'turn-geometry-result.json', 'navigation-gate-result.json']:
        shutil.copy2(PROJECT / '.local/tests' / name, OUT / ('tests-' + name))
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
