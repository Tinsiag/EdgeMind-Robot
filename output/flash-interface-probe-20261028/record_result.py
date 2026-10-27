from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
RUN = OUT / '20261027T172655.080769Z'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
a = json.loads((RUN / 'audit.json').read_text())
assert a['sha256'] == 'b7cb31acf792c9650a6e99299a5a077af61f5b6976d7af662ca295d47f13510b'
assert sha(RUN / 'image.fs') == a['sha256']
assert all(a[k] for k in ('flash_program_verify_completed', 'reload_command_completed', 'status_read_completed'))
assert len(a['steps']) == 3 and all(s['returncode'] == 0 for s in a['steps'])
assert 'Program and Verify Flash successfully.' in (RUN / 'flash_program_verify.console.log').read_text()
assert '0x30000460' in (RUN / 'read_status.console.log').read_text()
status = {
    'status': 'flash_verified_rolling_coloured_bands_not_correct_eight_blocks',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'bitstream_sha256': a['sha256'], 'log_directory': str(RUN),
    'flash_program_verify_completed': True, 'reload_completed': True,
    'status_read_completed': True, 'status_register': '0x30000460',
    'panel_size': [800, 480], 'pixel_clock_mhz': 33,
    'user_screen_reports': ['出现了彩色色块', '现在屏幕每大约一秒就闪烁一次，每次闪烁都会滑动色块', '后续澄清：滚动的彩色色条，并非清楚的两列四行八色块'],
    'user_led_report': 'D3闪烁，而且跟屏幕闪烁时间一致，D1，D2，D4也闪烁，D5，D0常亮',
    'backlight_toggle_seconds': 2**25/50000000,
    'colour_response_visible': True, 'correct_eight_blocks_verified': False, 'stable_picture_verified': False,
    'physical_pad_readback_observed': {'backlight': True, 'pclk_activity': True, 'de_seen': True},
    'application_verified': False, 'cold_boot_verified': False,
    'camera_sensors_network_active': False, 'main_project_source_preserved': True,
    'motor_pads_grounded': True, 'arm_sent': False, 'motion_started': False,
    'retry_attempted': False, 'standing_programming_authorization': True,
    'per_candidate_approval_required': False,
    'root_cause': 'not established; both pad primitives and backlight behaviour changed since previous white-screen build',
    'next_step': 'Keep successful interface/scanner, change only backlight to one startup delay then continuously on; inspect stable pattern',
    'led_map': {'D0': 'constant-on marker', 'D1': 'system heartbeat', 'D2': '16-frame heartbeat',
                'D3': 'backlight pad readback', 'D4': 'PCLK pad activity', 'D5': 'DE seen', 'D6-D7': 'off'}
}
(OUT / 'STATUS.json').write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
tracked = [*RUN.iterdir(), OUT/'AUTHORIZATION.json', OUT/'STATUS.json', Path(__file__)]
(OUT / 'ARTIFACT-SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)): sha(p) for p in tracked if p.is_file()}, indent=2)+'\n')
print('PASS Flash54/verify/reload/status/staged SHA; user sees blinking/sliding colour blocks; full application/cold boot unverified')
