"""Replay CRC-checked board packets through the real RTL filter and scan guard."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def linux(p):
    s = p.resolve().as_posix()
    return '/mnt/' + s[0].lower() + s[2:]


def decode(path):
    result = []
    previous = None
    for item in json.loads(path.read_text())['datagrams']:
        data = bytes.fromhex(item['hex'])
        if data[:4] != b'EML1':
            continue
        assert len(data) == 64 and struct.unpack_from('<HH', data, 4) == (1, 64)
        seq = struct.unpack_from('<I', data, 8)[0]
        assert previous is None or seq == (previous + 1) & 0xffffffff, 'Capture lost a raw packet'
        previous = seq
        raw = data[16:63]
        assert raw[:2] == b'\x54\x2c'
        crc = 0
        for b in raw[:46]:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ 0x4d if crc & 128 else crc << 1) & 255
        assert crc == raw[46], 'Bad sensor CRC'
        start, end = struct.unpack_from('<H', raw, 4)[0], struct.unpack_from('<H', raw, 42)[0]
        span = (end - start) % 36000
        assert start < 36000 and end < 36000 and span <= 1500
        for i in range(12):
            d, c = struct.unpack_from('<HB', raw, 6 + i * 3)
            result.append(((start + span * i // 11) % 36000, d, c))
    assert len(result) >= 1000
    return result


def reference(samples):
    # Independent whole-group calculation, rather than RTL's five-point window.
    # Unlike the vendor's group-average rule, a strong singleton is kept by its
    # own intensity. Group support retains *all* points, not just the midpoint.
    keep = [d > 0 and c >= 20 and (d >= 5000 or c >= 220) for a, d, c in samples]
    groups = []
    group = []
    for i, (a, d, c) in enumerate(samples):
        eligible = 0 < d < 5000 and c >= 20
        joined = False
        if group and eligible:
            pa, pd, pc = samples[group[-1]]
            joined = 0 < (a - pa) % 36000 <= 250 and abs(d - pd) * 100 <= pd * 3
        if not joined and group:
            groups.append(group)
            group = []
        if eligible:
            group.append(i)
    if group:
        groups.append(group)
    for group in groups:
        if len(group) >= 3:
            for i in group:
                keep[i] = True
    return [c if k else 0 for (a, d, c), k in zip(samples, keep)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('capture', type=Path)
    args = ap.parse_args()
    samples = decode(args.capture)
    expected = reference(samples)
    out = ROOT / '.local/lidar-replay'
    out.mkdir(exist_ok=True)
    vector = out / 'points.hex'
    vector.write_text(''.join(f'{a:04x}{d:04x}{c:02x}{e:02x}\n'
                              for (a, d, c), e in zip(samples, expected)) + '0' * 12 + '\n' + '0' * 12 + '\n')
    bench = out / 'replay.v'
    bench.write_text('''`timescale 1ns/1ps
module replay;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,point_valid=0;
 reg [15:0] angle=0,distance=0;reg [7:0] confidence=0;
 wire filtered_valid;wire [15:0] filtered_angle,filtered_distance;wire [7:0] filtered_confidence;
 a745_lidar_filter filter(.clk(clk),.rst_n(rst_n),.stream_valid(1'b1),.*);
 wire raw_valid,new_valid,rl,rr,nl,nr;wire [15:0] rf,lf,rgt,rb,nf,nlf,nrgt,nb;
 wire [7:0] raw_seq,new_seq;
 a745_navigation_scan raw_scan(.clk(clk),.rst_n(rst_n),.ms_tick(1'b0),.stream_valid(1'b1),
  .point_valid(point_valid),.angle(angle),.distance(distance),.confidence(confidence),
  .scan_valid(raw_valid),.front(rf),.left(lf),.right(rgt),.rear(rb),.left_clear(rl),.right_clear(rr),.scan_sequence(raw_seq));
 a745_navigation_scan new_scan(.clk(clk),.rst_n(rst_n),.ms_tick(1'b0),.stream_valid(1'b1),
  .point_valid(filtered_valid),.angle(filtered_angle),.distance(filtered_distance),.confidence(filtered_confidence),
  .scan_valid(new_valid),.front(nf),.left(nlf),.right(nrgt),.rear(nb),.left_clear(nl),.right_clear(nr),.scan_sequence(new_seq));
 localparam N=SAMPLE_COUNT;
 reg [47:0] v[0:N+1];integer i,raw_scans=0,new_scans=0,raw_clear=0,new_clear=0;
 reg [7:0] last_raw=0,last_new=0;
 always @(posedge clk) begin
  #2;
  if(raw_seq!=last_raw) begin
   raw_scans=raw_scans+1;if(raw_valid && (rl || rr)) raw_clear=raw_clear+1;last_raw=raw_seq;
  end
  if(new_seq!=last_new) begin
   new_scans=new_scans+1;if(new_valid && (nl || nr)) new_clear=new_clear+1;last_new=new_seq;
  end
 end
 initial begin
  $readmemh("VECTOR_PATH",v);
  repeat(4) @(negedge clk);rst_n=1;
  for(i=0;i<N+2;i=i+1) begin
   @(negedge clk);point_valid=1;angle=v[i][47:32];distance=v[i][31:16];confidence=v[i][15:8];
   @(posedge clk);#1;
   if(i<2 && filtered_valid) $fatal(1,"early sample");
   if(i>=2 && (!filtered_valid || filtered_angle!==v[i-2][47:32] ||
     filtered_distance!==v[i-2][31:16] || filtered_confidence!==v[i-2][7:0]))
    $fatal(1,"raw replay mismatch at %0d",i-2);
  end
  @(negedge clk);point_valid=0;repeat(8) @(negedge clk);
  if(new_scans<100 || new_clear<100) $fatal(1,"static clear scene still blocked");
  $display("PASS REPLAY points=%0d raw_scans=%0d raw_clear=%0d filtered_scans=%0d filtered_clear=%0d front=%0d left=%0d right=%0d",N,raw_scans,raw_clear,new_scans,new_clear,nf,nlf,nrgt);$finish;
 end
endmodule
'''.replace('SAMPLE_COUNT', str(len(samples))).replace('VECTOR_PATH', linux(vector)))
    sources = [ROOT / 'rtl' / n for n in ['a745_lidar_filter.v', 'a745_navigation_scan.v', 'a745_turn_envelope.v']]
    prefix = ['wsl.exe', '-d', 'Ubuntu-26.04', '--cd', linux(ROOT), '--exec']
    product = out / 'replay.vvp'
    commands = [prefix + ['iverilog', '-g2012', '-s', 'replay', '-o', linux(product), linux(bench), *map(linux, sources)],
                prefix + ['vvp', linux(product)]]
    for phase, cmd in zip(['compile', 'execute'], commands):
        p = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=90)
        (out / f'{phase}.log').write_text(p.stdout + p.stderr, encoding='utf-8')
        assert p.returncode == 0, p.stdout + p.stderr
    assert 'PASS REPLAY' in p.stdout
    metrics = {k: int(v) for k, v in re.findall(r'(points|raw_scans|raw_clear|filtered_scans|filtered_clear|front|left|right)=(\d+)', p.stdout)}
    receipt = {'passed': True, 'capture': str(args.capture), 'packets_sent': 0,
               'physical_turning_tested': False, 'metrics': metrics,
               'weak_returns_rejected': sum(c >= 20 and d > 0 and e == 0 for (a, d, c), e in zip(samples, expected)),
               'input_sha256': {str(f): sha(f) for f in sources + [Path(__file__), args.capture]}}
    (ROOT / '.local/tests/lidar-replay-result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
