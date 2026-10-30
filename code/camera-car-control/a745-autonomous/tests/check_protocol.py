"""Independently inspect bytes exported by RTL and validate the passive decoder."""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from receiver import decode_status, decode_attitude


def main():
    exported = ROOT / '.local/tests/udp-frames.hex'
    frames = [bytes.fromhex(line) for line in exported.read_text().splitlines()]
    assert len(frames) == 3
    records = []
    for frame, magic, payload_length in zip(frames, [b'EMS1', b'EMF1', b'EML1'], [112, 48, 64]):
        assert len(frame) == 14 + 20 + 8 + payload_length
        assert frame[:6] == b'\xff' * 6 and frame[6:12] == b'\x02\0\0\0\0\x02'
        assert frame[12:14] == b'\x08\x00'
        ip = frame[14:34]
        assert ip[0] == 0x45 and ip[9] == 17 and ip[12:16] == bytes([192, 168, 0, 2])
        assert ip[16:20] == b'\xff' * 4 and int.from_bytes(ip[2:4], 'big') == 28 + payload_length
        checksum = sum(struct.unpack('!10H', ip))
        while checksum >> 16:
            checksum = (checksum & 65535) + (checksum >> 16)
        assert checksum == 65535
        source, destination, length, udp_checksum = struct.unpack('!4H', frame[34:42])
        assert (source, destination, length, udp_checksum) == (6103, 6103, payload_length + 8, 0)
        assert frame[42:46] == magic
        records.append({'magic': magic.decode(), 'payload_bytes': payload_length,
                        'ipv4_checksum_valid': True, 'sha256': hashlib.sha256(frame).hexdigest()})
    status = bytearray(112)
    struct.pack_into('<4sHH', status, 0, b'EMS1', 1, 112)
    struct.pack_into('<H', status, 20, 0x320)
    struct.pack_into('<ii', status, 28, -60, 80)
    struct.pack_into('<I', status, 68, 0x300A5640)
    struct.pack_into('<I', status, 80, 12345)
    status[98], status[99] = 4, (12 << 3) | 4
    value = decode_status(status)
    assert value['targets'] == (-60, 80) and value['armed'] and value['frame_ready'] and value['ddr_ready']
    assert (value['camera_error'], value['camera_phase'], value['camera_attempt']) == (4, 12, 4)
    assert (value['camera_register'], value['camera_expected'], value['camera_value']) == (0x300A, 0x56, 0x40)
    assert value['video_frames'] == 12345 and not value['camera_ready']
    status[98], status[99] = 0, (11 << 3) | 1
    assert decode_status(status)['camera_ready']
    struct.pack_into('<I',status,16,74504)
    struct.pack_into('<HBB',status,104,750,1,123)
    value=decode_status(status)
    assert value['rear']==750 and value['left_clear'] and not value['right_clear'] and value['scan_sequence']==123
    fusion = bytearray(48)
    struct.pack_into('<4sHH', fusion, 0, b'EMF1', 1, 48)
    fusion[16] = 1
    struct.pack_into('<hh', fusion, 20, -16384, 8192)
    fusion[24], fusion[41] = 1, 2
    assert decode_attitude(fusion) == dict(roll=-90, pitch=45, tilt_valid=True, cpu_alive=True,cpu_fault=False,cpu_progress=0)
    struct.pack_into('<I', fusion, 37, 123456)
    fusion[41] = 4
    assert decode_attitude(fusion)['cpu_progress'] == 123456 and decode_attitude(fusion)['cpu_fault']
    for decoder, packet in [(decode_status, status), (decode_attitude, fusion)]:
        for invalid in [packet[:-1], packet + b'\0', b'xxxx' + packet[4:], packet[:4] + b'\x02\0' + packet[6:]]:
            try:
                decoder(invalid)
            except ValueError:
                continue
            raise AssertionError('Malformed packet accepted')
    receipt = {'passed': True, 'frames': records, 'decoder_camera_and_signed_values': True,
               'malformed_length_magic_version_rejected': True, 'packets_sent': 0,
               'export_sha256': hashlib.sha256(exported.read_bytes()).hexdigest(),
               'input_sha256': {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                [ROOT/'host/receiver.py',Path(__file__).resolve(),exported]}}
    (ROOT / '.local/tests/protocol-result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
