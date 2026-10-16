"""Archive the A71D build/program evidence without changing earlier records."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

repo = Path(__file__).resolve().parents[2]
root = repo / 'code/fpga/acg720-motor-test'
archive = root / 'verification/2026-10-15'
manifest_path = archive / 'SHA256SUMS.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, digest in manifest.items():
    assert sha(archive / name) == digest.lower(), name

audit_path = root / '.local/build-audit-left_static-wiring-20261014.json'
audit = json.loads(audit_path.read_text(encoding='utf-8'))
assert audit['bitstream_user_code'] == '0x0000A71D'
assert sha(root / 'impl/pnr/acg720_left_static.fs').upper() == audit['bitstream_sha256']
for name, digest in audit['source_sha256'].items():
    assert sha(root / name).upper() == digest, name

def logtext(name):
    data = (root / '.local' / name).read_bytes()
    return data.decode('utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')

assert '0x0000A71C' in logtext('before-left-static-usercode-20261015.log')
assert 'Finished.' in logtext('sram-left-static-program-20261015.log')
assert '0x0000A71D' in logtext('after-left-static-usercode-20261015.log')
assert '0x70022020' in logtext('after-left-static-status-20261015.log')
sim_path = root / '.local/sim/acg720_left_static_tb.log'
sim_data = sim_path.read_bytes()
assert 'PASS A71D' in sim_data.decode('utf-16' if sim_data[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')

sources = [sim_path, audit_path,
           root / 'impl/pnr/acg720_left_static.rpt.txt',
           root / 'impl/pnr/acg720_left_static_tr_content.html',
           root / 'impl/gwsynthesis/acg720_left_static.vg']
sources += [root / '.local' / name for name in (
    'build-left-static-20261015.log', 'before-left-static-usercode-20261015.log',
    'sram-left-static-program-20261015.log', 'after-left-static-usercode-20261015.log',
    'after-left-static-status-20261015.log')]
new_names = []
for src in sources:
    dst = archive / src.name
    assert not dst.exists(), dst
    shutil.copyfile(src, dst)
    new_names.append(dst.name)

evidence = {
    'recorded_at': datetime.now().astimezone().isoformat(),
    'user_request': '用户报告右电机驱动确认烧了；要求左LAIN1持续高、LAIN2持续低',
    'right_driver_damaged': {'source': 'user report', 'independently_verified_this_turn': False},
    'VM_state': '上轮用户明确VM未接；本轮沿用，未收到新状态确认；本轮未操作VM',
    'user_code': audit['bitstream_user_code'],
    'bitstream_sha256': audit['bitstream_sha256'],
    'source_sha256': audit['source_sha256'],
    'constant_output_buffers': audit['constant_output_buffers'],
    'timing_violations': audit['timing_violations'],
    'fmax_mhz': audit['fmax_mhz'], 'routed_port_count': len(audit['pins']),
    'simulation_passed': True, 'static_pinmap_tests_passed': 10,
    'before_user_code': '0x0000A71C', 'programming_operation': 'SRAM Program (2)',
    'flash_written': False, 'independent_after_user_code': '0x0000A71D',
    'independent_after_status': '0x70022020', 'device_id': '0x0001481B',
    'cable_location': 8740, 'output_changes_with_S0_S1_S2_clock_or_timer': False,
    'physical_output_voltages_measured': False, 'motor_start_verified': False,
    'motor_VM_must_remain_disconnected': True,
}
record = archive / 'left-static-build-program-evidence-20261015.json'
assert not record.exists(), record
record.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
new_names.append(record.name)

current = ('**最新：用户报告右电机驱动已损坏，已按要求切换为A71D左路持续高低电平版，'
           '独立回读A71D / 0x70022020。** LAIN1=A18/P7-5/L-1恒为1，'
           'LAIN2=A19/P7-6/L-2恒为0，右路两输入及相机复位恒低。无PWM、按键或超时门控，'
           'S0也不撤销固定输出。D1常亮、D2常灭；仅SRAM下载、未写Flash。VM断开状态沿用上轮用户确认，'
           'VM继续物理断开。未独立验证右模块损坏或左电机起动。'
           '详见 [A71D记录](LINK)。以下A71C及更早记录保留各历史阶段。')
for path, link in (
    (root / 'README.md', 'PREP-LEFT-STATIC-2026-10-15.md'),
    (repo / 'code/fpga/acg720-motion-control/README.md', '../acg720-motor-test/PREP-LEFT-STATIC-2026-10-15.md')):
    content = path.read_text(encoding='utf-8')
    lines = content.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.startswith('**最新：已切换到 A71C'))
    lines[index] = current.replace('LINK', link) + '\n'
    path.write_text(''.join(lines), encoding='utf-8')

bench = repo / 'code/fpga/acg720-motion-control/BENCH-RESUME-2026-10-15.md'
with bench.open('a', encoding='utf-8') as handle:
    handle.write('\n\n## 用户报告右驱动损坏，A71D左路固定输出已上板（当前）\n\n'
                 + current.replace('LINK', '../acg720-motor-test/PREP-LEFT-STATIC-2026-10-15.md')
                 + '\n\n专用仿真及公共10项静态管脚回归通过，实际21端口及OBUF常量审查通过；'
                   '50MHz setup/hold违例0/0，Fmax256.533MHz。构建完成21:06:15。'
                   '下载前回读A71C，核对源码和位流哈希后仅SRAM下载，随后独立回读A71D / 0x70022020。'
                   '位流SHA256=' + audit['bitstream_sha256'] + '。未接VM、未实测新输出电压。\n')

verification_readme = archive / 'README.md'
with verification_readme.open('a', encoding='utf-8') as handle:
    handle.write('\n\n最新A71D左路固定电平版：用户报告右驱动损坏后要求LAIN1=1/LAIN2=0，'
                 '右路两输入0，无PWM及按键/超时门控，VM继续断开。专用仿真、10项管脚静态回归、'
                 '21个PNR端口、OBUF常量及50MHz时序审查通过；仅SRAM下载并独立回读A71D / 0x70022020。'
                 '详见left-static-build-program-evidence-20261015.json；本轮未验证物理输出或电机起动。\n')
for name in new_names:
    manifest[name] = sha(archive / name)
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert all(sha(archive / name) == digest.lower() for name, digest in manifest.items())
print(f'Archived {len(new_names)} A71D records; all {len(manifest)} evidence hashes match; current handoff updated.')
