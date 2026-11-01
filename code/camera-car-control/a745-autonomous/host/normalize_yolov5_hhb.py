#!/usr/bin/env python3
"""Normalize YOLOv5 ONNX for TH1520 HHB 2.4.5.

HHB rejects the exported Pow(x,2) detection-head op and mixed float16/float32
constants. This pass replaces Pow(x,2) with Mul(x,x) and promotes constants to
float32 before HHB import.
"""
import argparse, onnx, numpy as np
from onnx import helper, numpy_helper, TensorProto

ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); a=ap.parse_args()
m=onnx.load(a.src)
for i in m.graph.initializer:
    x=numpy_helper.to_array(i)
    if x.dtype==np.float16: i.CopyFrom(numpy_helper.from_array(x.astype(np.float32), i.name))
const={}
for n in m.graph.node:
    for at in n.attribute:
        if at.type==onnx.AttributeProto.TENSOR:
            x=numpy_helper.to_array(at.t)
            if x.dtype==np.float16: at.t.CopyFrom(numpy_helper.from_array(x.astype(np.float32)))
            const[n.output[0]]=x
new=[]
for n in m.graph.node:
    if n.op_type=='Pow' and len(n.input)>1 and n.input[1] in const and float(const[n.input[1]])==2.0:
        new.append(helper.make_node('Mul',[n.input[0],n.input[0]],list(n.output),name=n.name+'_mul'))
    else: new.append(n)
m.graph.ClearField('node'); m.graph.node.extend(new)
for x in list(m.graph.input)+list(m.graph.output):
    if x.type.tensor_type.elem_type==TensorProto.FLOAT16: x.type.tensor_type.elem_type=TensorProto.FLOAT
onnx.checker.check_model(m); onnx.save(m,a.dst)
