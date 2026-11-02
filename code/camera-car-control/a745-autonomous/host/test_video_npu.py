"""Run on Linux/4A: python3 -m unittest -v test_video_npu.py."""
import os
import sys
import time
import unittest

from npu_daemon import NpuDaemon


class ProtocolTests(unittest.TestCase):
    def client(self, script, timeout=.4):
        client = NpuDaemon([sys.executable, '-u', '-c', script], timeout=timeout,
                           start_timeout=timeout, input_bytes=16)
        self.addCleanup(client.close)
        return client

    def test_file_protocol_repeats_and_cleanup(self):
        client = self.client('''
import sys
print('INFO runtime'); print('READY 4')
for path in sys.stdin:
    assert open(path.strip(),'rb').read() == b'1234567890123456'
    print('TIME 6.5'); print('DET 1'); print('0 0.9 1 2 30 40'); print('END')
''')
        client.start(); path = client.path
        for _ in range(4):
            ms, boxes = client.infer(b'1234567890123456')
            self.assertEqual(ms, 6.5)
            self.assertEqual(boxes, [(0, .9, 1, 2, 30, 40)])
        proc = client.proc; client.close()
        self.assertIsNotNone(proc.poll()); self.assertFalse(os.path.exists(path))

    def test_start_timeout_without_newline(self):
        client = self.client("import time; print('stuck',end='',flush=True); time.sleep(10)")
        start = time.monotonic()
        with self.assertRaises(TimeoutError): client.start()
        self.assertLess(time.monotonic() - start, 3)
        self.assertIsNone(client.proc)

    def test_reply_timeout_closes_process_and_tensor(self):
        client = self.client("import sys,time; print('READY 4'); sys.stdin.readline(); time.sleep(10)")
        client.start(); path = client.path
        with self.assertRaises(TimeoutError): client.infer(b'x'*16)
        self.assertIsNone(client.proc); self.assertFalse(os.path.exists(path))

    def test_eof_and_invalid_reply(self):
        for reply in ("", "TIME 1\\nDET 2\\nEND", "TIME nan\\nDET 0\\nEND",
                      "TIME 1\\nDET 1\\n-1 .9 1 2 3 4\\nEND"):
            script = ("import sys; print('READY 4'); sys.stdin.readline(); "
                      + "print('" + reply + "',flush=True)")
            client = self.client(script)
            client.start()
            with self.assertRaises(RuntimeError): client.infer(b'x'*16)
            self.assertIsNone(client.proc)

    def test_reject_wrong_blob_size(self):
        client = self.client("print('READY 4'); input()")
        client.start()
        with self.assertRaises(ValueError): client.infer(b'x')


class ImageTests(unittest.TestCase):
    def test_rgb565_conversion_matches_reference_all_values(self):
        import numpy as np
        from fpga_video_yolo_web import rgb565_to_bgr
        values = (np.arange(480*640,dtype=np.uint32) % 65536).astype('<u2').reshape(480,640)
        bgr = rgb565_to_bgr(values.view(np.uint8).reshape(480,1280))
        r=(values>>11)&31; g=(values>>5)&63; b=values&31
        reference=np.stack(((b<<3)|(b>>2),(g<<2)|(g>>4),(r<<3)|(r>>2)),axis=-1).astype(np.uint8)
        np.testing.assert_array_equal(bgr,reference)

    def test_letterbox_and_inverse_coordinates(self):
        import numpy as np
        from fpga_video_yolo_web import NpuDetector, Assembler
        detector = NpuDetector(Assembler())
        class Stub:
            def infer(self, blob):
                image = np.frombuffer(blob,'<f4').reshape(3,384,640)
                # 640x480 -> 512x384, with 64 grey columns each side.
                np.testing.assert_allclose(image[:,:,:64],114/255,atol=1e-6)
                np.testing.assert_allclose(image[:,:,64:576],1)
                np.testing.assert_allclose(image[:,:,576:],114/255,atol=1e-6)
                return 6, [(0,.9,144,40,464,280)]
        detector.client = Stub()
        self.assertEqual(detector.detect(np.full((480,640,3),255,np.uint8)),
                         [dict(cls='person',score=.9,box=[100,50,500,350])])


if __name__ == '__main__': unittest.main()
