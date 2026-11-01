#!/usr/bin/env python3
"""Convert every FLOAT16 tensor in an ONNX model to FLOAT (fp32).

The shipped yolov5n.onnx is fp16 throughout, and the yolov5n_fp32.onnx beside
it is a half-finished conversion (fp32 initializers, fp16 graph I/O and
Constant nodes) that onnxruntime rejects with "Type parameter (T) of Optype
(Conv) bound to different types". OpenCV 4.6 on the Lichee Pi 4A cannot read
fp16 at all, so the board needs a consistently fp32 model.

usage: convert_onnx_fp16_to_fp32.py <in.onnx> <out.onnx>
"""
import sys
import numpy as np
import onnx
from onnx import numpy_helper

FP16 = onnx.TensorProto.FLOAT16
FP32 = onnx.TensorProto.FLOAT


def convert_tensor(t):
    if t.data_type != FP16:
        return False
    a = numpy_helper.to_array(t).astype(np.float32)
    new = numpy_helper.from_array(a, t.name)
    t.CopyFrom(new)
    return True


def convert_value(v):
    tt = v.type.tensor_type
    if tt.elem_type == FP16:
        tt.elem_type = FP32
        return True
    return False


def main():
    src, dst = sys.argv[1], sys.argv[2]
    m = onnx.load(src)
    g = m.graph
    n_init = sum(convert_tensor(t) for t in g.initializer)
    n_attr = 0
    for node in g.node:
        for a in node.attribute:
            if a.type == onnx.AttributeProto.TENSOR:
                n_attr += convert_tensor(a.t)
            elif a.type == onnx.AttributeProto.TENSORS:
                for t in a.tensors:
                    n_attr += convert_tensor(t)
    n_val = sum(convert_value(v) for v in list(g.input) + list(g.output) + list(g.value_info))
    onnx.checker.check_model(m)
    onnx.save(m, dst)
    print(f'{src} -> {dst}: {n_init} initializers, {n_attr} attribute tensors, {n_val} value types converted')


if __name__ == '__main__':
    main()
