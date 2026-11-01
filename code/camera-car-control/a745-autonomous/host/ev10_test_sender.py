#!/usr/bin/env python3
"""Send synthetic EV10 line packets (same layout as a745_video_udp_tx.v).

Use to verify fpga_video_yolo_web.py without the FPGA:
  python ev10_test_sender.py --host 127.0.0.1 --image some.jpg --drop 0.01
"""
import argparse, random, socket, struct, time
import numpy as np


def to_rgb565(bgr):
    b, g, r = (bgr[..., i].astype(np.uint16) for i in range(3))
    return (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).astype('<u2')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1'); ap.add_argument('--port', type=int, default=6104)
    ap.add_argument('--image'); ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--frames', type=int, default=90); ap.add_argument('--drop', type=float, default=0.0)
    a = ap.parse_args()
    if a.image:
        import cv2
        img = cv2.resize(cv2.imread(a.image), (640, 480))
    else:
        y, x = np.mgrid[0:480, 0:640]
        img = np.stack([x * 255 // 639, y * 255 // 479, np.full_like(x, 128)], -1).astype(np.uint8)
    px = to_rgb565(img)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for fid in range(1, a.frames + 1):
        t = time.monotonic()
        for line in range(480):
            if random.random() < a.drop:
                continue
            s.sendto(b'EV10' + struct.pack('<IHH', fid, line, 1280) + px[line].tobytes(), (a.host, a.port))
        time.sleep(max(0, 1 / a.fps - (time.monotonic() - t)))
    print('sent', a.frames, 'frames')


if __name__ == '__main__':
    main()
