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
    assert result['timing_signed_off'] and not result['path_slack_violations']
    sys.path.insert(0, str(PROJECT / 'scripts'))
    from prepare import prepare
    files, platform = prepare()
    for name, expected in result['source_sha256'].items():
        assert sha(Path(name)) == expected, name
    assert set(map(str, files)) <= set(result['source_sha256'])
    tests = json.loads((PROJECT / '.local/tests/result.json').read_text())
    expected_benches = {p.stem for p in (PROJECT / 'tests').glob('*_tb.v')}
    assert set(tests['passed']) == expected_benches and len(tests['passed']) == len(expected_benches)
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
    revision = int(re.search(r"snapshot\[159:128\]<=32'd(\d+)", (PROJECT/'rtl/a745_core.v').read_text())[1])
    reverse_geometry = json.loads((OUT / f'reverse-clearance-{revision}.json').read_text())
    assert reverse_geometry['generated_by'] == str(OUT / 'check_reverse_clearance.py')
    assert reverse_geometry['passed'] and reverse_geometry['rear_stop_mm'] > reverse_geometry['inflated_rear_corner_radius_mm']
    for name, expected in reverse_geometry['inputs_sha256'].items():
        assert sha(Path(name)) == expected, name
    navigation = json.loads((PROJECT / '.local/tests/navigation-gate-result.json').read_text())
    assert navigation['passed'] and navigation['main_netlist_sha256'] == result['synthesis_netlist_sha256']
    for name, expected in navigation['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    replay = json.loads((PROJECT / '.local/tests/lidar-replay-result.json').read_text())
    assert replay['passed'] and replay['metrics']['filtered_clear'] >= 100
    for name, expected in replay['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    assert 'SDPB cpuregs_cpuregs' not in (BUILD / 'impl/gwsynthesis/a745.vg').read_text()
    timing = json.loads((OUT / 'TIMING-REVIEW.json').read_text())
    assert timing['numeric_checks_pass'] and not timing['inactive_constraints']
    for name in ['TFT-PAD-TIMING.json', 'TX-SKEW-REVIEW.json', 'CAMERA-INPUT-REVIEW.json', 'RX-INPUT-REVIEW.json', 'DISPLAY-ISOLATION.json']:
        review = json.loads((OUT / name).read_text())
        assert review['passed'] and review['bitstream_sha256'] == result['artifact_sha256']
        if name == 'TX-SKEW-REVIEW.json':
            assert review['q_to_pad_checks_pass'] and review['q_to_pad_budget_ns'] == [0.5,3.0]
    targets = json.loads((OUT / 'CONSTRAINT-TARGETS.json').read_text())
    assert targets['routed_netlist_used'] and targets['netlist_sha256'] == result['synthesis_netlist_sha256']
    assert targets['routed_netlist_sha256'] == sha(BUILD / 'impl/pnr/a745.vo')
    assert targets['timing_sdc_sha256'] == sha(PROJECT / 'constraints/timing.sdc')
    assert len(targets['tx_oddr_q_route_targets']) == 6 and targets['net_fifo_bundled_pointer']['bits'] == 12
    ports = (platform / 'a745_top.v').read_text()
    assert all(name in ports for name in ['rgmii_rxd', 'rgmii_rx_ctl', 'rgmii_rx_clk', 'a745_detection_rx #(.SESSION_CYCLES(100000000)) detection_rx'])
    assert not any(name in ports for name in ['command_parser', 'network_mode'])
    detection = json.loads((PROJECT / '.local/tests/detection-result.json').read_text())
    assert detection['passed'] and detection['display_only'] and detection['motion_command_receiver'] and detection['task_channel_separate']
    for name, expected in detection['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    detection_gate = json.loads((PROJECT / '.local/tests/detection-gate-result.json').read_text())
    assert detection_gate['passed'] and detection_gate['main_netlist_sha256'] == result['synthesis_netlist_sha256']
    for name, expected in detection_gate['input_sha256'].items():
        assert sha(Path(name)) == expected, name
    assert targets['rx_iddr_count'] == 5
    for receipt in ['mission-gate-result.json','path-geometry-result.json']:
        mission=json.loads((PROJECT/'.local/tests'/receipt).read_text())
        assert mission['passed']
        if receipt=='mission-gate-result.json':assert mission['main_netlist_sha256']==result['synthesis_netlist_sha256']
        for name,expected in mission['input_sha256'].items():assert sha(Path(name))==expected,name
    assert result['network_control_enabled'] and not result['network_arm_enabled']
    isolation=json.loads((OUT/'DISPLAY-ISOLATION.json').read_text())
    assert isolation['raw_rx_reaches_motor_outputs'] and len(isolation['unreachable_motor_outputs_from_ed10_box_data'])==4
    assert targets['ethernet_clock']['pll_output_mhz']==250 and targets['ethernet_clock']['mac_clock_mhz']==125
    for host in ['receiver.py', 'app.py']:
        tree = ast.parse((PROJECT / 'host' / host).read_text(encoding='utf-8'))
        assert not any(isinstance(n, ast.Attribute) and n.attr in ['send', 'sendto', 'sendall'] for n in ast.walk(tree))
    artifact = Path(result['artifact'])
    assert sha(artifact) == result['artifact_sha256']
    assert artifact.stat().st_mtime >= result['evidence_freshness_lower_bound_unix']
    revision = int(re.search(r"snapshot\[159:128\]<=32'd(\d+)", (PROJECT/'rtl/a745_core.v').read_text())[1])
    front_stop_mm = int(re.search(r'\bSTOP_MM=(\d+)', (PROJECT/'rtl/a745_autonomy.v').read_text())[1])
    record = {'status': 'review_passed_pending_programming', 'timing_signed_off': True, 'firmware_revision': revision,
              'artifact': str(artifact), 'artifact_sha256': result['artifact_sha256'], 'usercode': '0xA745',
              'hardware_programmed': False, 'hardware_display_verified': False, 'cold_boot_verified': False,
              'armed': False, 'rtl_tests_passed': len(expected_benches), 'protocol_checks_passed': True,
              'network_control_enabled': True, 'network_arm_enabled': False, 'local_mode3_required': True,
              'detection_display_rx_enabled': True, 'vm_off_confirmed': False,
              'application_verified': False,
              'motor_pads_dynamic': True, 'common_ground_must_remain_connected': True,
              'turn_geometry_verified': True, 'navigation_gate_checks_passed': True, 'front_stop_mm': front_stop_mm,
              'recorded_utc': datetime.now(timezone.utc).isoformat()}
    candidate=ROOT/'output/motion-task-20261103'/f'CANDIDATE-{revision}.json'
    candidate.write_text(json.dumps(record, indent=2) + '\n')
    result.update(timing_signed_off=True, review_record=str(candidate))
    (BUILD / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    shutil.copy2(BUILD / 'result.json', OUT / 'build-evidence-current/result.json')
    for name in ['result.json', 'protocol-result.json', 'cpu-gate-result.json', 'turn-geometry-result.json', 'navigation-gate-result.json', 'lidar-replay-result.json', 'detection-result.json', 'detection-gate-result.json', 'mission-gate-result.json', 'path-geometry-result.json']:
        shutil.copy2(PROJECT / '.local/tests' / name, OUT / ('tests-' + name))
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()

