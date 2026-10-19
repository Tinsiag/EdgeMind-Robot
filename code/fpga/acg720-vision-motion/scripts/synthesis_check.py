"""Synthesis-only feasibility check of portable RTL; never runs P&R or bitgen."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gowin', required=True)
    args = parser.parse_args()
    out = build.ROOT / '.local' / 'synthesis'
    out.mkdir(parents=True, exist_ok=True)
    sources = sorted((build.ROOT / 'rtl').glob('*.v'))
    sources += [build.SHARED / (n + '.v') for n in build.SHARED_NAMES]
    project = ET.Element('Project')
    ET.SubElement(project, 'Template').text = 'FPGA'
    ET.SubElement(project, 'Version').text = '5'
    ET.SubElement(project, 'Device', {'name': 'GW5AT-60B', 'pn': build.PART}).text = 'gw5at60b-002'
    files = ET.SubElement(project, 'FileList')
    for path in sources:
        ET.SubElement(files, 'File', {'path': path.as_posix(), 'type': 'file.verilog', 'enable': '1'})
    ET.ElementTree(project).write(out / 'portable.gprj', encoding='utf-8', xml_declaration=True)
    tcl = '\n'.join(['cd [file dirname [file normalize [info script]]]',
                     'open_project portable.gprj', 'set_option -top_module vision_motion_top',
                     'set_option -output_base_name portable', 'run syn', ''])
    (out / 'synthesis.tcl').write_text(tcl, encoding='utf-8')
    command = [args.gowin, str(out / 'synthesis.tcl')]
    hashes = {p.as_posix(): build.digest(p) for p in sources}
    # Keep long-running synthesis output in a local log, not the chat transcript.
    with (out / 'synthesis.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    changed = any(build.digest(p) != hashes[p.as_posix()] for p in sources)
    record = {'returncode': result.returncode, 'sources_changed_during_run': changed,
              'pnr_run': False, 'bitstream_generated': False,
              'hardware_tested': False, 'timing_signed_off': False,
              'source_sha256': hashes}
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(out / 'synthesis.log')
    return result.returncode or int(changed)


if __name__ == '__main__':
    sys.exit(main())
