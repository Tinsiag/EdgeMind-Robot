#!/usr/bin/env python3
"""Prepare a classic YOLOv5n ONNX for HHB / TH1520 NPU compilation.

HHB compiles the network up to the three raw detection convolutions and the
anchor decode is done afterwards on the CPU, so we extract exactly that
subgraph (dropping the Reshape/Sigmoid detect head whose constants are baked
for one input size) and set the input to 1x3x384x640, the shape the Sipeed
LPi4A wiki uses for its YOLOv5n NPU example.

usage: prepare_yolov5_for_hhb.py <in.onnx> <out.onnx> [H] [W]
"""
import sys
import onnx
from onnx import shape_inference

OUTPUTS = ['/model.24/m.0/Conv_output_0',
           '/model.24/m.1/Conv_output_0',
           '/model.24/m.2/Conv_output_0']


def main():
    src, dst = sys.argv[1], sys.argv[2]
    h = int(sys.argv[3]) if len(sys.argv) > 3 else 384
    w = int(sys.argv[4]) if len(sys.argv) > 4 else 640

    model = onnx.load(src)
    names = {o for n in model.graph.node for o in n.output}
    missing = [o for o in OUTPUTS if o not in names]
    if missing:
        raise SystemExit(f'missing detection conv outputs: {missing}')
    inp = model.graph.input[0].name

    # Keep only backbone+neck+3 convs; the detect head is replaced by CPU decode.
    onnx.utils.extract_model(src, dst, [inp], OUTPUTS)

    m = onnx.load(dst)
    d = m.graph.input[0].type.tensor_type.shape.dim
    d[0].dim_value, d[1].dim_value, d[2].dim_value, d[3].dim_value = 1, 3, h, w
    # Drop stale shapes so inference recomputes them for the new size.
    del m.graph.value_info[:]
    for o in m.graph.output:
        o.type.tensor_type.ClearField('shape')
    m = shape_inference.infer_shapes(m, strict_mode=True)
    onnx.checker.check_model(m)
    onnx.save(m, dst)

    shp = lambda v: [x.dim_value for x in v.type.tensor_type.shape.dim]
    print(f'{src} -> {dst}')
    print(f'  input  {m.graph.input[0].name} {shp(m.graph.input[0])}')
    for o in m.graph.output:
        print(f'  output {o.name} {shp(o)}')
    print(f'  nodes  {len(m.graph.node)}')


if __name__ == '__main__':
    main()
