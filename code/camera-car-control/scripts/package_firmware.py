"""Archive a successful board build with pin, hash and timing evidence."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat

from check_fpga import ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = ROOT / '.local/gowin-board'
    record = json.loads((build / 'result.json').read_text())
    if not record['compile_passed'] or not record['bitstream_generated']:
        raise SystemExit('Refusing to package an unsuccessful build')
    artifact = Path(record['artifact'])
    if sha(artifact) != record['artifact_sha256']:
        raise SystemExit('Bitstream changed after build')
    for name, digest in record['source_sha256'].items():
        if sha(Path(name)) != digest:
            raise SystemExit('Source changed after build: ' + name)
    cst = ROOT / 'constraints/acg720_camera_car.cst'
    expected = dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+(\w+);', cst.read_text()))
    report = (build / 'impl/pnr/camera_car.rpt.txt').read_text(errors='replace')
    actual = {}
    for line in report.splitlines():
        match = re.match(r'^([A-Z]+\d+)/\S+\s*\|\s*([^|]+)\|', line)
        if match and match[2].strip() in expected:
            actual[match[2].strip()] = match[1]
    if actual != expected or len(set(actual.values())) != len(expected):
        raise SystemExit('Final PnR pin assignments do not match the complete CST')
    rtl = (ROOT / '.local/rtl-tests.log').read_text(errors='replace')
    host = (ROOT / '.local/host-tests.log').read_text(errors='replace')
    motion = (ROOT / '.local/motion-tests.log').read_text(errors='replace')
    checks = ['PASS board camera:', 'PASS camera_ethernet_core:',
              'PASS Ethernet/ARP/IPv4/UDP checksums', 'PASS camera_motion_core:',
              'PASS RGMII RX', 'PASS video_udp_packetizer:']
    if not all(value in rtl for value in checks) or 'FAILED' in host or not re.search(r'^OK$', host, re.M):
        raise SystemExit('Missing successful RTL or host test evidence')
    if 'FAILED' in motion or not re.search(r'^OK$', motion, re.M):
        raise SystemExit('Missing successful motion regression evidence')
    release = ROOT / 'release/A740-20261019'
    release.mkdir(parents=True, exist_ok=True)
    artifacts = {
        artifact: 'acg720_camera_car.fs',
        build / 'result.json': 'build-result.json',
        build / 'build.log': 'build.log',
        build / 'build.tcl': 'build.tcl',
        build / 'camera_car.gprj': 'camera_car.gprj',
        build / 'impl/pnr/camera_car.rpt.txt': 'pnr-report.txt',
        build / 'impl/pnr/camera_car.tr': 'timing-report.txt',
        build / 'impl/pnr/camera_car.tr.html': 'timing-report.html',
        ROOT / '.local/platform/provenance.json': 'platform-provenance.json',
        ROOT / '.local/platform/manifest.json': 'platform-manifest.json',
        ROOT / '.local/rtl-tests.log': 'rtl-tests.log',
        ROOT / '.local/host-tests.log': 'host-tests.log',
        ROOT / '.local/motion-tests.log': 'motion-tests.log',
        cst: cst.name,
        ROOT / 'constraints/acg720_camera_car.sdc': 'acg720_camera_car.sdc',
    }
    for source, name in artifacts.items():
        destination = release / name
        if destination.is_file() and sha(destination) == sha(source):
            continue
        if destination.exists():
            destination.chmod(destination.stat().st_mode | stat.S_IWRITE)
        shutil.copy2(source, destination)
    summary = {
        'firmware': 'A740', 'date': '2026-10-19', 'user_code': '0000A740',
        'bitstream_sha256': sha(artifact), 'pins_verified': len(expected),
        'python_tests': int(re.search(r'Ran (\d+) tests', host)[1]),
        'motion_python_tests': int(re.search(r'Ran (\d+) tests', motion)[1]),
        'rtl_testbenches': 5, 'network_frame_checks': True,
        'timing_violated_endpoints': record.get('timing_violated_endpoints'),
        'timing_signed_off': False, 'hardware_programmed': False, 'hardware_tested': False,
        'release_status': 'EXPERIMENTAL - timing and physical link validation pending',
        'pins': expected,
    }
    (release / 'audit.json').write_text(json.dumps(summary, indent=2)+'\n')
    hashes = {p.name: sha(p) for p in sorted(release.iterdir()) if p.is_file() and p.name != 'SHA256.json'}
    (release / 'SHA256.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    print('Packaged: ' + str(release))


if __name__ == '__main__':
    main()
