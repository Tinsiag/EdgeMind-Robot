from pathlib import Path
from datetime import datetime, timezone
import hashlib, html, json, re

P = Path(__file__).resolve().parent
ROOT = P.parents[2]
OUT = ROOT / 'output/flash-official480-9mhz-20261028'
OUT.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
b = json.loads((P / 'result.json').read_text())
r = json.loads((P / 'REVIEW.json').read_text())
s = json.loads((P / 'SIMULATION.json').read_text())
expected = '163ea290fec887007502fb65886d914a5e893249d9f04e5dde49d22bdec195cc'
assert b['returncode'] == 0 and r['passed'] and s['passed'] and r['motor_pads_grounded']
assert b['artifact_sha256'] == r['bitstream_sha256'] == sha(P / 'impl/pnr/probe.fs') == expected
assert all(sha(P / f) == h for f, h in b['source_sha256'].items())
assert all(sha(Path(f)) == h for f, h in s['input_sha256'].items())
assert sha(P / 'impl/pnr/probe.sdf') == r['sdf_sha256']
assert sha(P / 'impl/pnr/probe.vo') == r['vo_sha256']
assert len(r['windows']) == 20 and r['external_sample_edge_hypothesis'] == 'falling'
assert all(0.4 * 1000 / 9 <= 1000 / 18 + r['clock_arrival_ns'][0][i] - r['clock_arrival_ns'][1][i] <= 0.6 * 1000 / 9 for i in range(3))
assert all(v is not None and v > 0 for v in r['sta_worst_slack_ns'].values())
prior = P.parent / 'falling-sample-probe'
assert all(sha(P / n) == sha(prior / n) for n in ('wrapper.v', 'probe.cst', 'probe.gprj', 'src/disp_driver.v', 'src/pll_init.v'))
assert (P / 'probe.sdc').read_text() == (prior / 'probe.sdc').read_text().replace('lcd33m', 'lcd9m').replace('-multiply_by 33 -divide_by 50', '-multiply_by 9 -divide_by 50')
assert (P / 'src/disp_parameter_cfg.v').read_text() == (prior / 'src/disp_parameter_cfg.v').read_text().replace('\n//`define HW_TFT43', '\n`define HW_TFT43').replace('\n`define HW_TFT50', '\n//`define HW_TFT50')
vo = (P / 'impl/pnr/probe.vo').read_text()
for name, value in (('IDIV_SEL', 2), ('MDIV_SEL', 36), ('ODIV0_SEL', 100)):
    assert re.search(r'defparam\s+\\official/Gowin_PLL/u_pll/PLLA_inst\s+\.' + name + '=' + str(value) + ';', vo)
assert 'MULTI_FAC = 36;' in (P / 'src/gowin_pll/gowin_pll.v').read_text()
assert 'PLL_INIT(MULTI_FAC=36)' in (P / 'build.log').read_text()
assert '//UserCode: 0x0000a72f' in (P / 'impl/pnr/probe.fs').read_text()
assert not re.search(r'\b(?:WARN|ERROR)\b', (P / 'build.log').read_text())
pins = {'TFT_clk': 'AB20', 'TFT_hs': 'V19', 'TFT_vs': 'Y19', 'TFT_de': 'AB22', 'TFT_pwm': 'AB21',
        'left_in1': 'A18', 'left_in2': 'A19', 'right_in1': 'F13', 'right_in2': 'F14'}
pins.update({f'TFT_rgb[{i}]': pin for i, pin in enumerate('R18 R14 P14 U18 U17 N13 R16 P15 P17 N17 T18 L6 N15 R17 P16 N14'.split())})
rows = [list(map(html.unescape, re.findall(r'<td[^>]*>(.*?)</td>', row, re.S))) for row in re.findall(r'<tr>(.*?)</tr>', (P / 'impl/pnr/probe.pin.html').read_text(), re.S)]
for port, pin in pins.items():
    assert any(row and row[0] == port and any(cell.split('/')[0] == pin for cell in row) for row in rows), (port, pin)
evidence = ['result.json', 'REVIEW.json', 'SIMULATION.json', 'simulation.log', 'build.log', 'impl/pnr/probe.tr', 'impl/pnr/probe.sdf', 'impl/pnr/probe.vo', 'impl/pnr/probe.pin.html', 'impl/pnr/cmd.do']
auth = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'user_standing_authorization': '烧录，然后修改这个规定，你可以不用我授权直接烧写',
    'user_latest_direction': '你把我们刚刚能显示滑块的那个拿来再改改',
    'latest_feedback_before_candidate': '反转PCLK后跟之前一样的结果',
    'sha256': expected, 'bitstream': str(P / 'impl/pnr/probe.fs'),
    'preflight_passed': True, 'per_candidate_approval_required': False,
    'motor_vm_state': 'previous user confirmation retained; no reported change',
    'motor_pads_grounded': True, 'arm_authorized': False,
    'change': 'Official HW_TFT43 480x272/9MHz raster; matching eight-block dimensions and actual PLL/PLL_INIT; previous falling-edge mapping wrapper retained',
    'panel_resolution_confirmed': False, 'sample_edge_hypothesis': 'falling',
    'main_project_modified': False,
    'actual_pll': {'reference_mhz': 50, 'idiv': 2, 'mdiv': 36, 'odiv': 100, 'vco_mhz': 900, 'output_mhz': 9},
    'actual_pin_map': pins,
    'evidence_sha256': {f: sha(P / f) for f in evidence},
    'programming_script_sha256': sha(ROOT / 'scripts/fpga/program_flash.py'),
    'programming_tests_sha256': sha(ROOT / 'scripts/fpga/test_program_flash.py'),
    'programming_tests_passed_previously': 16,
    'configuration_verification': 'wait for documented wakeup/DONE and verify UserCode 0x0000A72F; no rewrite or SRAM fallback',
}
(OUT / 'AUTHORIZATION.json').write_text(json.dumps(auth, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('PASS exact image/source/simulation/STA/SDF; actual PLL9MHz and all TFT/motor pins checked; motor GND; no build warnings')
