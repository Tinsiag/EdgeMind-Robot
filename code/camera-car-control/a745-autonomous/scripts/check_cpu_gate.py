"""Synthesize the real supervisor and execute its Gowin primitive netlist."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linux(path):
    value = path.resolve().as_posix()
    return '/mnt/' + value[0].lower() + value[2:]


def main():
    out = ROOT / '.local/cpu-gate-check'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'firmware').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'firmware/mission.hex', out / 'firmware/mission.hex')
    top = out / 'cpu_gate_probe.v'
    top.write_text('module cpu_gate_probe(input wire clk,rst_n,ms_tick,armed,output wire alive,fault,output wire [31:0] progress);\na741_bare_cpu cpu(.*);endmodule\n')
    files = [top, ROOT / 'lib/a741_bare_cpu.v', ROOT / 'vendor/picorv32.v', ROOT / 'rtl/a745_cpu_regs.v']
    bench = ROOT / 'tests/gates/supervisor_gate_tb.v'
    primitive = Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')
    inputs = files[1:] + [bench, primitive, ROOT / 'firmware/mission.hex']
    hashes = {str(p): sha(p) for p in inputs}
    project = ET.Element('Project')
    ET.SubElement(project, 'Template').text = 'FPGA'
    ET.SubElement(project, 'Version').text = '5'
    ET.SubElement(project, 'Device', name='GW5AT-60B', pn='GW5AT-LV60PG484AC1/I0').text = 'gw5at60b-002'
    listing = ET.SubElement(project, 'FileList')
    for path in files:
        ET.SubElement(listing, 'File', path=path.as_posix(), type='file.verilog', enable='1')
    (out / 'cpu.gprj').write_bytes(ET.tostring(project, encoding='utf-8', xml_declaration=True))
    tcl = out / 'build.tcl'
    tcl.write_text('cd [file dirname [file normalize [info script]]]\nopen_project cpu.gprj\nset_option -top_module cpu_gate_probe\nset_option -output_base_name cpu\nset_option -verilog_std sysv2017\nrun syn\n')
    with (out / 'build.log').open('w', encoding='utf-8') as log:
        subprocess.run(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe', str(tcl)],
                       cwd=out, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    netlist = out / 'impl/gwsynthesis/cpu.vg'
    text = netlist.read_text(encoding='utf-8')
    assert 'SDPB cpuregs_cpuregs' not in text, 'Synchronous RAM cannot implement combinational register reads'
    assert 'module a745_cpu_regs' in text
    prefix = ['wsl.exe', '-d', 'Ubuntu-26.04', '--cd', linux(ROOT), '--exec']
    product = '/var/tmp/edgemind-a745-cpu-gate.vvp'
    compile_command = prefix + ['iverilog', '-g2012', '-s', 'supervisor_gate_tb', '-o', product,
                                 linux(bench), linux(netlist), linux(primitive)]
    compiled = subprocess.run(compile_command, capture_output=True, text=True, errors='replace', timeout=90)
    (out / 'compile.log').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    executed = subprocess.run(prefix + ['timeout', '80s', 'vvp', product], capture_output=True, text=True, errors='replace', timeout=90)
    (out / 'execution.log').write_text(executed.stdout + executed.stderr, encoding='utf-8')
    assert executed.returncode == 0 and 'PASS synthesized GW5A supervisor' in executed.stdout, executed.stdout + executed.stderr
    assert hashes == {str(p): sha(p) for p in inputs}, 'Gate test inputs changed'
    receipt = {'passed': True, 'input_sha256': hashes, 'netlist_sha256': sha(netlist),
               'synchronous_register_file_ram_count': 0, 'primitive_model': str(primitive),
               'actual_board_tested': False}
    result = ROOT / '.local/tests/cpu-gate-result.json'
    result.parent.mkdir(exist_ok=True)
    result.write_text(json.dumps(receipt, indent=2) + '\n')
    print(executed.stdout.strip())


if __name__ == '__main__':
    main()
