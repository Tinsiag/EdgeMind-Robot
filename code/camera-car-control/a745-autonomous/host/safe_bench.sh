#!/bin/sh
# Guarded inference benchmark: low priority, limited threads, hard timeout,
# so a slow or crashing backend cannot wedge the 4-core board.
#
# usage: safe_bench.sh <model.onnx> <provider> <threads> <timeout_s>
set -eu
cd /home/debian/fpga

MODEL="${1:-yolov5nu_320.onnx}"
PROVIDER="${2:-ShlExecutionProvider}"
THREADS="${3:-2}"
TMO="${4:-240}"
OUT="safe_bench.log"

rm -f "$OUT"
cat > _sb.py <<'PY'
import os, sys, time
import numpy as np
model, provider, threads = sys.argv[1], sys.argv[2], int(sys.argv[3])
import onnxruntime as ort
so = ort.SessionOptions()
so.intra_op_num_threads = threads
so.inter_op_num_threads = 1
t0 = time.time()
s = ort.InferenceSession(model, so, providers=[provider])
print('loaded in %.1fs providers=%s' % (time.time() - t0, s.get_providers()), flush=True)
i = s.get_inputs()[0]
shape = [d if isinstance(d, int) and d > 0 else 1 for d in i.shape]
x = np.random.rand(*shape).astype(np.float32)
print('input %s %s' % (i.name, shape), flush=True)
for k in range(3):
    t = time.time()
    o = s.run(None, {i.name: x})[0]
    print('run%d %.2fs out=%s' % (k, time.time() - t, o.shape), flush=True)
print('OK', flush=True)
PY

# nice+ionice keep the video service responsive; timeout bounds the damage.
setsid nohup nice -n 15 timeout -s KILL "$TMO" \
    ./venv-system/bin/python -u _sb.py "$MODEL" "$PROVIDER" "$THREADS" \
    < /dev/null > "$OUT" 2>&1 &
sleep 2
echo "launched $MODEL / $PROVIDER / ${THREADS}t / ${TMO}s timeout"
