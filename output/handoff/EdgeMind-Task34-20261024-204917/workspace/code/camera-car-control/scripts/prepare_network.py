"""Copy a pinned MIT Ethernet stack into this project's third_party directory."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = '77320a9471d19c7dd383914bc049e02d9f4f1ffb'
ETHERNET = ('udp_complete udp udp_ip_rx udp_ip_tx udp_checksum_gen ip_complete ip ip_eth_rx ip_eth_tx '
            'arp arp_eth_rx arp_eth_tx arp_cache eth_arb_mux ip_arb_mux eth_axis_rx eth_axis_tx '
            'lfsr eth_mac_1g_fifo eth_mac_1g axis_gmii_rx axis_gmii_tx').split()
AXIS = ('arbiter priority_encoder axis_fifo axis_fifo_adapter axis_adapter '
        'axis_async_fifo axis_async_fifo_adapter').split()


def main():
    source = ROOT / '.local/verilog-ethernet'
    if not source.is_dir():
        subprocess.run(['git', 'clone', 'https://github.com/alexforencich/verilog-ethernet.git', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', REVISION], check=True)
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != REVISION:
        raise SystemExit(f'Unexpected dependency revision {actual}; expected {REVISION}')
    target = ROOT / 'third_party/verilog-ethernet'
    (target / 'rtl').mkdir(parents=True, exist_ok=True)
    manifest = {'upstream': 'https://github.com/alexforencich/verilog-ethernet', 'commit': actual, 'sha256': {}}
    for name, folder in [(n, 'rtl') for n in ETHERNET] + [(n, 'lib/axis/rtl') for n in AXIS]:
        path = source / folder / (name + '.v')
        output = target / 'rtl' / path.name
        shutil.copy2(path, output)
        manifest['sha256']['rtl/' + path.name] = hashlib.sha256(output.read_bytes()).hexdigest()
    shutil.copy2(source / 'COPYING', target / 'COPYING')
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(manifest["sha256"])} pinned upstream RTL files with MIT license.')


if __name__ == '__main__':
    main()
