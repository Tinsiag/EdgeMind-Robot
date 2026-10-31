"""Record real FW74508 Flash/passive evidence; never starts motion or programs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PROJECT = ROOT / 'code/camera-car-control/a745-autonomous'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def main():
    audit_path = OUT / 'flash/20261031T092737.270324Z/audit.json'
    health_path = OUT / 'imu-fault-20261031/74508-health-20261031.json'
    audit, health = read(audit_path), read(health_path)
    status = read(OUT / 'STATUS.json')
    build = read(PROJECT / '.local/gowin-a745-autonomous/result.json')
    navigation = read(PROJECT / '.local/tests/navigation-gate-result.json')
    assert build['compile_passed'] and build['timing_signed_off']
    assert navigation['passed'] and len(navigation['tests']) == 8
    assert navigation['main_netlist_sha256'] == build['synthesis_netlist_sha256']
    assert all(audit[k] for k in ['flash_program_verify_completed', 'reload_command_completed',
                                'configuration_ready', 'status_read_completed', 'user_code_verified'])
    assert audit['final_status_register'].lower() == '0x70022020'
    assert status['firmware_revision'] == 74508 and status['timing_signed_off']
    assert status['artifact_sha256'] == audit['sha256'] == build['artifact_sha256']
    assert hashlib.sha256(Path(status['artifact']).read_bytes()).hexdigest() == audit['sha256']
    states, attitudes = health['status'], health['attitude']
    assert len(states) >= 100 and len(attitudes) >= 100
    assert health['packets_sent'] == 0 and health['invalid_packets'] == 0
    assert all(s['revision'] == 74508 and s['state'] == 0 and s['faults'] == 0 and not s['armed']
               and s['targets'] == [0, 0] and s['imu_valid'] and s['gyro_valid']
               and s['imu_errors'] == 0 and s['camera_ready'] and s['ddr_ready'] and s['frame_ready']
               and not s['video_error'] and s['imu_fault_sources'] == 0 for s in states)
    assert all(a['tilt_valid'] and a['cpu_alive'] and not a['cpu_fault']
               and a['imu_fault_sources'] == 0 for a in attitudes)
    assert attitudes[-1]['cpu_progress'] > attitudes[0]['cpu_progress']
    assert states[-1]['video_frames'] > states[0]['video_frames']
    relative = lambda p: p.relative_to(ROOT).as_posix()
    analysis = dict(passed=True, hardware_revision=74508, hardware_sha256=audit['sha256'],
                    status_packets=len(states), attitude_packets=len(attitudes),
                    states=sorted({s['state'] for s in states}),
                    faults=sorted({s['faults'] for s in states}), packets_sent=0,
                    imu_errors=max(s['imu_errors'] for s in states),
                    max_imu_age_ms=max(s['imu_age_ms'] for s in states),
                    cpu_progress_delta=attitudes[-1]['cpu_progress']-attitudes[0]['cpu_progress'],
                    video_frame_delta=states[-1]['video_frames']-states[0]['video_frames'],
                    physical_motion_verified=False, cold_boot_verified=False,
                    input_sha256={relative(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [health_path, audit_path, Path(__file__).resolve()]})
    write(health_path.with_name('74508-health-20261031-ANALYSIS.json'), analysis)
    status.update(status='74508_flash_verified_passive_health_healthy_loaded_motion_pending',
                  hardware_programmed=True, current_hardware_revision=74508,
                  last_known_hardware_revision=74508, last_known_flash_sha256=audit['sha256'],
                  vm_off_confirmed=True, vm_state_note='User confirmed VM off after FW74507 ground fault; no subsequent motion. FW74508 reloaded without ARM.',
                  programming_audit=relative(audit_path), last_programming_attempt=relative(audit_path),
                  last_programming_returncode=0, final_status_register=audit['final_status_register'],
                  health_telemetry=relative(health_path), application_telemetry_healthy=True,
                  last_observed_status=states[-1], last_observed_attitude=attitudes[-1],
                  application_verified=False, candidate_application_verified=False,
                  hardware_display_verified=False, cold_boot_verified=False, physical_turning_verified=False,
                  err0001_fixed=False, root_cause_confirmed=False,
                  isolated_attitude_spike_mitigation_implemented=True,
                  attitude_filter='Three completed inclination samples ranked by max absolute roll/pitch; publish the median complete pair.',
                  attitude_filter_samples=3, tilt_limit_degrees=22.5,
                  sustained_tilt_typical_added_delay_ms=10, sustained_tilt_max_accepted_added_delay_ms=30,
                  kalman_filter_enabled=False, gyro_roll_pitch_fusion_enabled=False,
                  encoder_no_pulse_stops_motion=False, encoder_illegal_transition_fault_retained=True,
                  rear_stop_mm=350, reverse_stop_mm=350, reverse_speed_mm_s=60,
                  reverse_nominal_mm=100, reverse_max_ms=2000, reverse_settle_ms=150,
                  reverse_attempts_per_blocked_episode=1, current_hardware_front_stop_mm=300,
                  current_changes_pushed=False, last_pushed_commit='ac56a9e2fff37c3db84be713505248ef39f75f0d',
                  last_motion_report='FW74507 ground straight ERR0001, user reports no visible side tilt. FW74508 only passive health verified.',
                  last_fault_capture=relative(OUT/'imu-fault-20261031/74507-fault-20261031T085714Z.json'),
                  last_fault_analysis=relative(OUT/'imu-fault-20261031/74507-fault-20261031T085714Z-ANALYSIS.json'),
                  last_fault_sources=8, last_fault_valid_flags=239, last_fault_roll_deg=27.960205078125,
                  last_fault_pitch_deg=-1.900634765625, last_fault_status_ms=111199,
                  waiting_for='User-controlled loaded short straight/left/right tests and S1/S0 stops, plus actual cold boot for FW74508 SHA. If ERR0001 recurs: VM off, keep FAULT, no S1; capture before reset. Raw triggering IMU and original spike duration remain unavailable.',
                  recorded_utc=datetime.now(timezone.utc).isoformat())
    write(OUT/'STATUS.json', status)
    timing = read(OUT/'TIMING-REVIEW.json')
    release = dict(revision=74508, state=status['status'], sha256=audit['sha256'],
                   rtl_benches=status['rtl_tests_passed'], navigation_primitive_cases=len(navigation['tests']),
                   geometry_edge_points=122536, lidar_replay_points=91080,
                   flash_programmed=True, flash_audit=relative(audit_path), passive_health=relative(health_path),
                   application_verified=False, err0001_fixed=False, root_cause_confirmed=False,
                   display_verified=False, cold_boot_verified=False, motion_verified=False,
                   isolated_attitude_spike_mitigation_implemented=True,
                   timing_worst_slack_ns=timing['worst_reported_slack_ns'])
    write(OUT/'RELEASE-74508.json', release)
    print(json.dumps(analysis, indent=2))


if __name__ == '__main__':
    main()
