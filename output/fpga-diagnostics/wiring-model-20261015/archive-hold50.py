from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[3]
project = root / 'code/fpga/acg720-motor-test'
archive = project / 'verification/2026-10-15'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path = archive / 'SHA256SUMS.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
# Preserve the earlier A71A evidence byte-for-byte; keep this repeat separately.
for name in ['acg720_bridge_probe_tb.log', 'acg720_bridge_probe_duration_tb.log']:
    prior = project / '.local/sim' / name
    assert digest(prior) == manifest[name], name
    if digest(archive / name) != manifest[name]:
        shutil.copyfile(archive / name, archive / ('hold50-regression-' + name))
        shutil.copyfile(prior, archive / name)
for name, expected in manifest.items():
    assert digest(archive / name) == expected, f'Historical evidence mismatch: {name}'

audit = json.loads((project / '.local/build-audit-hold50-wiring-20261014.json').read_text(encoding='utf-8'))
assert audit['bitstream_user_code'] == '0x0000A71B'
assert audit['bitstream_sha256'] == digest(project / 'impl/pnr/acg720_motor_hold_1khz_50.fs').upper()
for name, expected in audit['source_sha256'].items():
    assert digest(project / name).upper() == expected, name
assert '0x0000A71B' in (archive / 'after-hold50-usercode-20261015.log').read_text(encoding='utf-8')
assert '0x70022020' in (archive / 'after-hold50-status-20261015.log').read_text(encoding='utf-8')

for source, target in [
    ('.local/build-audit-hold50-wiring-20261014.json', 'build-audit-hold50-wiring-20261014.json'),
    ('impl/pnr/acg720_motor_hold_1khz_50.rpt.txt', 'acg720_motor_hold_1khz_50.rpt.txt'),
    ('impl/pnr/acg720_motor_hold_1khz_50_tr_content.html', 'acg720_motor_hold_1khz_50_tr_content.html'),
]:
    shutil.copyfile(project / source, archive / target)

evidence = {
    'recorded_at': datetime.now().astimezone().isoformat(),
    'user_code': '0x0000A71B', 'device_id': '0x0001481B',
    'bitstream_sha256': audit['bitstream_sha256'],
    'source_sha256': audit['source_sha256'],
    'build_time': datetime.fromtimestamp((project / 'impl/pnr/acg720_motor_hold_1khz_50.fs').stat().st_mtime).astimezone().isoformat(),
    'routed_ports_checked': 21, 'timing_violations': audit['timing_violations'],
    'fmax_mhz': audit['fmax_mhz'],
    'simulations_passed': ['acg720_motor_hold_safety_tb','acg720_motor_hold_duration_tb',
                           'acg720_bridge_probe_tb','acg720_bridge_probe_duration_tb'],
    'static_pinmap_tests_passed': 10,
    'interface_correction': 'six-wire photo header is R, four-wire header is L; original CST matches all eight signals',
    'programming_operation': 'SRAM Program (2), no Flash write',
    'before_user_code': '0x0000A719', 'after_user_code': '0x0000A71B',
    'after_status': '0x70022020', 'cable_location': 8740,
    'pre_program_user_confirmed': {'VM_disconnected': True, 'FPGA_logic_power_on': True,
                                  'wheels_raised': True, 'S1_S2_released': True},
    'programmer_path_note': 'Initial relative fsFile rejected without programming; absolute verified path succeeded.',
    'motor_test_requested': 'S1 once, max 1 second, wheels raised, then release and disconnect VM',
    'motor_test_result': None,
}
(archive / 'hold50-build-program-evidence-20261015.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in archive.iterdir():
    if p.is_file() and p.name not in {'README.md','SHA256SUMS.json'}:
        manifest[p.name] = digest(p)
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Archived A71B build/program evidence; all {len(manifest)} evidence hashes verified, prior A71A logs restored unchanged.')
