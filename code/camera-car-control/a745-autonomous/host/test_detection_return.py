import struct
import unittest
from detection_return import encode

class ReturnTests(unittest.TestCase):
    def test_independent_wire_layout(self):
        p = encode(0x12345678, [dict(cls='person', score=.8, box=[10,20,100,200])], ['person'])
        self.assertEqual(p.hex(), '454431307856341201008002e00100000a0014006400c80000cc0000')

    def test_empty_and_bounds(self):
        self.assertEqual(len(encode(0, [], [])), 16)
        boxes = [dict(cls='person', score=.8, box=[-1,0,100,200]),
                 dict(cls='person', score=.8, box=[0,0,640,480])]
        self.assertEqual(encode(0, boxes, ['person'])[8], 0)

    def test_top_eight_and_sequence_wrap(self):
        boxes = [dict(cls='person', score=i/20, box=[0,0,10,10]) for i in range(1,11)]
        p = encode(2**32+1, boxes, ['person'])
        self.assertEqual(struct.unpack_from('<I', p, 4)[0], 1)
        self.assertEqual(p[8], 8)
        self.assertEqual(len(p), 112)
        self.assertGreater(p[25], p[37])

if __name__ == '__main__':
    unittest.main()
