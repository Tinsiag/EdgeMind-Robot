from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

OUT = Path(__file__).resolve().parent
RUN = OUT / '20261027T183907.572515Z'
CANDIDATE = OUT.parent / 'tft800-official-20261028/official480-9mhz-probe'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
a = json.loads((RUN / 'audit.json').read_text())
expected = '163ea290fec887007502fb65886d914a5e893249d9f04e5dde49d22bdec195cc'
assert a['sha256'] == sha(RUN / 'image.fs') == sha(CANDIDATE / 'impl/pnr/probe.fs') == expected
assert all(a[k] for k in ('flash_program_verify_completed', 'reload_command_completed', 'status_read_completed', 'configuration_ready', 'user_code_verified'))
assert all(s['returncode'] == 0 and s['state'] == 'completed' for s in a['steps'])
ops = [s['command'][s['command'].index('--run') + 1] for s in a['steps']]
assert ops.count('54') == 1 and ops.count('1') == 1 and ops.count('73') == 1 and set(ops) <= {'54', '1', '74', '73'}
assert a['read_user_code'] == a['expected_user_code'] == '0x0000A72F'
assert 'Program and Verify Flash successfully.' in (RUN / 'flash_program_verify.console.log').read_text()
auth = json.loads((OUT / 'AUTHORIZATION.json').read_text(encoding='utf-8'))
assert auth['preflight_passed'] and auth['sha256'] == expected
assert all(sha(CANDIDATE / f) == h for f, h in auth['evidence_sha256'].items())
status = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'flash_ready_version_matched_480x272_9mhz_color_blocks_unstable',
    'bitstream_sha256': expected,
    'parent_bitstream_sha256': '7c0e06d8a814430e7b22d2a09787f55ccca7f3c1686df8786b0c4c4afa29e198',
    'log_directory': str(RUN), 'flash_program_verify_completed': True, 'reload_completed': True,
    'status_read_completed': True, 'initial_status_register': a['configuration_status_samples'][0]['raw'],
    'final_status_register': a['final_status_register'], 'configuration_ready': True,
    'user_code_verified': True, 'read_user_code': a['read_user_code'],
    'status_sample_count': len(a['configuration_status_samples']),
    'application_verified': False, 'cold_boot_verified': False,
    'pixel_clock_mhz': 9, 'active_raster_size': [480, 272], 'total_raster_size': [525, 286],
    'physical_panel_resolution_confirmed': False,
    'change': auth['change'], 'sample_edge_hypothesis': 'falling',
    'user_screen_report': '有色块，但仍滑动或排列随机；上下被中间线分成不同色块',
    'user_report_history': ['还是全白', '不对，这次不同了，有色块了', '有色块，但仍滑动或排列随机', '上下被这一条线分成了不同色块', '两灯都灭时也有色块', '刚刚那个照片是两灯都亮时'],
    'report_interpretation': 'Color response confirmed but unstable. Photo shows portrait installation and divided colors; both mode LEDs on contradicts the programmed 0/1/2 state set, so photo cannot be confidently assigned to a control mode.',
    'user_photo_path': 'C:/Users/sc/Documents/Tencent Files/2153958001/nt_qq/nt_data/Pic/2026-10/Ori/66b0d78ea4563a1df775edfcec6b86f1.png',
    'mode_seconds': 8.008,
    'modes': [
        {'D6': False, 'D7': False, 'AB22': 'DE', 'AB21': 'high', 'observation': '两灯都灭时也有色块'},
        {'D6': True, 'D7': False, 'AB22': 'high', 'AB21': 'DE', 'observation': None},
        {'D6': False, 'D7': True, 'AB22': 'DE', 'AB21': 'DE', 'observation': None},
    ],
    'camera_sensors_network_active': False, 'main_project_source_preserved': True,
    'motor_pads_grounded': True, 'arm_sent': False, 'motion_started': False,
    'standing_programming_authorization': True, 'per_candidate_approval_required': False,
    'rewrite_attempted': False, 'status_read_only_polling': True,
}
(OUT / 'STATUS.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(CANDIDATE / 'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(CANDIDATE)): sha(p) for p in CANDIDATE.rglob('*') if p.is_file() and p.name != 'ARTIFACT-SHA256.json'}, indent=2) + '\n')
files = [*RUN.iterdir(), OUT / 'AUTHORIZATION.json', OUT / 'STATUS.json', Path(__file__)]
(OUT / 'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)): sha(p) for p in files if p.is_file()}, indent=2) + '\n')
print('PASS Flash verify/ready/UserCode0xA72F; color blocks visible but unstable; application not accepted; status', a['final_status_register'])
