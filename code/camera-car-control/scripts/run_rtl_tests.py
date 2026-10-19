import argparse
from pathlib import Path
import subprocess
import sys

from check_fpga import ROOT, sources, tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iverilog')
    parser.add_argument('--vvp')
    args = parser.parse_args()
    output = ROOT / '.local/rtl'
    output.mkdir(parents=True, exist_ok=True)
    for test in sorted((ROOT / 'tests').glob('*_tb.v')):
        binary = output / (test.stem + '.vvp')
        dump = output / (test.stem + '.hex')
        uart_dump = output / (test.stem + '-uart.hex')
        extra = []
        if test.stem == 'camera_ethernet_core_tb':
            from network_vectors import make_vectors
            vector_path = output / 'network-input.hex'
            count = make_vectors(vector_path)
            extra = [f'+INPUT={vector_path}', f'+COUNT={count}']
        files = sources()
        if test.stem == 'board_platform_tb':
            files = [ROOT / 'rtl/ov5640_board_init.v',
                     ROOT.parent / 'fpga/acg720-ddr3/rtl/camera_init/ov5640_ctrl.v',
                     ROOT / '.local/platform/ov5640_init_table_rgb.v']
        elif test.stem == 'rgmii_rx_tb':
            files = [ROOT / 'rtl/acg720_rgmii_rx.v',
                     Path('C:/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw5a/prim_sim.v')]
        subprocess.run([tool('iverilog', args.iverilog), '-g2012', '-Wall', '-s', test.stem,
                        '-o', str(binary), *map(str, files), str(test)], check=True)
        result = subprocess.run([tool('vvp', args.vvp), '-i', str(binary), f'+DUMP={dump}', f'+UART={uart_dump}', *extra],
                                capture_output=True, text=True, timeout=300)
        print(result.stdout.strip())
        if result.returncode or 'PASS' not in result.stdout or 'FAIL' in result.stdout or 'FATAL' in result.stdout:
            raise SystemExit(result.stdout + result.stderr)
        if test.stem in ('board_platform_tb', 'rgmii_rx_tb'):
            continue
        if test.stem == 'camera_ethernet_core_tb':
            from network_vectors import verify_output
            verify_output(dump)
            continue
        sys.path.insert(0, str(ROOT / 'host'))
        from video import FrameAssembler
        assembler = FrameAssembler()
        frames = [f for line in dump.read_text().splitlines()
                  if (f := assembler.feed(bytes.fromhex(line), 0)) is not None]
        expected_dropped = 2 if test.stem == 'video_udp_packetizer_tb' else 1
        if len(frames) != 1 or assembler.dropped != expected_dropped:
            raise SystemExit(f'FAIL: host reassembly of RTL output: {test.stem}')
        if test.stem == 'video_udp_packetizer_tb':
            expected = b''.join((0x1000+i).to_bytes(2, 'big') for i in range(10))
        else:
            expected = b'\xf8\x00' * 8
            from legacy import FrameParser
            from protocol import decode_capabilities, decode_status
            replies = FrameParser().feed(bytes.fromhex(uart_dump.read_text()))
            if ([r[:2] for r in replies] != [(0xC0, 0x42), (0x80, 0x43)]
                    or not decode_capabilities(replies[0][2]).bridge_fixed
                    or decode_status(replies[1][2]).state != 0):
                raise SystemExit('FAIL: integrated UART CRC/capability/status')
        if frames[0][3] != expected:
            raise SystemExit('FAIL: RTL pixel byte order/content')
        print('PASS host decoded RTL packets and pixel content: ' + test.stem)


if __name__ == '__main__':
    main()
