#!/bin/sh
# Diagnostic: is onnxruntime on this board slow for every model, or only for
# the YOLO graph? MobileNetV2 (~0.3 GFLOPs) is the Sipeed wiki's reference
# model. Guarded: low priority + hard timeout so the board stays usable.
set -eu
cd /home/debian/fpga

M=mobilenetv2-12.onnx
[ -f "$M" ] || wget -q --show-progress -O "$M" \
  https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx
ls -la "$M"

rm -f mnet.log
cat > _mn.py <<'PY'
import sys, time
import numpy as np, onnxruntime as ort
prov = sys.argv[1]
so = ort.SessionOptions(); so.intra_op_num_threads = 2; so.inter_op_num_threads = 1
t0 = time.time()
s = ort.InferenceSession('mobilenetv2-12.onnx', so, providers=[prov])
print('%s loaded %.1fs %s' % (prov, time.time()-t0, s.get_providers()), flush=True)
i = s.get_inputs()[0]
x = np.random.rand(1, 3, 224, 224).astype(np.float32)
for k in range(3):
    t = time.time(); o = s.run(None, {i.name: x})[0]
    print('%s run%d %.3fs out=%s' % (prov, k, time.time()-t, o.shape), flush=True)
print('OK', flush=True)
PY

setsid nohup nice -n 15 timeout -s KILL 180 \
    ./venv-system/bin/python -u _mn.py "${1:-CPUExecutionProvider}" \
    < /dev/null > mnet.log 2>&1 &
sleep 2
echo "launched mobilenet / ${1:-CPUExecutionProvider}"
