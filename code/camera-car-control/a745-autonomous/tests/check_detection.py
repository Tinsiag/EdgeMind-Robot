"""Seal the display-only interface and host protocol verification."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
def main():
    top = (ROOT/'rtl/a745_top.v').read_text()
    core = (ROOT/'rtl/a745_core.v').read_text()
    connection = re.search(r'a745_core core\((.*?)\);', top, re.S)[1]
    assert '.mac_diagnostic(detection_diagnostic)' in connection
    assert len(re.findall('mac_diagnostic', core)) == 2
    assert 'snapshot[191:184]<=mac_diagnostic' in core
    assert not any(x in connection for x in ('rx_data', 'detection_data', 'detection_update', 'gmii_rxd'))
    assert '.button_start(s1_start)' in connection
    assert 'a745_detection_overlay detection_overlay' in top
    assert '.pixel(overlay_pixel)' in top and '.pixel(camera_pixel)' in top
    assert '.cfg_rx_enable(phy_ready_rx[1])' in top
    assert not any(x in top for x in ('command_parser', 'network_mode'))
    p = subprocess.run([sys.executable, '-m', 'unittest', '-v', 'test_detection_return.py'],
                       cwd=ROOT/'host', capture_output=True, text=True)
    print(p.stdout+p.stderr)
    assert p.returncode == 0
    sources = [ROOT/'rtl'/name for name in ('a745_top.v','a745_core.v','a745_detection_rx.v',
                'a745_detection_overlay.v','a745_rgmii_rx.v')]
    sources += [ROOT/'host'/name for name in ('detection_return.py','test_detection_return.py','fpga_video_yolo_web.py')]
    sources.append(Path(__file__).resolve())
    record = dict(passed=True, display_only=True, motion_command_receiver=False,
                  diagnostic_core_usage='EMS1 byte23 only', packet_destination='192.168.0.2:6105',
                  host_tests=3, input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (ROOT/'.local/tests/detection-result.json').write_text(json.dumps(record, indent=2)+'\n')
    print('PASS display-only connections and independent host ED10 wire format')
if __name__ == '__main__':
    main()
